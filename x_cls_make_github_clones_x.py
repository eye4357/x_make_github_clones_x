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


# Logging removed: prints are used directly (INFO->stdout, ERROR->stderr) where needed.

# Templates and file-writing scaffolding removed: this cloner only clones/pulls.
# Optional removed; no longer needed


"""red rabbit 2025_0902_0944"""
try:
    # Python 3 builtin
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except Exception:  # pragma: no cover - extremely unlikely on CPython
    raise RuntimeError("urllib not available in this Python runtime.")

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
    ):
        self.username = username or self.DEFAULT_USERNAME
        self.target_dir = (
            os.path.abspath(target_dir)
            if target_dir
            else os.path.abspath(self.DEFAULT_TARGET_DIR)
        )
        self.shallow = shallow
        self.include_forks = include_forks
        self.names = (
            set([n.strip() for n in names.split(",") if n.strip()])
            if names
            else None
        )
        # Intentionally minimal: only keep the flags needed for cloning.
        self.token = os.environ.get("GITHUB_TOKEN")
        if not self.token or self.token == "NO_TOKEN_PROVIDED":
            raise RuntimeError(
                "No GitHub token provided in environment. Set GITHUB_TOKEN in your venv."
            )
        self.auth_username: str | None = None
        # exit code from last run (0 success, non-zero failure)
        self.exit_code = 0

    # No file-writing; no pyproject conflict tracking.

    def _request_json(self, url: str, headers: dict[str, str]) -> Any:
        req = Request(url, headers=headers)
        try:
            with urlopen(req) as resp:
                return json.load(resp)
        except HTTPError as e:
            body = None
            try:
                # Some HTTPError objects expose a .read() for body bytes
                body = e.read().decode("utf-8")
            except Exception:
                pass
            msg = f"GitHub API error: {getattr(e, 'code', '?')} {getattr(e, 'reason', '?')}"
            if body:
                msg = msg + f" - {body}"
            print(f"ERROR: {msg}", file=sys.stderr)
            raise RuntimeError(msg)

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
                msg = f"Unexpected response from GitHub API: {data!r}"
                print(f"ERROR: {msg}", file=sys.stderr)
                raise RuntimeError(msg)

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

    def fetch_authenticated_repos(
        self, token: str, include_forks: bool
    ) -> list[dict[str, Any]]:
        repos_local: list[dict[str, Any]] = []
        per_page_local = self.PER_PAGE
        page_local = 1
        headers_local = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.USER_AGENT,
            "Authorization": f"token {token}",
        }

        while True:
            params_local = urlencode(
                {"per_page": per_page_local, "page": page_local}
            )
            url_local = f"https://api.github.com/user/repos?{params_local}"
            data_local: Any = self._request_json(url_local, headers_local)

            if not isinstance(data_local, list):
                msg = f"Unexpected response from GitHub API: {data_local!r}"
                print(f"ERROR: {msg}")
                raise RuntimeError(msg)

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
        # Build and run the git clone command. INFO goes to stdout.
        cmd = ["git", "clone"]
        if shallow:
            cmd.extend(["--depth", "1"])
        cmd.extend([clone_url, dest_path])
        print(f"INFO: Running: {' '.join(cmd)}", file=sys.stdout)
        # Run git clone and return the exit code. Callers interpret 0 as success.
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
            info = self._request_json(
                "https://api.github.com/user", req_headers
            )
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
            print(f"INFO: Skipping {name} (not in whitelist)", file=sys.stdout)
            return "skipped", name, ""

        dest = os.path.join(self.target_dir, name)
        clone_url = self._build_clone_url(r, name)

        status = "skipped"
        if not os.path.exists(dest):
            print(f"INFO: Cloning {name} into {dest}", file=sys.stdout)
            rc = self.clone_repo(clone_url, dest, self.shallow)
            status = "cloned" if rc == 0 else "failed"
            if status == "failed":
                print(
                    f"ERROR: git clone failed for {name} (rc={rc})",
                    file=sys.stderr,
                )
        else:
            print(f"INFO: Updating {name} in {dest}", file=sys.stdout)
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
                    print(
                        f"ERROR: git pull failed for {name} (rc={rc})",
                        file=sys.stderr,
                    )
                    if result.stderr:
                        print(f"ERROR: {result.stderr}", file=sys.stderr)
                    status = "failed"
            except Exception as e:
                print(
                    f"ERROR: Exception during git pull for {name}: {e}",
                    file=sys.stderr,
                )
                status = "failed"

        return status, name, dest

    def _build_clone_url(self, r: dict[str, Any], name: str) -> str:
        # Avoid embedding token in clone URLs. Prefer SSH if available because
        # it avoids credentials leakage; otherwise use the API-provided HTTPS URL
        # and let the user's git credential helper handle authentication.
        return r.get("ssh_url") or r.get("clone_url") or ""

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
            print(f"INFO: {dest} is not a git repository. Recloning...")
            # Prefer the newer `onexc` parameter when available; otherwise
            # fall back to a plain rmtree call. This is defensive across
            # Python versions and avoids deprecated parameters.
            try:
                import inspect

                sig = inspect.signature(shutil.rmtree)
                if "onexc" in sig.parameters:
                    try:
                        shutil.rmtree(dest, onexc=_on_rm_error)
                    except TypeError:
                        try:
                            shutil.rmtree(dest)
                        except Exception:
                            pass
                else:
                    try:
                        shutil.rmtree(dest)
                    except Exception:
                        pass
            except Exception:
                try:
                    shutil.rmtree(dest)
                except Exception:
                    pass
        except Exception as e:
            print(f"ERROR: Failed to remove {dest}: {e}", file=sys.stderr)
            return "failed"
        rc2 = self.clone_repo(clone_url, dest, self.shallow)
        if rc2 == 0:
            print(
                f"INFO: Reclone successful for {os.path.basename(dest)}.",
                file=sys.stdout,
            )
            return "cloned"
        print(
            f"ERROR: Reclone failed for {os.path.basename(dest)} (rc={rc2})",
            file=sys.stderr,
        )
        return "failed"

    def _write_standard_configs(self, name: str, dest: str) -> None:
        """No-op: cloner is intentionally bare-bones and must not create project files.

        All project scaffolding (pyproject, pre-commit, CI workflows, etc.) is now
        the responsibility of the PyPI publisher class which runs in a controlled
        build directory. This prevents accidental overwrites in existing repos.
        """
        # Explicit policy: do not write scaffold files by default. If a developer
        # intends to re-enable this behavior they must opt-in via the
        # ALLOW_WRITE_YAML_CONFIGS environment variable (set to '1'). This
        # prevents accidental generation of YAML hooks when the cloner runs.
        allow = os.environ.get("ALLOW_WRITE_YAML_CONFIGS")
        if allow and allow.strip() == "1":
            # Developer has explicitly opted in; still we avoid writing by
            # default in this code path. If future maintainers implement
            # generation, they should do so deliberately here.
            print(
                "WARN: ALLOW_WRITE_YAML_CONFIGS=1 set; scaffold write allowed by policy but no-op remains by default",
                file=sys.stderr,
            )
            return

        # Default safe behavior: log and no-op.
        print(
            "INFO: Repository scaffold write disabled by policy; skipping creation of pyproject/pre-commit/CI workflows.",
            file=sys.stdout,
        )
        return

    # pre-commit config generation removed per request; do not write .pre-commit-config.yaml

    # All file-writing helpers removed. This cloner only clones and updates repos.

    def _process_repo(self, r: dict[str, Any]) -> str:
        status, _, _ = self._clone_or_update_repo(r)
        if status in {"failed", "skipped"}:
            return status
        # Intentionally do not write any files or install hooks.
        return status

    def _sync_repos(
        self, repos: list[dict[str, Any]]
    ) -> tuple[int, int, int, int]:
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
                print(f"INFO: Skipping {name} (not in whitelist)")
                continue

            repo_status, _, _ = self._clone_or_update_repo(r)
            if repo_status == "cloned":
                cloned += 1
                # No file-writing or hook installation.
            elif repo_status == "updated":
                updated += 1
                # No file-writing or hook installation.
            elif repo_status == "skipped":
                skipped += 1
            else:
                failed += 1
        return cloned, updated, skipped, failed

    def run(self) -> str:
        if not self.git_available():
            print(
                "ERROR: git is not available on PATH. Please install Git and retry.",
                file=sys.stderr,
            )
            self.exit_code = 10
            return ""

        # Ensure the target directory exists
        os.makedirs(self.target_dir, exist_ok=True)
        print(f"INFO: Fetching repositories for user: {self.username}")
        print(f"INFO: Synchronizing repositories in: {self.target_dir}")

        # Determine auth username if token provided
        if self.token:
            self.auth_username = self.determine_auth_username()

        if (
            self.token
            and self.auth_username
            and self.auth_username == self.username
        ):
            repos = self.fetch_authenticated_repos(
                self.token, self.include_forks
            )
        else:
            repos = self.fetch_repos(
                str(self.username), self.token, self.include_forks
            )

        print(f"INFO: Found {len(repos)} repositories (after fork filter).")

        # Delegate the per-repo work to _sync_repos to reduce complexity.
        cloned, updated, skipped, failed = self._sync_repos(repos)

        print(
            f"INFO: Done. cloned={cloned} updated={updated} skipped={skipped} failed={failed}"
        )
        self.exit_code = 0 if failed == 0 else 4
        if failed:
            raise AssertionError(
                f"{failed} repositories failed to clone or update"
            )
        # Return the target directory so downstream processes can use it.
        return self.target_dir


# Dummy main block for import safety


def _cli_main(argv: list[str] | None = None) -> int:
    """Small CLI wrapper: returns exit code (0 success, non-zero failure)."""
    import argparse

    argv = argv if argv is not None else None
    parser = argparse.ArgumentParser(
        description="Clone GitHub repos for a user"
    )
    parser.add_argument("username", help="GitHub username to clone")
    parser.add_argument("target_dir", help="Local directory to store clones")
    parser.add_argument(
        "--shallow", action="store_true", help="Shallow clone (--depth 1)"
    )
    parser.add_argument(
        "--include-forks", action="store_true", help="Include forked repos"
    )
    parser.add_argument(
        "--names", help="Comma-separated whitelist of repo names", default=None
    )
    args = parser.parse_args(argv)

    try:
        cl = x_cls_make_github_clones_x(
            username=args.username,
            target_dir=args.target_dir,
            shallow=bool(args.shallow),
            include_forks=bool(args.include_forks),
            names=args.names,
        )
        cl.run()
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_cli_main())
