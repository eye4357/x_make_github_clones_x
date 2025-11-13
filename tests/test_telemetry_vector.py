# ruff: noqa: S101

from __future__ import annotations

import pytest


@pytest.mark.skip("Telemetry vector tests live in x_make_telemetry_vector_x")
def test_telemetry_vector_moved() -> None:
    assert True
