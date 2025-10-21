"""Compatibility wrapper for JSON contracts module."""

from __future__ import annotations

from importlib import import_module

_IMPL = import_module("x_make_github_clones_x._json_contracts_impl")

ERROR_SCHEMA = _IMPL.ERROR_SCHEMA
INPUT_SCHEMA = _IMPL.INPUT_SCHEMA
OUTPUT_SCHEMA = _IMPL.OUTPUT_SCHEMA

__all__ = ["ERROR_SCHEMA", "INPUT_SCHEMA", "OUTPUT_SCHEMA"]
