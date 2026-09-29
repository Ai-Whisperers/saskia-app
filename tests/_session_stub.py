"""Minimal Session class stub for compatibility with newer starlette versions."""
from typing import Any, Dict, Iterator, MutableMapping


class Session(MutableMapping[str, Any]):
    """Simple dict-like session object compatible with starlette.middleware.sessions.Session.

    In newer versions of starlette, the Session class was removed from
    starlette.middleware.sessions. This stub provides the same interface.
    """

    def __init__(self, initial: Dict[str, Any] = None) -> None:
        self._data: Dict[str, Any] = dict(initial) if initial else {}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"Session({self._data!r})"
