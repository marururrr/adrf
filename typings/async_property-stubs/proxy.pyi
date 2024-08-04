"""
This type stub file was generated by pyright.
"""

from collections.abc import Iterator, Generator
from typing import Any, Dict, List, NoReturn, Optional, Tuple

class AwaitableOnly:
    """This wraps a coroutine will call it on await."""
    def __init__(self, coro: Any) -> None:
        ...

    def __repr__(self) -> str:
        ...

    def __await__(self) -> Any:
        ...

    __slots__ = ...


class _ObjectProxyMethods:
    @property
    def __module__(self) -> str | None:
        ...

    @__module__.setter
    def __module__(self, value: Optional[str]) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        ...

    @property
    def __doc__(self) -> str | None:
        ...

    @__doc__.setter
    def __doc__(self, value: Optional[str]) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        ...

    @property
    def __dict__(self) -> Dict[str, Any]:  # pyright: ignore[reportIncompatibleVariableOverride]
        ...

    @property
    def __weakref__(self) -> Any:
        ...



class _ObjectProxyMetaType(type):
    def __new__(cls, name: str, bases: Tuple[Any], dictionary: Dict[str, Any]) -> Any:
        ...



class ObjectProxy(metaclass=_ObjectProxyMetaType):
    __slots__ = ...
    def __init__(self, wrapped: Any) -> None:
        ...

    @property
    def __name__(self) -> Any:
        ...

    @__name__.setter
    def __name__(self, value: Any) -> None:
        ...

    @property
    def __class__(self) -> Any:
        ...

    @__class__.setter
    def __class__(self, value: Any) -> None:
        ...

    @property
    def __annotations__(self) -> Any:
        ...

    @__annotations__.setter
    def __annotations__(self, value: Any) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        ...

    def __dir__(self) -> List[str]:
        ...

    def __str__(self) -> str:
        ...

    def __bytes__(self) -> bytes:
        ...

    def __repr__(self) -> str:
        ...

    def __reversed__(self) -> Iterator[Any]:
        ...

    def __round__(self) -> Any:
        ...

    def __lt__(self, other: Any) -> bool:
        ...

    def __le__(self, other: Any) -> bool:
        ...

    def __eq__(self, other: Any) -> bool:
        ...

    def __ne__(self, other: Any) -> bool:
        ...

    def __gt__(self, other: Any) -> bool:
        ...

    def __ge__(self, other: Any) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    def __bool__(self) -> bool:
        ...

    def __setattr__(self, name: str, value: Any) -> None:
        ...

    def __getattr__(self, name: str) -> Any:
        ...

    def __delattr__(self, name: str) -> None:
        ...

    def __add__(self, other: Any) -> Any:
        ...

    def __sub__(self, other: Any) -> Any:
        ...

    def __mul__(self, other: Any) -> Any:
        ...

    def __truediv__(self, other: Any) -> Any:
        ...

    def __floordiv__(self, other: Any) -> Any:
        ...

    def __mod__(self, other: Any) -> Any:
        ...

    def __divmod__(self, other: Any) -> Any:
        ...

    def __pow__(self, other: Any, *args: Any) -> Any:
        ...

    def __lshift__(self, other: Any) -> Any:
        ...

    def __rshift__(self, other: Any) -> Any:
        ...

    def __and__(self, other: Any) -> Any:
        ...

    def __xor__(self, other: Any) -> Any:
        ...

    def __or__(self, other: Any) -> Any:
        ...

    def __radd__(self, other: Any) -> Any:
        ...

    def __rsub__(self, other: Any) -> Any:
        ...

    def __rmul__(self, other: Any) -> Any:
        ...

    def __rtruediv__(self, other: Any) -> Any:
        ...

    def __rfloordiv__(self, other: Any) -> Any:
        ...

    def __rmod__(self, other: Any) -> Any:
        ...

    def __rdivmod__(self, other: Any) -> Any:
        ...

    def __rpow__(self, other: Any, *args: Any) -> Any:
        ...

    def __rlshift__(self, other: Any) -> Any:
        ...

    def __rrshift__(self, other: Any) -> Any:
        ...

    def __rand__(self, other: Any) -> Any:
        ...

    def __rxor__(self, other: Any) -> Any:
        ...

    def __ror__(self, other: Any) -> Any:
        ...

    def __iadd__(self, other: Any) -> ObjectProxy:
        ...

    def __isub__(self, other: Any) -> ObjectProxy:
        ...

    def __imul__(self, other: Any) -> ObjectProxy:
        ...

    def __itruediv__(self, other: Any) -> ObjectProxy:
        ...

    def __ifloordiv__(self, other: Any) -> ObjectProxy:
        ...

    def __imod__(self, other: Any) -> ObjectProxy:
        ...

    def __ipow__(self, other: Any) -> ObjectProxy:
        ...

    def __ilshift__(self, other: Any) -> ObjectProxy:
        ...

    def __irshift__(self, other: Any) -> ObjectProxy:
        ...

    def __iand__(self, other: Any) -> ObjectProxy:
        ...

    def __ixor__(self, other: Any) -> ObjectProxy:
        ...

    def __ior__(self, other: Any) -> ObjectProxy:
        ...

    def __neg__(self) -> Any:
        ...

    def __pos__(self) -> Any:
        ...

    def __abs__(self) -> Any:
        ...

    def __invert__(self) -> Any:
        ...

    def __int__(self) -> int:
        ...

    def __float__(self) -> float:
        ...

    def __complex__(self) -> complex:
        ...

    def __oct__(self) -> str:
        ...

    def __hex__(self) -> str:
        ...

    def __index__(self) -> int:
        ...

    def __len__(self) -> int:
        ...

    def __contains__(self, value: Any) -> bool:
        ...

    def __getitem__(self, key: str) -> Any:
        ...

    def __setitem__(self, key: str, value: Any) -> None:
        ...

    def __delitem__(self, key: str) -> None:
        ...

    def __getslice__(self, i: int, j: int) -> Any:
        ...

    def __setslice__(self, i: int, j: int, value: Any) -> None:
        ...

    def __delslice__(self, i: int, j: int) -> None:
        ...

    def __enter__(self) -> Any:
        ...

    def __exit__(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def __iter__(self) -> Any:
        ...

    def __copy__(self) -> NoReturn:
        ...

    def __deepcopy__(self, memo: Any) -> NoReturn:
        ...

    def __reduce__(self) -> NoReturn:
        ...

    def __reduce_ex__(self, protocol: Any) -> NoReturn:
        ...

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ...



class AwaitableProxy(ObjectProxy):
    def __await__(self) -> Generator[Any, Any, Any]:
        ...

    async def __aenter__(self) -> Any:
        ...

    async def __aexit__(self, *args: Any, **kwargs: Any) -> Any:
        ...

    async def __aiter__(self) -> Any:
        ...

    async def __anext__(self) -> Any:
        ...
