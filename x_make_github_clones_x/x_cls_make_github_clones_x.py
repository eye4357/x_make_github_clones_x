"""Expose the CLI implementation from the script module."""

from ..x_cls_make_github_clones_x import (
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
