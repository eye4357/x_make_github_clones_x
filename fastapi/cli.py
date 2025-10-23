from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import import_module
from typing import Any, cast

DispatchMain = Callable[[Sequence[str] | None], None]


def _load_dispatch_main() -> DispatchMain:
    try:
        module = import_module("fastapi_cli.cli")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        message = "fastapi-cli is required to use this entrypoint"
        raise RuntimeError(message) from exc

    main_obj: Any = getattr(module, "main", None)
    if not callable(main_obj):
        message = "fastapi_cli.cli.main must be callable"
        raise TypeError(message)
    return cast("DispatchMain", main_obj)


def main(argv: Sequence[str] | None = None) -> None:
    dispatch_main = _load_dispatch_main()
    dispatch_main(argv)
