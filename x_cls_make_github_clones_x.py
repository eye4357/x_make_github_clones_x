#!/usr/bin/env python3
"""
Merged cloner and bootstrap utility for GitHub repos.

Features:
- Clones all whitelisted repositories for a single GitHub user into the target directory as children.
- If a repo folder does not exist, it is cloned. If it exists, it is updated (git pull).
- After cloning/updating, always creates or overwrites .pre-commit-config.yaml, pyproject.toml, and .github/workflows/ci.yml in each repo for code quality and CI.
- (Legacy) Can snapshot, validate, and restore repo folders (see previous bootstrap logic).

Why are .pre-commit-config.yaml, pyproject.toml, and .github/workflows/ci.yml always created or overwritten?

These files are essential for modern Python projects to ensure:
- Consistent code formatting and linting (ruff, black) and type checking (mypy) across all environments.
- Automatic enforcement of code quality before every commit (via pre-commit hooks).
- Automated CI checks on every push and pull request (via GitHub Actions), so code quality is never skipped.

Without these files, you lose automation, consistency, and easy enforcement of code standards. Their presence is a best practice for Python projects using these tools.

Important: review the script and the docstring carefully before running any destructive operations. This tool intentionally implements a dangerous workflow only when the user explicitly opts in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any, ClassVar, cast

"""red rabbit 2025_0902_0944"""
try:
    # Python 3 builtin
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except Exception:  # pragma: no cover - extremely unlikely on CPython
    print("urllib not available in this Python runtime.")
    sys.exit(1)

# Module-level default target directory (script-level variable) - empty by default
# The concrete default is set in main() and assigned to x_cls_make_github_clones_x.DEFAULT_TARGET_DIR
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
        # If true, allow overwriting repo config files like pyproject.toml; otherwise skip to avoid collisions.
        self.auto_overwrite_configs = bool(auto_overwrite_configs)
        self.token = os.environ.get("GITHUB_TOKEN")
        if not self.token or self.token == "NO_TOKEN_PROVIDED":
            raise RuntimeError(
                "No GitHub token provided in environment. Set GITHUB_TOKEN in your venv."
            )
        self.auth_username: str | None = None
        # exit code from last run (0 success, non-zero failure)
        self.exit_code = 0
        # Track repos where we detected pyproject.toml that look like packaging metadata and were not overwritten
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
            print(f"GitHub API error: {getattr(e, 'code', '?')} {getattr(e, 'reason', '?')}")
            if body:
                print(body)
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
                print("Unexpected response from GitHub API:", data)
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
                print("Unexpected response from GitHub API:", data_local)
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
        print("Running:", " ".join(cmd))
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
            print(f"Skipping {name} (not in whitelist)")
            return "skipped", name, ""

        dest = os.path.join(self.target_dir, name)
        clone_url = self._build_clone_url(r, name)

        status = "skipped"
        if not os.path.exists(dest):
            print(f"Cloning {name} into {dest}")
            rc = self.clone_repo(clone_url, dest, self.shallow)
            status = "cloned" if rc == 0 else "failed"
            if status == "failed":
                print(f"git clone failed for {name} (rc={rc})")
        else:
            print(f"Updating {name} in {dest}")
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
                    print(f"git pull failed for {name} (rc={rc})")
                    print(result.stderr)
                    status = "failed"
            except Exception as e:
                print(f"Exception during git pull for {name}: {e}")
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
            print(f"{dest} is not a git repository. Recloning...")
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
            print(f"Failed to remove {dest}: {e}")
            return "failed"
        rc2 = self.clone_repo(clone_url, dest, self.shallow)
        if rc2 == 0:
            print(f"Reclone successful for {os.path.basename(dest)}.")
            return "cloned"
        print(f"Reclone failed for {os.path.basename(dest)} (rc={rc2})")
        return "failed"

    def _write_standard_configs(self, name: str, dest: str) -> None:
        """No-op: cloner is intentionally bare-bones and must not create project files.

        All project scaffolding (pyproject, pre-commit, CI workflows, etc.) is now
        the responsibility of the PyPI publisher class which runs in a controlled
        build directory. This prevents accidental overwrites in existing repos.
        """
        # Intentionally do nothing. Keep repository folders minimal.
        return

    def _write_precommit_config(self, name: str, dest: str) -> None:
        precommit_path = os.path.join(dest, ".pre-commit-config.yaml")
        try:
            with open(precommit_path, "w", encoding="utf-8") as f:
                f.write(
                    """repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v4.6.0\n    hooks:\n      - id: trailing-whitespace\n      - id: end-of-file-fixer\n      - id: check-yaml\n      - id: check-toml\n  - repo: local\n    hooks:\n      - id: ruff\n        name: ruff\n        entry: ruff check\n        language: system\n        types: [python]\n      - id: black\n        name: black\n        entry: black\n        language: system\n        types: [python]\n      - id: mypy\n        name: mypy\n        entry: mypy\n        language: system\n        types: [python]\n        pass_filenames: false\n        args: ["."]\n"""
                )
        except Exception as e:
            print(f"Failed to write pre-commit config for {name}: {e}")

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
                print(
                    f"Existing pyproject.toml in {name} appears to contain project metadata; skipping overwrite to avoid collision with packaging tools."
                )
                self._pyproject_conflicts.append(name)
            elif not self.auto_overwrite_configs:
                write_pyproject = False
                print(
                    f"Existing pyproject.toml in {name} found; not overwriting (enable auto_overwrite_configs to force)."
                )
        if not write_pyproject:
            return
        pyproject_content = (
            f"[project]\n"
            f'name = "{name}"\n'
            f'version = "0.0.0"\n'
            f'description = "A repository in the {self.username} workspace. Update as needed."\n'
            f"authors = [{{name = \"{self.username or 'author'}\"}}]\n\n"
            '[tool.black]\nline-length = 100\ntarget-version = ["py313"]\n\n'
            '[tool.ruff]\nline-length = 100\ntarget-version = "py313"\nexclude = [\n  ".git",\n  "__pycache__",\n  ".mypy_cache",\n  ".ruff_cache",\n  ".venv",\n  "build",\n  "dist",\n]\n\n'
            '[tool.ruff.lint]\nselect = ["E", "F", "I", "UP", "B", "PL", "RUF"]\nignore = ["E501", "E402", "PLC0415", "PLR2004", "PLR0913"]\n\n'
            '[tool.mypy]\npython_version = "3.13"\nignore_missing_imports = true\nwarn_unused_ignores = true\nwarn_redundant_casts = true\nno_implicit_optional = true\nstrict_optional = true\nexclude = "(^.venv/|^.mypy_cache/|^build/|^dist/)"\n'
        )
        try:
            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(pyproject_content)
        except Exception as e:
            print(f"Failed to write pyproject.toml for {name}: {e}")

    def _write_ci_yaml(self, dest: str) -> None:
        ci_yml_path = os.path.join(dest, ".github", "workflows", "ci.yml")
        try:
            with open(ci_yml_path, "w", encoding="utf-8") as f:
                f.write(
                    """name: CI\n\non:\n  push:\n  pull_request:\n\njobs:\n  lint-type:\n    runs-on: windows-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.13'\n      - name: Cache pip\n        uses: actions/cache@v4\n        with:\n          path: ~\\AppData\\Local\\pip\\Cache\n          key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml') }}\n          restore-keys: |\n            ${{ runner.os }}-pip-\n      - name: Install tools\n        run: |\n          python -m pip install -U pip\n          python -m pip install -U ruff black mypy\n      - name: Ruff\n        run: ruff check .\n      - name: Black (check)\n        run: black --check .\n      - name: Mypy\n        run: mypy .\n"""
                )
        except Exception as e:
            print(f"Failed to write CI workflow for {dest}: {e}")

    def _write_gitignore_and_requirements(self, name: str, dest: str) -> None:
        gitignore_path = os.path.join(dest, ".gitignore")
        gitignore_template = """# Python\n__pycache__/\n*.pyc\n*.pyo\n*.pyd\n*.so\n*.egg\n*.egg-info/\ndist/\nbuild/\n.eggs/\n*.manifest\n*.spec\n\n# VS Code\n.vscode/\n\n# OS\n.DS_Store\nThumbs.db\n"""
        try:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(gitignore_template)
        except Exception as e:
            print(f"Failed to write .gitignore for {name}: {e}")
        requirements_dev_path = os.path.join(dest, "requirements-dev.txt")
        try:
            with open(requirements_dev_path, "w", encoding="utf-8") as f:
                f.write("pre-commit\nruff\nblack\nmypy\n")
        except Exception as e:
            print(f"Failed to write requirements-dev.txt for {name}: {e}")

    def _write_bootstrap_scripts(self, dest: str) -> None:
        bootstrap_ps1 = os.path.join(dest, "bootstrap_dev_tools.ps1")
        bootstrap_sh = os.path.join(dest, "bootstrap_dev_tools.sh")
        try:
            with open(bootstrap_ps1, "w", encoding="utf-8") as f:
                f.write(
                    "# PowerShell bootstrap: run from the repo root\n"
                    "python -m pip install -U -r requirements-dev.txt\n"
                    "python -m pre_commit install\n"
                    "python -m pre_commit run --all-files\n"
                )
        except Exception:
            pass
        try:
            with open(bootstrap_sh, "w", encoding="utf-8") as f:
                f.write(
                    "#!/usr/bin/env bash\n"
                    "# Shell bootstrap: run from the repo root\n"
                    "python -m pip install -U -r requirements-dev.txt\n"
                    "python -m pre_commit install\n"
                    "python -m pre_commit run --all-files\n"
                )
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
                    "To enable development tooling (pre-commit hooks, ruff/black/mypy):\n\n"
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
            pass

    def _install_pre_commit_hooks(self, dest: str) -> None:
        if not self.auto_install_hooks:
            return
        try:
            import shutil

            pre_exec = shutil.which("pre-commit")
            if pre_exec:
                print(f"Installing pre-commit hooks in {dest}")
                try:
                    subprocess.run([pre_exec, "install"], cwd=dest, check=False)
                except Exception:
                    subprocess.run(["pre-commit", "install"], cwd=dest, check=False)
                try:
                    subprocess.run([pre_exec, "run", "--all-files"], cwd=dest, check=False)
                except Exception:
                    subprocess.run(["pre-commit", "run", "--all-files"], cwd=dest, check=False)
            else:
                print(
                    f"pre-commit not found on PATH; skipping hook install in {dest}. Install pre-commit or run 'pip install -r requirements-dev.txt' to enable it."
                )
        except Exception as e:
            print(f"Failed to install/run pre-commit hooks in {dest}: {e}")

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
                print(f"Skipping {name} (not in whitelist)")
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
            print("git is not available on PATH. Please install Git and retry.")
            self.exit_code = 10
            return ""

        # Ensure the target directory exists
        os.makedirs(self.target_dir, exist_ok=True)

        print(f"Fetching repositories for user: {self.username}")
        print(f"Synchronizing repositories in: {self.target_dir}")

        # Determine auth username if token provided
        if self.token:
            self.auth_username = self.determine_auth_username()

        if self.token and self.auth_username and self.auth_username == self.username:
            repos = self.fetch_authenticated_repos(self.token, self.include_forks)
        else:
            repos = self.fetch_repos(str(self.username), self.token, self.include_forks)

        print(f"Found {len(repos)} repositories (after fork filter).")

        # Delegate the per-repo work to _sync_repos to reduce complexity.
        cloned, updated, skipped, failed = self._sync_repos(repos)

        print(f"Done. cloned={cloned} updated={updated} skipped={skipped} failed={failed}")
        # Report pyproject.toml collisions (if any)
        if self._pyproject_conflicts:
            print(
                "\npyproject.toml collision report: the following repos contain project metadata and were NOT overwritten by the cloner:"
            )
            for repo_name in sorted(set(self._pyproject_conflicts)):
                print(f" - {repo_name}")
            print(
                "If you want the cloner to overwrite these files, construct x_cls_make_github_clones_x with auto_overwrite_configs=True."
            )
        self.exit_code = 0 if failed == 0 else 4
        if failed:
            raise AssertionError(f"{failed} repositories failed to clone or update")
        # Return the target directory so downstream processes can use it.
        return self.target_dir


# Dummy main block for import safety
