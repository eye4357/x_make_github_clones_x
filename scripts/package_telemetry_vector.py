"""Compatibility wrapper for relocated telemetry packaging script."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    root_repo = Path(__file__).resolve().parents[2] / "x_make_telemetry_vector_x"
    script = root_repo / "scripts" / "package_telemetry_vector.py"
    message = (
        "Telemetry packaging moved to 'x_make_telemetry_vector_x'. "
        "Invoke the script via"
        f" {script}"
    )
    raise SystemExit(message)


if __name__ == "__main__":
    main()
