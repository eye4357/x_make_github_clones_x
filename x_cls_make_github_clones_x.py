#!/usr/bin/env python3
"""
Merged cloner and bootstrap utility for GitHub repos.

Features:
- Clone whitelisted repositories for a GitHub user into a target directory.
- Clone if missing, otherwise update via git pull.
- Optionally create or overwrite common repo tooling files (pre-commit, pyproject,
  CI workflows) to bootstrapp developer workflows.
- Contains legacy snapshot/restore helpers kept for compatibility.

These scaffolding files help enforce formatting, linting, and type checks
across environments (ruff, black, mypy) and enable pre-commit and CI checks.

Important: review this script before running destructive operations. It will
only perform dangerous actions when the user explicitly opts in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, ClassVar, cast

from tools import templates
from typing import Optional

# Local no-op logging shim (logging removed)
class _NoopLogger:
    def debug(self, *a: object, **k: object) -> None:
        return None

    def info(self, *a: object, **k: object) -> None:
        return None

    def warning(self, *a: object, **k: object) -> None:
        return None

    def error(self, *a: object, **k: object) -> None:
        return None

    def exception(self, *a: object, **k: object) -> None:
        return None


_silent_logger = _NoopLogger()


def setup_basic_logger(name: str = "x_make", *, file_path: Optional[str] = None) -> _NoopLogger:
    return _silent_logger

logger = setup_basic_logger("x_make_github_clones_x")

"""red rabbit 2025_0902_0944"""
try:
    # Python 3 builtin
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except Exception:  # pragma: no cover - extremely unlikely on CPython
    logger.error("urllib not available in this Python runtime.")
    sys.exit(1)

# Module-level default target directory (script-level variable) - empty by default
# Concrete default is set in main() as DEFAULT_TARGET_DIR
DEFAULT_TARGET_DIR = ""


class x_cls_make_github_clones_x:
    """Clone GitHub repositories for a user.

    Tweakable parameters are exposed as class variables so you can subclass or
    modify behavior programmatically.
    """

    # Tweakable class variables
    DEFAULT_TARGET_DIR: str = DEFAULT_TARGET_DIR
    # Do not assume a username by default; main() must supply it.
    DEFAULT_USERNAME = None
    PER_PAGE = 100
    USER_AGENT = "clone-script"
    PROMPT_FOR_TOKEN_IN_VENV = True

    # Default whitelist (names to include) - empty by default; main() provides defaults
    DEFAULT_NAMES: ClassVar[list[str]] = []

    def __init__(
        self,
        username: str | None = None,
        target_dir: str | None = None,
        *,
        shallow: bool = False,
        include_forks: bool = False,
        names: str | None = None,
        yes: bool = False,
        auto_install_hooks: bool = True,
        auto_overwrite_configs: bool = False,
    ):
        self.username = username or self.DEFAULT_USERNAME
        self.target_dir = (
            os.path.abspath(target_dir) if target_dir else os.path.abspath(self.DEFAULT_TARGET_DIR)
        )
        self.shallow = shallow
        self.include_forks = include_forks
        self.names = set([n.strip() for n in names.split(",") if n.strip()]) if names else None
        self.yes = yes
        # If true, attempt to auto-install and run pre-commit hooks inside each cloned repo
        self.auto_install_hooks = bool(auto_install_hooks)
        # If true, allow overwriting repo config files like pyproject.toml.
        # Otherwise skip to avoid collisions with existing packaging metadata.
        self.auto_overwrite_configs = bool(auto_overwrite_configs)
        self.token = os.environ.get("GITHUB_TOKEN")
        if not self.token or self.token == "NO_TOKEN_PROVIDED":
            raise RuntimeError(
                "No GitHub token provided in environment. Set GITHUB_TOKEN in your venv."
            )
        self.auth_username: str | None = None
        # exit code from last run (0 success, non-zero failure)
        self.exit_code = 0
        # Track repos where pyproject.toml looked like packaging metadata and was not overwritten
        self._pyproject_conflicts: list[str] = []

    def _request_json(self, url: str, headers: dict[str, str]) -> Any:
        req = Request(url, headers=headers)
        try:
            with urlopen(req) as resp:
                return json.load(resp)
        except HTTPError as e:
            body = None
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.error(
                "GitHub API error: %s %s", getattr(e, "code", "?"), getattr(e, "reason", "?")
            )
            if body:
                logger.error(body)
            sys.exit(2)

    def fetch_repos(
        self, username: str, token: str | None, include_forks: bool
    ) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        per_page = self.PER_PAGE
        page = 1
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.USER_AGENT,
        }
        if token:
            headers["Authorization"] = f"token {token}"

        while True:
            params = urlencode({"per_page": per_page, "page": page})
            url = f"https://api.github.com/users/{username}/repos?{params}"
            data: Any = self._request_json(url, headers)

            if not isinstance(data, list):
                logger.error("Unexpected response from GitHub API: %s", data)
                sys.exit(3)

            data_list = cast(list[dict[str, Any]], data)
            if not data_list:
                break

            for r in data_list:
                # r is a dynamic mapping from the GitHub API; it should be a dict
                if not include_forks and r.get("fork"):
                    continue
                repos.append(r)

            if len(data_list) < per_page:
                break
            page += 1
            time.sleep(0.1)

        return repos

    def fetch_authenticated_repos(self, token: str, include_forks: bool) -> list[dict[str, Any]]:
        repos_local: list[dict[str, Any]] = []
        per_page_local = self.PER_PAGE
        page_local = 1
        headers_local = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.USER_AGENT,
            "Authorization": f"token {token}",
        }

        while True:
            params_local = urlencode({"per_page": per_page_local, "page": page_local})
            url_local = f"https://api.github.com/user/repos?{params_local}"
            data_local: Any = self._request_json(url_local, headers_local)

            if not isinstance(data_local, list):
                logger.error("Unexpected response from GitHub API: %s", data_local)
                sys.exit(3)

            data_local_list = cast(list[dict[str, Any]], data_local)
            if not data_local_list:
                break

            for r in data_local_list:
                if not include_forks and r.get("fork"):
                    continue
                repos_local.append(r)

            if len(data_local_list) < per_page_local:
                break
            page_local += 1
            time.sleep(0.1)

        return repos_local

    @staticmethod
    def git_available() -> bool:
        try:
            completed = subprocess.run(
                ["git", "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
            return completed.returncode == 0
        except FileNotFoundError:
            return False

    def clone_repo(self, clone_url: str, dest_path: str, shallow: bool) -> int:
        cmd = ["git", "clone"]
        if shallow:
            cmd += ["--depth", "1"]
        cmd += [clone_url, dest_path]
        logger.info("Running: %s", " ".join(cmd))
        # Run git clone and return the exit code. Keep behavior simple and
        # consistent with prior implementation; callers interpret 0 as success.
        proc = subprocess.run(cmd, check=False)
        return proc.returncode

    def determine_auth_username(self) -> str | None:
        if not self.token:
            return None
        try:
            req_headers = {
                "Authorization": f"token {self.token}",
                "User-Agent": self.USER_AGENT,
                "Accept": "application/vnd.github.v3+json",
            }
            info = self._request_json("https://api.github.com/user", req_headers)
            if isinstance(info, dict):
                info_dict = cast(dict[str, Any], info)
                return info_dict.get("login")
            return None
        except Exception:
            return None

    def _clone_or_update_repo(self, r: dict[str, Any]) -> tuple[str, str, str]:
        """Clone or update repo; return (status, name, dest).

        status is one of 'cloned', 'updated', 'failed', 'skipped'.
        """
        name = r.get("name")
        if not name:
            return "skipped", "", ""
        if self.names and name not in self.names:
            logger.info("Skipping %s (not in whitelist)", name)
            return "skipped", name, ""

        dest = os.path.join(self.target_dir, name)
        clone_url = self._build_clone_url(r, name)

        status = "skipped"
        if not os.path.exists(dest):
            logger.info("Cloning %s into %s", name, dest)
            rc = self.clone_repo(clone_url, dest, self.shallow)
            status = "cloned" if rc == 0 else "failed"
            if status == "failed":
                logger.error("git clone failed for %s (rc=%s)", name, rc)
        else:
            logger.info("Updating %s in %s", name, dest)
            try:
                result = subprocess.run(
                    ["git", "-C", dest, "pull"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                rc = result.returncode
                if rc == 0:
                    status = "updated"
                elif "not a git repository" in (result.stderr or ""):
                    # Recloning helper will remove the dest and reclone; keep logic small here.
                    status = self._reclone_cleanup(dest, clone_url)
                else:
                    logger.error("git pull failed for %s (rc=%s)", name, rc)
                    logger.error(result.stderr)
                    status = "failed"
            except Exception as e:
                logger.exception("Exception during git pull for %s: %s", name, e)
                status = "failed"

        return status, name, dest

    def _build_clone_url(self, r: dict[str, Any], name: str) -> str:
        clone_url = r.get("clone_url") or r.get("ssh_url") or ""
        if self.token and r.get("private"):
            owner = r.get("owner", {}).get("login", self.username)
            clone_url = f"https://{self.token}@github.com/{owner}/{name}.git"
        return clone_url

    def _reclone_cleanup(self, dest: str, clone_url: str) -> str:
        """Remove a corrupt repo folder and attempt to reclone. Returns 'cloned' or 'failed'."""
        import shutil
        import stat

        def _on_rm_error(func: Any, path: str, exc_info: Any) -> None:
            """Compatibility onerror/onexc handler for rmtree.

            Parameters typed broadly to satisfy static analysis. The handler
            attempts to make the path writable and retry the operation.
            """
            try:
                os.chmod(path, stat.S_IWRITE)
            except Exception:
                pass
            try:
                # Some rmtree callers pass the failing function as the first
                # arg, others expect a (path, exc_info) style handler. We try
                # to call with the path if the provided 'func' is callable.
                if callable(func):
                    try:
                        func(path)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            logger.info("%s is not a git repository. Recloning...", dest)
            # Prefer the newer `onexc` parameter when available; fall back to
            # `onerror` on older Python versions. Build kwargs dynamically to
            # avoid passing an unsupported keyword directly.
            try:
                import inspect

                sig = inspect.signature(shutil.rmtree)
                kwargs: dict[str, Any] = {}
                if "onexc" in sig.parameters:
                    kwargs["onexc"] = _on_rm_error
                else:
                    # Older Pythons expect `onerror`.
                    kwargs["onerror"] = _on_rm_error
                try:
                    shutil.rmtree(dest, **kwargs)
                except TypeError:
                    # Some runtimes may reject kwargs; try plain rmtree.
                    try:
                        shutil.rmtree(dest)
                    except Exception:
                        # Give up gracefully and continue to reclone step.
                        pass
            except Exception:
                # Best-effort fallback: attempt rmtree with onerror where possible.
                try:
                    # Fall back to onerror for very old runtimes. mypy/ruff may
                    # still warn about deprecated 'onerror'; silence for this
                    # compatibility branch only.
                    shutil.rmtree(dest, onerror=_on_rm_error)
                except Exception:
                    try:
                        shutil.rmtree(dest)
                    except Exception:
                        pass
        except Exception as e:
            logger.error("Failed to remove %s: %s", dest, e)
            return "failed"
        rc2 = self.clone_repo(clone_url, dest, self.shallow)
        if rc2 == 0:
            logger.info("Reclone successful for %s.", os.path.basename(dest))
            return "cloned"
        logger.error("Reclone failed for %s (rc=%s)", os.path.basename(dest), rc2)
        return "failed"

    def _write_standard_configs(self, name: str, dest: str) -> None:
        """No-op: cloner is intentionally bare-bones and must not create project files.

        All project scaffolding (pyproject, pre-commit, CI workflows, etc.) is now
        the responsibility of the PyPI publisher class which runs in a controlled
        build directory. This prevents accidental overwrites in existing repos.
        """
        # Intentionally do nothing. Keep repository folders minimal.
        return

    # pre-commit config generation removed per request; do not write .pre-commit-config.yaml

    def _maybe_write_pyproject(self, name: str, dest: str) -> None:
        pyproject_path = os.path.join(dest, "pyproject.toml")
        write_pyproject = True
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, encoding="utf-8") as pf:
                    existing = pf.read()
            except Exception:
                existing = ""
            if "[project]" in existing or "name =" in existing or "version =" in existing:
                write_pyproject = False
                logger.info("Existing pyproject.toml in %s; skipping.", name)
                self._pyproject_conflicts.append(name)
            elif not self.auto_overwrite_configs:
                write_pyproject = False
                logger.info("Existing pyproject.toml in %s; not overwriting.", name)
        if not write_pyproject:
            return
        # Compose a minimal pyproject with project metadata followed by tooling fragment
        pyproject_content = (
            f"[project]\n"
            f'name = "{name}"\n'
            f'version = "0.0.0"\n'
            f'description = "A repository in the {self.username} workspace. Update as needed."\n'
            f"authors = [{{name = \"{self.username or 'author'}\"}}]\n\n"
            + templates.PYPROJECT_FRAGMENT
        )
        try:
            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(pyproject_content)
        except Exception as e:
            logger.error("Failed to write pyproject.toml for %s: %s", name, e)

    def _write_ci_yaml(self, dest: str) -> None:
        ci_yml_path = os.path.join(dest, ".github", "workflows", "ci.yml")
        try:
            with open(ci_yml_path, "w", encoding="utf-8") as f:
                f.write(templates.CI_WINDOWS)
        except Exception as e:
            logger.error("Failed to write CI workflow for %s: %s", dest, e)

    def _write_gitignore_and_requirements(self, name: str, dest: str) -> None:
        gitignore_path = os.path.join(dest, ".gitignore")
        gitignore_template = (
            "# Python\n"
            "__pycache__/\n"
            "*.pyc\n"
            "*.pyo\n"
            "*.pyd\n"
            "*.so\n"
            "*.egg\n"
            "*.egg-info/\n"
            "dist/\n"
            "build/\n"
            ".eggs/\n"
            "*.manifest\n"
            "*.spec\n"
            """
            No-op: cloner is intentionally bare-bones and must not create project files.

            All project scaffolding (pyproject, CI workflows, etc.) is now
            the responsibility of the PyPI publisher class which runs in a controlled
            build directory. This prevents accidental overwrites in existing repos.
            """
        )
        try:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(gitignore_template)
        except Exception as e:
            logger.error("Failed to write .gitignore for %s: %s", name, e)
        requirements_dev_path = os.path.join(dest, "requirements-dev.txt")
        try:
            with open(requirements_dev_path, "w", encoding="utf-8") as f:
                f.write(templates.REQS_DEV)
        except Exception as e:
            logger.error("Failed to write requirements-dev.txt for %s: %s", name, e)

    def _write_bootstrap_scripts(self, dest: str) -> None:
        bootstrap_ps1 = os.path.join(dest, "bootstrap_dev_tools.ps1")
        bootstrap_sh = os.path.join(dest, "bootstrap_dev_tools.sh")
        try:
            with open(bootstrap_ps1, "w", encoding="utf-8") as f:
                f.write(templates.BOOTSTRAP_PS1)
        except Exception:
            pass
        try:
            with open(bootstrap_sh, "w", encoding="utf-8") as f:
                f.write(templates.BOOTSTRAP_SH)
        except Exception:
            pass
        try:
            import stat as _stat

            os.chmod(bootstrap_sh, (os.stat(bootstrap_sh).st_mode | _stat.S_IXUSR))
        except Exception:
            pass

    def _write_readme(self, name: str, dest: str) -> None:
        readme_path = os.path.join(dest, "README.md")
        try:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# {name}\n\nThis repository was bootstrapped by the workspace cloner.\n\n"
                    "To enable development tooling (ruff/black/mypy):\n\n"
                    "PowerShell:\n\n"
                    "```powershell\n"
                    "./bootstrap_dev_tools.ps1\n"
                    "```\n\n"
                    "POSIX shell:\n\n"
                    "```bash\n"
                    "./bootstrap_dev_tools.sh\n"
                    "```\n\n"
                    "Edit `pyproject.toml` to set a proper `name` and `version` for packaging.\n"
                )
        except Exception:
            logger.exception("Failed to write README for %s", name)

    # pre-commit hook installation removed per request; do not run or install hooks automatically

    def _process_repo(self, r: dict[str, Any]) -> str:
        status, name, dest = self._clone_or_update_repo(r)
        if status in {"failed", "skipped"}:
            return status
        # write configs and run hooks
        self._write_standard_configs(name, dest)
        self._install_pre_commit_hooks(dest)
        return status

    def _sync_repos(self, repos: list[dict[str, Any]]) -> tuple[int, int, int, int]:
        """Sync the provided repos list: clone/update and post-process.

        Returns (cloned, updated, skipped, failed).
        """
        cloned = updated = skipped = failed = 0
        for r in repos:
            name = r.get("name")
            if not name:
                continue
            if self.names and name not in self.names:
                skipped += 1
                logger.info("Skipping %s (not in whitelist)", name)
                continue

            repo_status, _, _ = self._clone_or_update_repo(r)
            dest = os.path.join(self.target_dir, name)
            if repo_status == "cloned":
                cloned += 1
                self._write_standard_configs(name, dest)
                self._install_pre_commit_hooks(dest)
            elif repo_status == "updated":
                updated += 1
                self._write_standard_configs(name, dest)
                self._install_pre_commit_hooks(dest)
            elif repo_status == "skipped":
                skipped += 1
            else:
                failed += 1
        return cloned, updated, skipped, failed

    def run(self) -> str:
        if not self.git_available():
            logger.error("git is not available on PATH. Please install Git and retry.")
            self.exit_code = 10
            return ""

        # Ensure the target directory exists
        os.makedirs(self.target_dir, exist_ok=True)
        logger.info("Fetching repositories for user: %s", self.username)
        logger.info("Synchronizing repositories in: %s", self.target_dir)

        # Determine auth username if token provided
        if self.token:
            self.auth_username = self.determine_auth_username()

        if self.token and self.auth_username and self.auth_username == self.username:
            repos = self.fetch_authenticated_repos(self.token, self.include_forks)
        else:
            repos = self.fetch_repos(str(self.username), self.token, self.include_forks)

        logger.info("Found %d repositories (after fork filter).", len(repos))

        # Delegate the per-repo work to _sync_repos to reduce complexity.
        cloned, updated, skipped, failed = self._sync_repos(repos)

        logger.info(
            "Done. cloned=%d updated=%d skipped=%d failed=%d", cloned, updated, skipped, failed
        )
        # Report pyproject.toml collisions (if any)
        if self._pyproject_conflicts:
            logger.info(
                "\npyproject.toml collision report: the following repos were NOT overwritten:"
            )
            for repo_name in sorted(set(self._pyproject_conflicts)):
                logger.info(" - %s", repo_name)
            logger.info("To overwrite, set auto_overwrite_configs=True on the cloner.")
        self.exit_code = 0 if failed == 0 else 4
        if failed:
            raise AssertionError(f"{failed} repositories failed to clone or update")
        # Return the target directory so downstream processes can use it.
        return self.target_dir

    def _install_pre_commit_hooks(self, dest: str) -> None:
        """No-op placeholder: pre-commit installation was removed by refactor.

        Kept as a no-op so older call sites remain safe and type-checkers
        see a defined attribute.
        """
        # Intentionally do nothing.
        return


# Dummy main block for import safety
