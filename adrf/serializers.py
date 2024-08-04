import asyncio
import traceback
from collections import OrderedDict
from typing import (
    Any,
    Callable,
    Dict,
    List,
    NoReturn,
    Protocol,
    Set,
    Type,
    TypeGuard,
    cast,
)

from asgiref.sync import sync_to_async
from async_property import async_property
from async_property.base import AsyncPropertyDescriptor
from django.db import models
from rest_framework.fields import Field, SkipField
from rest_framework.serializers import (
    LIST_SERIALIZER_KWARGS,
    model_meta,  # type: ignore
    raise_errors_on_nested_writes,
)
from rest_framework.serializers import BaseSerializer as DRFBaseSerializer
from rest_framework.serializers import ListSerializer as DRFListSerializer
from rest_framework.serializers import ModelSerializer as DRFModelSerializer
from rest_framework.serializers import Serializer as DRFSerializer
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList


class AsyncSerializerProtocol(Protocol):
    @async_property
    async def adata(self): ...
    async def ato_representation(self, data: Any) -> Any: ...
    async def aupdate(self, instance: Any, validated_data: Any) -> Any: ...
    async def acreate(self, validated_data: Any) -> Any: ...
    async def asave(self, **kwargs: Any) -> Any: ...


class HasAtoRepresentation(Protocol):
    async def ato_representation(self, instance: Any) -> Any: ...


def has_ato_representation(obj: Any) -> TypeGuard[HasAtoRepresentation]:
    return asyncio.iscoroutinefunction(getattr(obj, "ato_representation", None))


class HasAcreate(Protocol):
    async def acreate(self, validated_data: Any): ...


def has_acreate(obj: Any) -> TypeGuard[HasAcreate]:
    return asyncio.iscoroutinefunction(getattr(obj, "acreate", None))


class HasAdata(Protocol):
    @async_property
    async def adata(self) -> Any: ...


def has_adata(obj: Any) -> TypeGuard[HasAdata]:
    if hasattr(obj, "adata"):
        assert isinstance(getattr(obj.__class__, "adata"), AsyncPropertyDescriptor)
        return True
    return False
    # return isinstance(getattr(obj.__class__, "adata", None), AsyncPropertyDescriptor)


class HasAsave(Protocol):
    async def asave(self, **kwargs: Any): ...


def has_asave(obj: Any) -> TypeGuard[HasAsave]:
    return asyncio.iscoroutinefunction(getattr(obj, "asave", None))


async def serializer_adata(serializer: DRFBaseSerializer):
    """Use adata if the serializer supports it, data otherwise."""
    return await (
        serializer.adata
        if has_adata(serializer)
        else sync_to_async(lambda: serializer.data)()
    )


async def serializer_asave(serializer: DRFBaseSerializer, **kwargs: Any):
    """Use asave() if the serializer supports it, save() otherwise."""
    return await (
        serializer.asave(**kwargs)
        if has_asave(serializer)
        else sync_to_async(serializer.save)(**kwargs)
    )


# NOTE This is the list of fields defined by DRF for which we need to call to_representation.
SOOP_FREE_DRF_FIELDS = cast(  # djangorestframework-types-0.8.0 has wrong declarations
    Set[Type[Field[Any, Any, Any, Any]]],
    set(
        list(DRFModelSerializer.serializer_field_mapping.values())
        + [
            DRFModelSerializer.serializer_related_field,
            DRFModelSerializer.serializer_related_to_field,  # SlugRelatedField is free from SO-op?
            DRFModelSerializer.serializer_url_field,
            DRFModelSerializer.serializer_choice_field,
        ]
    ),
)


class BaseSerializer(DRFBaseSerializer):
    """
    Base serializer class.
    """

    @classmethod
    def many_init(cls, *args: Any, **kwargs: Any):
        allow_empty = kwargs.pop("allow_empty", None)
        max_length = kwargs.pop("max_length", None)
        min_length = kwargs.pop("min_length", None)
        child_serializer = cls(*args, **kwargs)
        list_kwargs = {
            "child": child_serializer,
        }
        if allow_empty is not None:
            list_kwargs["allow_empty"] = allow_empty
        if max_length is not None:
            list_kwargs["max_length"] = max_length
        if min_length is not None:
            list_kwargs["min_length"] = min_length
        list_kwargs.update(
            {
                key: value
                for key, value in kwargs.items()
                if key in LIST_SERIALIZER_KWARGS
            }
        )
        meta = getattr(cls, "Meta", None)
        list_serializer_class = getattr(meta, "list_serializer_class", ListSerializer)
        return list_serializer_class(*args, **list_kwargs)

    @async_property
    async def adata(self):
        if hasattr(self, "initial_data") and not hasattr(self, "_validated_data"):
            msg = (
                "When a serializer is passed a `data` keyword argument you "
                "must call `.is_valid()` before attempting to access the "
                "serialized `.data` representation.\n"
                "You should either call `.is_valid()` first, "
                "or access `.initial_data` instead."
            )
            raise AssertionError(msg)

        if not hasattr(self, "_data"):
            if self.instance is not None and not getattr(self, "_errors", None):
                self._data = await self.ato_representation(self.instance)
            elif hasattr(self, "_validated_data") and not getattr(
                self, "_errors", None
            ):
                self._data = await self.ato_representation(self.validated_data)
            else:
                self._data = self.get_initial()

        return self._data

    async def ato_representation(self, instance: Any) -> Any:
        raise NotImplementedError("`ato_representation()` must be implemented.")

    async def aupdate(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError("`aupdate()` must be implemented.")

    async def acreate(self, validated_data: Any) -> Any:
        raise NotImplementedError("`acreate()` must be implemented.")

    async def asave(self, **kwargs: Any):
        assert hasattr(
            self, "_errors"
        ), "You must call `.is_valid()` before calling `.asave()`."

        assert (
            not self.errors
        ), "You cannot call `.asave()` on a serializer with invalid data."

        # Guard against incorrect use of `serializer.asave(commit=False)`
        assert "commit" not in kwargs, (
            "'commit' is not a valid keyword argument to the 'asave()' method."
            " If you need to access data before committing to the database"
            " then inspect 'serializer.validated_data' instead. You can also"
            " pass additional keyword arguments to 'asave()' if you need to"
            " set extra attributes on the saved model instance. For example:"
            " 'serializer.asave(owner=request.user)'.'"
        )

        assert not hasattr(self, "_data"), (
            "If you need to access data before committing to the database then"
            " inspect 'serializer.validated_data' instead. "
        )

        validated_data = {**self.validated_data, **kwargs}

        if self.instance is not None:
            self.instance = await self.aupdate(self.instance, validated_data)
            assert (
                self.instance is not None
            ), "`aupdate()` did not return an object instance."
        else:
            self.instance = await self.acreate(validated_data)
            assert (
                self.instance is not None
            ), "`acreate()` did not return an object instance."

        return self.instance


class Serializer(BaseSerializer, DRFSerializer):
    @async_property
    async def adata(self):
        """
        Return the serialized data on the serializer.
        """

        ret = await super().adata

        return ReturnDict(ret, serializer=self)  # type: ignore  # djangorestframework-types-0.8.0 has wrong declarations

    async def ato_representation(self, instance: Any) -> Any:
        """
        Object instance -> Dict of primitive datatypes.
        """

        ret: Dict[str, Any] = OrderedDict()
        fields = self._readable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            check_for_none = (
                attribute.pk if isinstance(attribute, models.Model) else attribute
            )
            field_name = field.field_name
            assert field_name is not None
            if check_for_none is None:
                ret[field_name] = None
            else:
                if type(field) in SOOP_FREE_DRF_FIELDS:
                    repr = field.to_representation(attribute)
                elif has_ato_representation(field):
                    repr = await field.ato_representation(attribute)
                else:
                    repr = await sync_to_async(field.to_representation)(attribute)

                ret[field_name] = repr

        return ret


class ListSerializer(BaseSerializer, DRFListSerializer):
    async def ato_representation(self, data: Any) -> Any:  # pyright: ignore[reportIncompatibleMethodOverride]
        """
        List of object instances -> List of dicts of primitive datatypes.
        """
        # Dealing with nested relationships, data can be a Manager,
        # so, first get a queryset from the Manager if needed

        if isinstance(data, models.Manager):
            data = data.all()

        if has_ato_representation(self.child):
            if isinstance(data, models.query.QuerySet):
                return [
                    await self.child.ato_representation(item)
                    async for item in data  # type: ignore
                ]
            else:
                return [await self.child.ato_representation(item) for item in data]
        else:
            assert self.child is not None
            if isinstance(data, models.query.QuerySet):
                return [
                    await sync_to_async(
                        cast(Callable[[Any], Any], self.child.to_representation)
                    )(item)
                    async for item in data  # type: ignore
                ]
            else:
                return [
                    await sync_to_async(
                        cast(Callable[[Any], Any], self.child.to_representation)
                    )(item)
                    for item in data
                ]

    async def asave(self, **kwargs: Any) -> Any:
        """
        Save and return a list of object instances.
        """
        # Guard against incorrect use of `serializer.asave(commit=False)`
        assert "commit" not in kwargs, (
            "'commit' is not a valid keyword argument to the 'asave()' method."
            " If you need to access data before committing to the database"
            " then inspect 'serializer.validated_data' instead. You can also"
            " pass additional keyword arguments to 'asave()' if you need to"
            " set extra attributes on the saved model instance. For example:"
            " 'serializer.asave(owner=request.user)'.'"
        )

        validated_data = [{**attrs, **kwargs} for attrs in self.validated_data]

        if self.instance is not None:
            self.instance = await self.aupdate(self.instance, validated_data)
            assert (
                self.instance is not None
            ), "`aupdate()` did not return an object instance."
        else:
            self.instance = await self.acreate(validated_data)
            assert (
                self.instance is not None
            ), "`acreate()` did not return an object instance."

        return self.instance

    async def aupdate(self, instance: Any, validated_data: Any) -> NoReturn:
        raise NotImplementedError(
            "Serializers with many=True do not support multiple update by "
            "default, only multiple create. For updates it is unclear how to "
            "deal with insertions and deletions. If you need to support "
            "multiple update, use a `ListSerializer` class and override "
            "`.aupdate()` so you can specify the behavior exactly."
        )

    @async_property
    async def adata(self):
        ret = await super().adata
        return ReturnList(ret, serializer=self)  # type: ignore  # djangorestframework-types-0.8.0 has wrong declarations

    async def acreate(self, validated_data: Any) -> List[Any]:
        if has_acreate(self.child):
            return [await self.child.acreate(attrs) for attrs in validated_data]
        else:
            return [
                await sync_to_async(cast(DRFBaseSerializer, self.child).create)(attrs)
                for attrs in validated_data
            ]


class ModelSerializer(Serializer, DRFModelSerializer):
    async def acreate(self, validated_data: Any):
        """
        Create and return a new `Snippet` instance, given the validated data.
        """
        raise_errors_on_nested_writes("acreate", self, validated_data)

        ModelClass = self.Meta.model

        info = model_meta.get_field_info(ModelClass)
        many_to_many = {}
        for field_name, relation_info in info.relations.items():
            if relation_info.to_many and (field_name in validated_data):
                many_to_many[field_name] = validated_data.pop(field_name)

        try:
            instance = await ModelClass._default_manager.acreate(**validated_data)
        except TypeError:
            tb = traceback.format_exc()
            msg = (
                "Got a `TypeError` when calling `%s.%s.create()`. "
                "This may be because you have a writable field on the "
                "serializer class that is not a valid argument to "
                "`%s.%s.create()`. You may need to make the field "
                "read-only, or override the %s.create() method to handle "
                "this correctly.\nOriginal exception was:\n %s"
                % (
                    ModelClass.__name__,
                    ModelClass._default_manager.name,
                    ModelClass.__name__,
                    ModelClass._default_manager.name,
                    self.__class__.__name__,
                    tb,
                )
            )
            raise TypeError(msg)

        if many_to_many:
            for field_name, value in many_to_many.items():
                field = getattr(instance, field_name)
                field.set(value)

        return instance

    async def aupdate(self, instance: Any, validated_data: Any):
        raise_errors_on_nested_writes("aupdate", self, validated_data)
        info = model_meta.get_field_info(instance)

        # Simply set each attribute on the instance, and then asave it.
        # Note that unlike `.create()` we don't need to treat many-to-many
        # relationships as being a special case. During updates we already
        # have an instance pk for the relationships to be associated with.
        m2m_fields = []
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                m2m_fields.append((attr, value))
            else:
                setattr(instance, attr, value)

        await instance.asave()

        # Note that many-to-many fields are set after updating instance.
        # Setting m2m fields triggers signals which could potentially change
        # updated instance and we do not want it to collide with .update()
        for attr, value in m2m_fields:
            field = getattr(instance, attr)
            field.set(value)

        return instance
