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
    TypeGuard,
    cast,
)

from asgiref.sync import sync_to_async
from async_property import async_property
from async_property.base import AsyncPropertyDescriptor
from django.db import models
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)

from rest_framework.fields import (  # NOQA # isort:skip
    Field,
    SkipField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    EmailField,
    FileField,
    FilePathField,
    FloatField,
    HStoreField,
    ImageField,
    IntegerField,
    IPAddressField,
    JSONField,
    # ListField,
    ModelField,
    SlugField,
    TimeField,
    URLField,
    UUIDField,
)
from rest_framework.relations import (
    HyperlinkedIdentityField,
    PrimaryKeyRelatedField,
    RelatedField,
)

# SlugRelatedField,
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

# NOTE This is the list of fields defined by DRF known to be free from
# SynchronousOnlyOperation when accessed as django Model instance attributes.

# In the original implementation of adrf, there is a list, named 'DRF_FIELDS',
# generated from DRFModelSerializer.serializer_field_mappings and some class variables
# of DRFModelSerializer to know the non-existence of `ato_representation`, we cannot
# use the same approach here because the mappings or variables can be modified by user
# and user can specify Fields that requires SynchronousOnlyOperation.
SOOP_FREE_DRF_FIELDS = set(
    [
        BooleanField,
        CharField,
        DateField,
        DateTimeField,
        DecimalField,
        DurationField,
        EmailField,
        FileField,
        FilePathField,
        FloatField,
        HStoreField,
        ImageField,
        IntegerField,
        IPAddressField,
        JSONField,
        # ListField,  # ListField is not safe in general.  child.to_representation() can use SynchronousOnlyOperation.
        ModelField,
        SlugField,
        TimeField,
        URLField,
        UUIDField,
        PrimaryKeyRelatedField,
        HyperlinkedIdentityField,
        # SlugRelatedField,  # SlugRelatedField is not safe in general.  slug_field can have multiple '__'s.
    ]
)


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


async def get_model_field_value(
    instance: models.Model, field: Field[Any, Any, Any, Any]
):
    if isinstance(field, RelatedField) and field.use_pk_only_optimization():
        return field.get_attribute(instance)

    descriptor = getattr(instance.__class__, field.source)
    if not hasattr(descriptor, "is_cached") or descriptor.is_cached(instance):
        return field.get_attribute(instance)

    if isinstance(descriptor, ForwardManyToOneDescriptor):
        # ForwardOneToOneDescriptor also comes here.
        if None not in descriptor.field.get_local_related_value(instance):  # type: ignore  # django-types-0.19.1 lacks declarations
            # MEMO: (asynchronized) partial inline copy of
            # django.db.models.fields.related_descriptors.ForwardManyToOneDescriptor.__get__()

            # Since qs.aget() called below is still implemented with sync_to_async() in django-5.0.7,
            # this can be so expensive that cons eat up pros of 'async'.
            instance_field_class = getattr(instance.__class__, field.source)
            qs = instance_field_class.get_queryset(instance=instance)
            try:
                val = await qs.aget(
                    instance_field_class.field.get_reverse_related_filter(instance)
                )
                setattr(instance, field.source, val)
                return val
            except descriptor.RelatedObjectDoesNotExist:
                raise
        else:
            if descriptor.field.null:
                return None
            raise descriptor.RelatedObjectDoesNotExist(
                "%s has no %s."
                % (descriptor.field.model.__name__, descriptor.field.name)
            )

    if isinstance(descriptor, ReverseOneToOneDescriptor):
        # MEMO: (asynchronized) partial inline copy of
        # django.db.models.fields.related_descriptors.ReverseOneToOneDescriptor.__get__()
        related_pk = instance.pk
        if related_pk is None:
            rel_obj = None
        else:
            filter_args = descriptor.related.field.get_forward_related_filter(instance)
            try:
                rel_obj = await descriptor.get_queryset(instance=instance).aget(
                    **filter_args
                )
            except descriptor.related.related_model.DoesNotExist:
                rel_obj = None
            else:
                descriptor.related.field.set_cached_value(rel_obj, instance)
        descriptor.related.set_cached_value(instance, rel_obj)
        if rel_obj is None:
            raise descriptor.RelatedObjectDoesNotExist(
                "%s has no %s."
                % (instance.__class__.__name__, descriptor.related.get_accessor_name())
            )
        return rel_obj

    # Should treat user defined descriptors that manipulate DBs here?
    if isinstance(descriptor, ReverseManyToOneDescriptor):
        # ManyToManyDescriptor also comes here because it is a child of
        # ReverseManyToOneDescriptor.
        # Since these descriptors return a Manager for every single call,
        # it does not raise SynchronousOnlyOperation here.
        return field.get_attribute(instance)

    # For unknown possibly user defined descriptors.
    # They may require SynchronousOnlyOperation.
    return await sync_to_async(field.get_attribute)(instance)


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
        is_model_instance = isinstance(instance, models.Model)

        for field in fields:
            try:
                # attribute = field.get_attribute(instance)
                attribute = (
                    await get_model_field_value(instance, field)
                    if is_model_instance
                    else field.get_attribute(instance)
                )
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
