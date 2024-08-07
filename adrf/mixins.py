import asyncio
import warnings
from typing import Any, Dict, cast

from asgiref.sync import sync_to_async
from django.db.models import Model, QuerySet
from rest_framework import status
from rest_framework.generics import GenericAPIView as DRFGenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer as DRFBaseSerializer
from rest_framework.settings import api_settings

from adrf.serializers import (
    serializer_adata,
    serializer_ais_valid,
    serializer_asave,
)


class CreateModelMixin:
    """
    Create a model instance.
    """

    async def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = cast(DRFGenericAPIView, self).get_serializer(data=request.data)
        await sync_to_async(serializer.is_valid)(raise_exception=True)
        if asyncio.iscoroutinefunction(self.perform_create):
            await self.perform_create(serializer)
        else:
            if not getattr(self, "use_sync_perform_create", False):
                warnings.warn(
                    "Non async perform_create(): %s" % self.__class__.__name__,
                    PendingDeprecationWarning,
                )
            await sync_to_async(self.perform_create)(serializer)
        data = await serializer_adata(serializer)
        headers = self.get_success_headers(data)
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    async def perform_create(self, serializer: DRFBaseSerializer):
        await serializer_asave(serializer)

    def get_success_headers(self, data: Dict[str, Any]) -> Dict[str, str]:
        try:
            return {"Location": str(data[api_settings.URL_FIELD_NAME])}
        except (TypeError, KeyError):
            return {}


class ListModelMixin:
    """
    List a queryset.
    """

    async def list(self, *args: Any, **kwargs: Any) -> Response:
        from adrf.generics import GenericAPIView

        assert isinstance(self, GenericAPIView)
        queryset = self.filter_queryset(self.get_queryset())  # type: ignore  # why?

        page = await self.paginate_queryset(cast(QuerySet[Any], queryset))
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = await serializer_adata(serializer)
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = await serializer_adata(serializer)
        return Response(data, status=status.HTTP_200_OK)


class RetrieveModelMixin:
    """
    Retrieve a model instance.
    """

    async def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from adrf.generics import GenericAPIView

        assert isinstance(self, GenericAPIView)
        instance = await self.aget_object()
        serializer = self.get_serializer(instance, many=False)
        data = await serializer_adata(serializer)
        return Response(data, status=status.HTTP_200_OK)


class UpdateModelMixin:
    """
    Update a model instance.
    """

    async def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from adrf.generics import GenericAPIView

        assert isinstance(self, GenericAPIView)
        partial = kwargs.pop("partial", False)
        instance = await self.aget_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        await serializer_ais_valid(serializer, raise_exception=True)
        if asyncio.iscoroutinefunction(self.perform_update):
            await self.perform_update(serializer)
        else:
            if not getattr(self, "use_sync_perform_update", False):
                warnings.warn(
                    "Non async perform_update(): %s" % self.__class__.__name__,
                    PendingDeprecationWarning,
                )
            await sync_to_async(self.perform_update)(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        data = await serializer_adata(serializer)

        return Response(data, status=status.HTTP_200_OK)

    async def perform_update(self, serializer: DRFBaseSerializer):
        await serializer_asave(serializer)

    async def partial_update(
        self, request: Request, *args: Any, **kwargs: Any
    ) -> Response:
        kwargs["partial"] = True
        return await self.update(request, *args, **kwargs)


class DestroyModelMixin:
    """
    Destroy a model instance.
    """

    async def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from adrf.generics import GenericAPIView

        assert isinstance(self, GenericAPIView)
        instance = await self.aget_object()
        if asyncio.iscoroutinefunction(self.perform_destroy):
            await self.perform_destroy(instance)
        else:
            if not getattr(self, "use_sync_perform_destroy", False):
                warnings.warn(
                    "Non async perform_destroy(): %s" % self.__class__.__name__,
                    PendingDeprecationWarning,
                )
            await sync_to_async(self.perform_destroy)(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    async def perform_destroy(self, instance: Model):
        await instance.adelete()
