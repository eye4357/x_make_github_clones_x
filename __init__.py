"""x_make_github_clones_x package."""

from __future__ import annotations

# Re-export public surface for convenient imports.
from x_make_github_clones_x.x_cls_make_github_clones_x import (
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
