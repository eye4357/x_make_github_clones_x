from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi_cli.cli import main as dispatch_main

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> None:
    dispatch_main(argv)
