"""JSON contracts exposed by x_make_github_clones_x."""

from __future__ import annotations

import sys as _sys

from ._impl import ERROR_SCHEMA, INPUT_SCHEMA, OUTPUT_SCHEMA

# Preserve legacy import path "json_contracts" for downstream tooling.
_sys.modules.setdefault("json_contracts", _sys.modules[__name__])

__all__ = ["ERROR_SCHEMA", "INPUT_SCHEMA", "OUTPUT_SCHEMA"]
