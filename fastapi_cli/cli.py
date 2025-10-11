from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType


class _Entrypoint(Protocol):
    def __call__(self) -> int | None: ...


_PYTHON_DISPATCH: dict[str, tuple[str, str]] = {
    "mypy": ("mypy.main", "main"),
}

_KNOWN_TOOLS = frozenset((*_PYTHON_DISPATCH.keys(), "pyright"))


def _normalize_args(argv: Sequence[str] | None) -> list[str]:
    if argv is not None:
        return [str(arg) for arg in argv]
    return [str(arg) for arg in sys.argv[1:]]


def _detect_tool(argv: Sequence[str]) -> str | None:
    for raw in argv:
        candidate = raw.lower()
        if candidate in _KNOWN_TOOLS:
            return candidate
        for name in _KNOWN_TOOLS:
            if name in candidate:
                return name
    return None


def _remaining_args(argv: list[str], tool: str) -> list[str]:
    try:
        index = next(i for i, arg in enumerate(argv) if arg.lower() == tool)
    except StopIteration:
        return argv
    return argv[index + 1 :]


def main(argv: Sequence[str] | None = None) -> None:
    normalized = _normalize_args(argv)
    tool = _resolve_tool(normalized, script_hint=str(sys.argv[0]))

    if tool is None:
        raise SystemExit(_unknown_tool_message())

    exit_code = _invoke_tool(tool, _remaining_args(normalized, tool))
    if isinstance(exit_code, int) and exit_code != 0:
        raise SystemExit(exit_code)


def _resolve_tool(argv: Sequence[str], *, script_hint: str) -> str | None:
    detected = _detect_tool(argv)
    if detected is not None:
        return detected

    script_name = script_hint.lower()
    for candidate in _KNOWN_TOOLS:
        if candidate in script_name:
            return candidate
    return None


def _unknown_tool_message() -> str:
    return (
        "fastapi_cli stub cannot determine the requested command. "
        "Install fastapi[standard] for the full CLI experience."
    )


def _invoke_tool(tool: str, args: list[str]) -> int | None:
    if tool == "pyright":
        return _run_pyright(args)
    return _run_python_tool(tool, args)


def _run_python_tool(tool: str, args: list[str]) -> int | None:
    dispatch_entry = _PYTHON_DISPATCH.get(tool)
    if dispatch_entry is None:
        message = f"Unsupported tooling request: {tool}"
        raise SystemExit(message)

    module_name, attr_name = dispatch_entry
    module: ModuleType = importlib.import_module(module_name)
    entrypoint_obj: object | None = getattr(module, attr_name, None)

    if entrypoint_obj is None:
        message = (
            f"fastapi_cli stub cannot locate callable '{attr_name}' in {module_name}"
        )
        raise SystemExit(message)

    if callable(entrypoint_obj):
        callable_entrypoint = cast("_Entrypoint", entrypoint_obj)
    else:
        message = (
            f"fastapi_cli stub cannot locate callable '{attr_name}' in {module_name}"
        )
        raise SystemExit(message)
    sys.argv = [tool, *args]
    result = callable_entrypoint()
    if not isinstance(result, int):
        return None
    return result


def _run_pyright(args: list[str]) -> int:
    node_command = _pyright_command()
    command = [*node_command, *args]
    completed = subprocess.run(command, check=False)  # noqa: S603
    return completed.returncode


def _pyright_command() -> list[str]:
    try:
        nodejs = importlib.import_module("nodejs")
    except ImportError as exc:  # pragma: no cover - defensive guard
        message = (
            "pyright CLI backend requires the 'nodejs-bin' package. "
            "Install it with 'pip install nodejs-bin' and rerun the command."
        )
        raise SystemExit(message) from exc

    module_file: str | None = getattr(nodejs, "__file__", None)
    if module_file is None:
        message = (
            "Unable to determine installation path for the 'nodejs' package. "
            "Reinstall 'nodejs-bin' and try again."
        )
        raise SystemExit(message)

    base_dir = Path(module_file).resolve().parent
    node_exe = _resolve_node_executable(base_dir)
    pyright_entry = _resolve_pyright_entrypoint(base_dir)
    return [str(node_exe), str(pyright_entry)]


def _resolve_node_executable(base_dir: Path) -> Path:
    node_exe = base_dir / "node.exe"
    if node_exe.exists():
        return node_exe

    fallback = shutil.which("node")
    if fallback is not None:
        return Path(fallback)

    message = (
        "Unable to locate a Node.js runtime. Install the 'nodejs-bin' Python package "
        "or add Node.js to your PATH."
    )
    raise SystemExit(message)


def _resolve_pyright_entrypoint(base_dir: Path) -> Path:
    candidate = base_dir / "node_modules" / "pyright" / "index.js"
    if candidate.exists():
        return candidate

    message = (
        "Node-based pyright CLI is missing. Install it with "
        "'python -m nodejs.npm install -g pyright'."
    )
    raise SystemExit(message)


if __name__ == "__main__":
    main()
