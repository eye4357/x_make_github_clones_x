"""Expose the CLI implementation from the script module with lazy runtime imports.

This avoids mypy import-cycle confusion by importing for types only under
TYPE_CHECKING and assigning real objects via importlib at runtime.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # static type checkers see precise symbols
    from x_make_github_clones_x.x_cls_make_github_clones_x import (
        RepoRecord as RepoRecord,
    )
    from x_make_github_clones_x.x_cls_make_github_clones_x import main_json as main_json
    from x_make_github_clones_x.x_cls_make_github_clones_x import (
        resolve_workspace_root as resolve_workspace_root,
    )
    from x_make_github_clones_x.x_cls_make_github_clones_x import (
        synchronize_workspace as synchronize_workspace,
    )
    from x_make_github_clones_x.x_cls_make_github_clones_x import (
        x_cls_make_github_clones_x as x_cls_make_github_clones_x,
    )


def _load_runtime_symbols() -> None:
    impl = import_module("x_make_github_clones_x.x_cls_make_github_clones_x")
    globals()["RepoRecord"] = impl.RepoRecord
    globals()["main_json"] = impl.main_json
    globals()["resolve_workspace_root"] = impl.resolve_workspace_root
    globals()["synchronize_workspace"] = impl.synchronize_workspace
    globals()["x_cls_make_github_clones_x"] = impl.x_cls_make_github_clones_x


_load_runtime_symbols()

__all__ = [
    "RepoRecord",
    "main_json",
    "resolve_workspace_root",
    "synchronize_workspace",
    "x_cls_make_github_clones_x",
]
