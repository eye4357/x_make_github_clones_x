from __future__ import annotations

from collections.abc import Callable, Sequence
from importlib import import_module
from typing import Protocol, cast

DispatchMain = Callable[[Sequence[str] | None], None]


def _load_dispatch_main() -> DispatchMain:
    class _CliModule(Protocol):
        main: DispatchMain

    try:
        module = cast("_CliModule", import_module("fastapi_cli.cli"))
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        message = "fastapi-cli is required to use this entrypoint"
        raise RuntimeError(message) from exc

    return module.main


def main(argv: Sequence[str] | None = None) -> None:
    dispatch_main = _load_dispatch_main()
    dispatch_main(argv)
