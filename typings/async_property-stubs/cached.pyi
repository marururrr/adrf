"""
This type stub file was generated by pyright.
"""
from typing import Any, Callable, overload

from .proxy import AwaitableOnly, AwaitableProxy

is_coroutine = ...
ASYNC_PROPERTY_ATTR = ...
def async_cached_property(func: Callable[[Any], Any], *args: Any, **kwargs: Any) -> AsyncCachedPropertyDescriptor:
    ...

class AsyncCachedPropertyInstanceState:
    def __init__(self) -> None:
        ...

    __slots__ = ...


class AsyncCachedPropertyDescriptor:
    def __init__(self, _fget: Callable[[Any], Any], _fset: Callable[[Any, Any], None]=..., _fdel: Callable[[Any], None]=..., field_name: str=...) -> None:
        ...

    def __set_name__(self, owner: Any, name: str) -> None:
        ...

    @overload
    def __get__(self, instance: None, owner: Any) -> AsyncCachedPropertyDescriptor:
        ...
    @overload
    def __get__(self, instance: object, owner: Any) -> AwaitableProxy | AwaitableOnly:
        ...

    def __set__(self, instance: Any, value: Any) -> None:
        ...

    def __delete__(self, instance: Any) -> None:
        ...

    def setter(self, method: Callable[[Any, Any], None]) -> AsyncCachedPropertyDescriptor:
        ...

    def deleter(self, method: Callable[[Any], None]) -> AsyncCachedPropertyDescriptor:
        ...

    def get_instance_state(self, instance: Any) -> Any:
        ...

    def get_lock(self, instance: Any) -> Any:
        ...

    def get_cache(self, instance: Any) -> Any:
        ...

    def has_cache_value(self, instance: Any) -> bool:
        ...

    def get_cache_value(self, instance: Any) -> Any:
        ...

    def set_cache_value(self, instance: Any, value: Any) -> None:
        ...

    def del_cache_value(self, instance: Any) -> None:
        ...

    def get_loader(self, instance: Any) -> Any:
        ...

    def already_loaded(self, instance: Any) -> AwaitableProxy:
        ...

    def not_loaded(self, instance: Any) -> AwaitableOnly:
        ...
