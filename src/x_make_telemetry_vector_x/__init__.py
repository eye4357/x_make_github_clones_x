"""Compatibility shim for the relocated telemetry package.

This module simply re-exports the canonical implementation living at
`x_make_telemetry_vector_x` in the workspace root. Keeping the shim in place
avoids breaking callers immediately while the workspace migration completes.
"""

from __future__ import annotations

from x_make_telemetry_vector_x import *  # noqa: F403
