"""Minimal stub of ``fastapi`` for local tooling.

The project relies on a tiny portion of FastAPI's surface area. This stub
provides no runtime behaviour beyond storing decorated callables; its purpose is
simply to satisfy type-checkers when the real dependency isn't available.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

_F = TypeVar("_F", bound=Callable[..., object])


@dataclass(slots=True)
class RouteDefinition:
    method: str
    path: str
    handler: Callable[..., object]
    options: dict[str, object]


class _RouteDecorator:
    def __init__(
        self,
        app: FastAPI,
        method: str,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> None:
        self._app = app
        self._method = method
        self._path = path
        options: dict[str, object] = dict(kwargs)
        if name is not None:
            options["name"] = name
        if tags is not None:
            options["tags"] = list(tags)
        self._options = options

    def __call__(self, func: _F) -> _F:
        self._app.routes.append(
            RouteDefinition(self._method, self._path, func, self._options.copy())
        )
        return func


class FastAPI:
    """Minimal FastAPI stub that records registered routes."""

    def __init__(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        version: str | None = None,
    ) -> None:
        self.title = title
        self.description = description
        self.version = version
        self.routes: list[RouteDefinition] = []

    def get(
        self,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> _RouteDecorator:
        return _RouteDecorator(self, "GET", path, name=name, tags=tags, **kwargs)

    def post(
        self,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> _RouteDecorator:
        return _RouteDecorator(self, "POST", path, name=name, tags=tags, **kwargs)

    def put(
        self,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> _RouteDecorator:
        return _RouteDecorator(self, "PUT", path, name=name, tags=tags, **kwargs)

    def delete(
        self,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> _RouteDecorator:
        return _RouteDecorator(self, "DELETE", path, name=name, tags=tags, **kwargs)

    def patch(
        self,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> _RouteDecorator:
        return _RouteDecorator(self, "PATCH", path, name=name, tags=tags, **kwargs)

    def websocket(
        self,
        path: str,
        *,
        name: str | None = None,
        tags: Sequence[str] | None = None,
        **kwargs: object,
    ) -> _RouteDecorator:
        return _RouteDecorator(self, "WEBSOCKET", path, name=name, tags=tags, **kwargs)


__all__ = ["FastAPI"]
