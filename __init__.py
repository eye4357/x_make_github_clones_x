"""x_make_github_clones_x package."""

from __future__ import annotations

from .x_cls_make_github_clones_x import (  # re-export public surface
    RepoRecord,
    main_json,
    resolve_workspace_root,
    synchronize_workspace,
    x_cls_make_github_clones_x,
)

__all__ = [
    "RepoRecord",
    "main_json",
    "resolve_workspace_root",
    "synchronize_workspace",
    "x_cls_make_github_clones_x",
]
