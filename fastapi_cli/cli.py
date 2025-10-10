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
    tool = _detect_tool(normalized)

    if tool is None:
        script_name = str(sys.argv[0]).lower()
        for candidate in _KNOWN_TOOLS:
            if candidate in script_name:
                tool = candidate
                break

    if tool is None:
        message = (
            "fastapi_cli stub cannot determine the requested command. "
            "Install fastapi[standard] for the full CLI experience."
        )
        raise SystemExit(message)

    args = _remaining_args(normalized, tool)

    if tool == "pyright":
        exit_code = _run_pyright(args)
    else:
        exit_code = _run_python_tool(tool, args)

    if isinstance(exit_code, int) and exit_code != 0:
        raise SystemExit(exit_code)


def _run_python_tool(tool: str, args: list[str]) -> int | None:
    module_name, attr_name = _PYTHON_DISPATCH[tool]
    module: ModuleType = importlib.import_module(module_name)
    entrypoint_obj = cast("object | None", getattr(module, attr_name, None))

    if not callable(entrypoint_obj):
        message = (
            f"fastapi_cli stub cannot locate callable '{attr_name}' in {module_name}"
        )
        raise SystemExit(message)

    callable_entrypoint = cast("_Entrypoint", entrypoint_obj)
    sys.argv = [tool, *args]
    result = callable_entrypoint()
    if isinstance(result, int):
        return result
    return None


def _run_pyright(args: list[str]) -> int:
    node_command = _pyright_command()
    command = [*node_command, *args]
    completed = subprocess.run(command, check=False)
    return completed.returncode


def _pyright_command() -> list[str]:
    try:
        import nodejs  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - defensive guard
        message = (
            "pyright CLI backend requires the 'nodejs-bin' package. "
            "Install it with 'pip install nodejs-bin' and rerun the command."
        )
        raise SystemExit(message) from exc

    module_file = getattr(nodejs, "__file__", None)
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
