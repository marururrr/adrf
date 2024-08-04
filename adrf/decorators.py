import asyncio
import types
from typing import Any, Callable, Optional, Sequence, Type, TypeVar

from django.http.response import HttpResponseBase
from rest_framework.authentication import BaseAuthentication

from adrf.views import APIView

_CallableViewHandler = Callable[..., HttpResponseBase]
_F = TypeVar("_F", bound=_CallableViewHandler)

_AuthClassesParam = Sequence[Type[BaseAuthentication]]


def api_view(http_method_names: Optional[Sequence[str]] = None):
    """
    Decorator that converts a function-based view into an APIView subclass.
    Takes a list of allowed methods for the view as an argument.
    """
    http_method_names = ["GET"] if (http_method_names is None) else http_method_names

    def decorator(func: Callable[..., Any]):
        WrappedAPIView = type("WrappedAPIView", (APIView,), {"__doc__": func.__doc__})

        # Note, the above allows us to set the docstring.
        # It is the equivalent of:
        #
        #     class WrappedAPIView(APIView):
        #         pass
        #     WrappedAPIView.__doc__ = func.doc    <--- Not possible to do this

        # api_view applied without (method_names)
        assert not (
            isinstance(http_method_names, types.FunctionType)
        ), "@api_view missing list of allowed HTTP methods"

        # api_view applied with eg. string instead of list of strings
        assert isinstance(http_method_names, (list, tuple)), (
            "@api_view expected a list of strings, received %s"
            % type(http_method_names).__name__
        )

        allowed_methods = set(http_method_names) | {"options"}
        WrappedAPIView.http_method_names = [
            method.lower() for method in allowed_methods
        ]

        view_is_async = asyncio.iscoroutinefunction(func)

        if view_is_async:

            async def handler(_, *args: Any, **kwargs: Any):  # type: ignore
                return await func(*args, **kwargs)

        else:

            def handler(_, *args: Any, **kwargs: Any):
                return func(*args, **kwargs)

        for method in http_method_names:
            setattr(WrappedAPIView, method.lower(), handler)

        WrappedAPIView.__name__ = func.__name__
        WrappedAPIView.__module__ = func.__module__

        WrappedAPIView.renderer_classes = getattr(
            func, "renderer_classes", APIView.renderer_classes
        )

        WrappedAPIView.parser_classes = getattr(
            func, "parser_classes", APIView.parser_classes
        )

        WrappedAPIView.authentication_classes = getattr(
            func, "authentication_classes", APIView.authentication_classes
        )

        WrappedAPIView.throttle_classes = getattr(
            func, "throttle_classes", APIView.throttle_classes
        )

        WrappedAPIView.permission_classes = getattr(
            func, "permission_classes", APIView.permission_classes
        )

        WrappedAPIView.schema = getattr(func, "schema", APIView.schema)

        return WrappedAPIView.as_view()

    return decorator
