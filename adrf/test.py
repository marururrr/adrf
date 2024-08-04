from collections.abc import Sequence
from typing import Any, Dict, Optional, Type, cast

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.core.handlers.asgi import ASGIRequest
from django.http import HttpResponse
from django.test.client import (  # django-types-0.19.1 lacks these stubs
    AsyncClient as DjangoAsyncClient,  # type: ignore
)
from django.test.client import (
    AsyncClientHandler,  # type: ignore
)
from django.test.client import (
    AsyncRequestFactory as DjangoAsyncRequestFactory,  # type: ignore
)
from django.utils.encoding import force_bytes
from django.utils.http import urlencode
from rest_framework.renderers import BaseRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.test import force_authenticate


class AsyncForceAuthClientHandler(AsyncClientHandler):  # type: ignore
    """
    A patched version of ClientHandler that can enforce authentication
    on the outgoing requests.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        self._force_user = None
        self._force_token = None
        super().__init__(*args, **kwargs)  # type: ignore

    def get_response(self, request: Request) -> HttpResponse:
        # This is the simplest place we can hook into to patch the
        # request object.
        force_authenticate(request, self._force_user, self._force_token)
        return super().get_response(request)  # type: ignore


class AsyncAPIRequestFactory(DjangoAsyncRequestFactory):  # type: ignore
    renderer_classes_list = (
        cast(  # djangorestframework-types-0.8.0 has wrong declarationss
            Sequence[type], api_settings.TEST_REQUEST_RENDERER_CLASSES
        )
    )
    default_format = api_settings.TEST_REQUEST_DEFAULT_FORMAT

    def __init__(self, enforce_csrf_checks: bool = False, **defaults: Any):
        self.enforce_csrf_checks = enforce_csrf_checks
        self.renderer_classes: Dict[str, Type[BaseRenderer]] = {}
        for cls in self.renderer_classes_list:
            assert issubclass(cls, BaseRenderer)
            self.renderer_classes[cls.format] = cls
        super().__init__(**defaults)  # type: ignore

    def _encode_data(
        self,
        data: Any,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
    ):
        """
        Encode the data returning a two tuple of (bytes, content_type)
        """

        if data is None:
            return ("", content_type)

        assert (
            format is None or content_type is None
        ), "You may not set both `format` and `content_type`."

        if content_type:
            # Content type specified explicitly, treat data as a raw bytestring
            ret = force_bytes(data, settings.DEFAULT_CHARSET)

        else:
            format = format or self.default_format

            assert format in self.renderer_classes, (
                "Invalid format '{}'. Available formats are {}. "
                "Set TEST_REQUEST_RENDERER_CLASSES to enable "
                "extra request formats.".format(
                    format,
                    ", ".join(["'" + fmt + "'" for fmt in self.renderer_classes]),
                )
            )

            # Use format and render the data into a bytestring
            renderer = self.renderer_classes[format]()
            ret = renderer.render(data)

            # Determine the content-type header from the renderer
            content_type = renderer.media_type
            if renderer.charset:
                content_type = "{}; charset={}".format(content_type, renderer.charset)

            # Coerce text to bytes if required.
            if isinstance(ret, str):
                ret = ret.encode(renderer.charset or "utf-8")

        return ret, content_type

    def get(self, path: str, data: Optional[Dict[str, Any]] = None, **extra: Any):
        r: Dict[str, Any] = {
            "QUERY_STRING": urlencode(data or {}, doseq=True),
        }
        if not data and "?" in path:
            # Fix to support old behavior where you have the arguments in the
            # url. See #1461.
            query_string = force_bytes(path.split("?")[1])
            query_string = query_string.decode("iso-8859-1")
            r["QUERY_STRING"] = query_string
        r.update(extra)
        return self.generic("GET", path, **r)

    def post(
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ):
        data, content_type = self._encode_data(data, format, content_type)
        return self.generic("POST", path, data, content_type, **extra)

    def put(
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ):
        data, content_type = self._encode_data(data, format, content_type)
        return self.generic("PUT", path, data, content_type, **extra)

    def patch(
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ):
        data, content_type = self._encode_data(data, format, content_type)
        return self.generic("PATCH", path, data, content_type, **extra)

    def delete(
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ):
        data, content_type = self._encode_data(data, format, content_type)
        return self.generic("DELETE", path, data, content_type, **extra)

    def options(
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ):
        data, content_type = self._encode_data(data, format, content_type)
        return self.generic("OPTIONS", path, data, content_type, **extra)

    def generic(
        self,
        method: str,
        path: str,
        data: Any = "",
        content_type: Optional[str] = "application/octet-stream",
        secure: bool = False,
        **extra: Any,
    ) -> ASGIRequest:
        # Include the CONTENT_TYPE, regardless of whether or not data is empty.
        if content_type is not None:
            extra["CONTENT_TYPE"] = str(content_type)

        return super().generic(method, path, data, content_type, secure, **extra)  # type: ignore

    def request(self, **kwargs: Any):
        request = super().request(**kwargs)  # type: ignore
        request._dont_enforce_csrf_checks = not self.enforce_csrf_checks
        return cast(ASGIRequest, request)


class AsyncAPIClient(DjangoAsyncClient, AsyncAPIRequestFactory):  # type: ignore
    """
    An async version of APIClient that creates ASGIRequests and calls through an
    async request path.

    Does not currently support "follow" on its methods.
    """

    def __init__(self, enforce_csrf_checks: bool = False, **defaults: Any):
        super().__init__(**defaults)  # type: ignore
        self.handler = AsyncForceAuthClientHandler(enforce_csrf_checks)
        self._credentials = {}

    def credentials(self, **kwargs: Any):
        """
        Sets headers that will be used on every outgoing request.
        """
        self._credentials = kwargs

    def force_authenticate(
        self, user: Optional[AbstractBaseUser] = None, token: Optional[str] = None
    ):
        """
        Forcibly authenticates outgoing requests with the given
        user and/or token.
        """
        self.handler._force_user = user  # type: ignore
        self.handler._force_token = token  # type: ignore
        if user is None and token is None:
            self.logout()  # Also clear any possible session info if required

    async def request(self, **kwargs: Any) -> HttpResponse:  # type: ignore
        # Ensure that any credentials set get added to every request.
        kwargs.update(self._credentials)
        return await super().request(**kwargs)  # type: ignore

    async def get(  # type: ignore
        self, path: str, data: Optional[Any] = None, **extra: Any
    ) -> Response:
        return await super().get(path, data=data, **extra)  # type: ignore

    async def post(  # type: ignore
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ) -> Response:
        return await super().post(  # type: ignore
            path,
            data=data,
            format=format,
            content_type=content_type,
            **extra,
        )

    async def put(  # type: ignore
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ) -> Response:
        return await super().put(  # type: ignore
            path, data=data, format=format, content_type=content_type, **extra
        )

    async def patch(  # type: ignore
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ) -> Response:
        return await super().patch(  # type: ignore
            path, data=data, format=format, content_type=content_type, **extra
        )

    async def delete(  # type: ignore
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ) -> Response:
        return await super().delete(  # type: ignore
            path, data=data, format=format, content_type=content_type, **extra
        )

    async def options(  # type: ignore
        self,
        path: str,
        data: Optional[Any] = None,
        format: Optional[str] = None,
        content_type: Optional[str] = None,
        **extra: Any,
    ) -> Response:
        return await super().options(  # type: ignore
            path, data=data, format=format, content_type=content_type, **extra
        )

    def logout(self):
        self._credentials = {}

        # Also clear any `force_authenticate`
        self.handler._force_user = None  # type: ignore
        self.handler._force_token = None  # type: ignore

        if getattr(self, "session", None):
            super().logout()  # type: ignore
