"""Expose the CLI implementation from the top-level script with typed re-exports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # make precise types visible to static analyzers
    from x_cls_make_github_clones_x import (
        RepoRecord,
        main_json,
        resolve_workspace_root,
        synchronize_workspace,
        x_cls_make_github_clones_x,
    )
else:  # keep runtime dependencies lazy
    impl = import_module("x_cls_make_github_clones_x")
    RepoRecord = impl.RepoRecord
    main_json = impl.main_json
    resolve_workspace_root = impl.resolve_workspace_root
    synchronize_workspace = impl.synchronize_workspace
    x_cls_make_github_clones_x = impl.x_cls_make_github_clones_x

__all__ = [
    "RepoRecord",
    "main_json",
    "resolve_workspace_root",
    "synchronize_workspace",
    "x_cls_make_github_clones_x",
]
