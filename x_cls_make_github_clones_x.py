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

import os
import subprocess
import sys
import time
from typing import Any, cast
from x_make_common_x.x_cls_make_common_x import BaseMake


# Logging removed: prints are used directly (INFO->stdout, ERROR->stderr) where needed.

# Templates and file-writing scaffolding removed: this cloner only clones/pulls.
# Optional removed; no longer needed


"""red rabbit 2025_0902_0944"""
try:
    # Python 3 builtin
    from urllib.parse import urlencode
except Exception as exc:  # pragma: no cover - extremely unlikely on CPython
    raise RuntimeError("urllib not available in this Python runtime.") from exc

# Module-level default target directory (script-level variable) - empty by default
# Concrete default is set in main() as DEFAULT_TARGET_DIR
DEFAULT_TARGET_DIR = ""


class x_cls_make_github_clones_x(BaseMake):
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

    # Configurable runtime options (can be overridden in subclasses)
    GIT_BIN: str = "git"
    TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
    ALLOW_TOKEN_CLONE_ENV: str = "X_ALLOW_TOKEN_CLONE"
    RECLONE_ON_CORRUPT: bool = True

    CLONE_RETRIES: int = 1
    # Default whitelist (names to include) - empty by default; main() provides defaults
    NAMES: list[str] | None = None

    def __init__(
        self,
        username: str | None = None,
        target_dir: str | None = None,
        shallow: bool = False,
        include_forks: bool = False,
        force_reclone: bool = False,
        names: list[str] | str | None = None,
        token: str | None = None,
        **kwargs: Any,
    ) -> None:
        # Instance configuration; prefer explicit args, then class defaults
        self.username = username or self.DEFAULT_USERNAME
        self.target_dir = target_dir or self.DEFAULT_TARGET_DIR or ""
        self.shallow = shallow
        self.include_forks = include_forks
        self.force_reclone = force_reclone
        # names can be provided as comma-separated string from CLI
        # Ensure `self.names` is declared with a union type so assignments
        # from different branches are compatible with static analysis.
        self.names: list[str] | None = None
        if isinstance(names, str):
            parsed = [n.strip() for n in names.split(",") if n.strip()]
            self.names = parsed
        else:
            self.names = names if names is not None else self.NAMES
        # Token may be provided explicitly or sourced from env
        self.token = token or os.environ.get(self.TOKEN_ENV_VAR)
        # placeholder for auth username discovered via token
        self.auth_username: str | None = None
        # exit code placeholder
        self.exit_code: int | None = None
        # accept optional ctx kwarg for compatibility with orchestrator tests
        ctx = kwargs.get("ctx")
        if ctx is not None:
            try:
                # Mirror test expectation
                from x_make_common_x.helpers import info as _info

                _info("[github_clones] initialized")
            except Exception:
                pass

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
                from x_make_common_x.helpers import error as _error

                _error(msg)
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

    @classmethod
    def git_available(cls) -> bool:
        try:
            completed = subprocess.run(
                [cls.GIT_BIN, "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
            return completed.returncode == 0
        except FileNotFoundError:
            return False

    def clone_repo(self, clone_url: str, dest_path: str, shallow: bool) -> int:
        # Build and run the git clone command. INFO goes to stdout.
        cmd = [self.GIT_BIN, "clone"]
        if shallow:
            cmd.extend(["--depth", "1"])
        cmd.extend([clone_url, dest_path])
        from x_make_common_x.helpers import info as _info

        _info(f"INFO: Running: {' '.join(cmd)}")
        # Run git clone and return the exit code. Callers interpret 0 as success.
        proc = subprocess.run(cmd, check=False)
        return proc.returncode

    def determine_auth_username(self) -> str | None:
        if not getattr(self, "token", None):
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
        name = cast(str | None, r.get("name"))
        early = self._validate_clone_candidate(name)
        if early is not None:
            return early

        # At this point name is expected to be a str per _validate_clone_candidate
        assert isinstance(name, str)
        dest = os.path.join(str(self.target_dir), name)
        clone_url = self._build_clone_url(r, name)

        # If dest doesn't exist, clone; otherwise let _handle_existing decide.
        if not os.path.exists(dest):
            from x_make_common_x.helpers import info as _info

            _info(f"Cloning {name} into {dest}")
            rc = self.clone_repo(clone_url, dest, self.shallow)
            status = "cloned" if rc == 0 else "failed"
            if status == "failed":
                from x_make_common_x.helpers import error as _error

                _error(f"git clone failed for {name} (rc={rc})")
            else:
                status = self._handle_existing(dest, clone_url, name)

            return status, name, dest
        # If destination already exists, defer to handler which attempts update
        # and returns a status string.
        status = self._handle_existing(dest, clone_url, name)
        return status, name, dest

    def _attempt_update(self, dest: str, clone_url: str, name: str) -> str:
        """Attempt to update an existing repo at dest and return new status.

        This helper consolidates the pull/fetch/reclone recovery flow so the
        public `_clone_or_update_repo` method remains small.
        """
        try:
            # Attempt a normal pull with one retry; if it fails, attempt fetch before recloning.
            result = subprocess.run(
                [self.GIT_BIN, "-C", dest, "pull"],
                check=False,
                capture_output=True,
                text=True,
            )
            rc = result.returncode
            if rc == 0:
                return "updated"

            # Try a fetch as a second-line recovery step (may succeed if only network hiccup)
            from x_make_common_x.helpers import info as _info

            _info(f"git pull for {name} returned rc={rc}; attempting git fetch as recovery")
            try:
                fetch_res = subprocess.run(
                    [self.GIT_BIN, "-C", dest, "fetch", "--all"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if fetch_res.returncode == 0:
                    # After a successful fetch, try pull again
                    retry = subprocess.run(
                        [self.GIT_BIN, "-C", dest, "pull"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if retry.returncode == 0:
                        return "updated"
                    from x_make_common_x.helpers import info as _info

                    _info(
                        f"git pull retry failed for {name} (rc={retry.returncode}); will attempt reclone"
                    )
                    return self._reclone_cleanup(dest, clone_url)
                # fetch failed; repository may be corrupted or remote unreachable
                from x_make_common_x.helpers import error as _error

                _error(
                    f"git fetch failed for {name} (rc={fetch_res.returncode}); stdout={fetch_res.stdout} stderr={fetch_res.stderr}"
                )
                return self._reclone_cleanup(dest, clone_url)
            except Exception as e:
                from x_make_common_x.helpers import error as _error

                _error(f"Exception during git fetch/pull recovery for {name}: {e}")
                
                return self._reclone_cleanup(dest, clone_url)
        except Exception as e:
            from x_make_common_x.helpers import error as _error

            _error(f"Exception during git pull for {name}: {e}")
            return self._reclone_cleanup(dest, clone_url)

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
            from x_make_common_x.helpers import info as _info

            _info(f"{dest} is not a git repository. Recloning...")
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
            from x_make_common_x.helpers import error as _error

            _error(f"Failed to remove {dest}: {e}")
            return "failed"
        rc2 = self.clone_repo(clone_url, dest, self.shallow)
        if rc2 == 0:
            from x_make_common_x.helpers import info as _info

            _info(f"Reclone successful for {os.path.basename(dest)}.")
            return "cloned"
        from x_make_common_x.helpers import error as _error

        _error(f"Reclone failed for {os.path.basename(dest)} (rc={rc2})")
        return "failed"

    def _request_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Any:
        """Simple JSON fetch helper used by both authenticated and public fetchers."""
        try:
            import json
            import urllib.request

            req = urllib.request.Request(url)
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.load(resp)
        except Exception:
            return {}

    def fetch_repos(
        self, username: str, token: str | None, include_forks: bool
    ) -> list[dict[str, Any]]:
        """Fetch public repos for a user (non-authenticated). Returns list of repo dicts."""
        repos_local: list[dict[str, Any]] = []
        per_page_local = self.PER_PAGE
        page_local = 1
        headers_local = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.USER_AGENT,
        }
        if token:
            headers_local["Authorization"] = f"token {token}"

        while True:
            params_local = urlencode(
                {"per_page": per_page_local, "page": page_local}
            )
            url_local = (
                f"https://api.github.com/users/{username}/repos?{params_local}"
            )
            data_local: Any = self._request_json(url_local, headers_local)
            if not isinstance(data_local, list):
                break
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

    def _validate_clone_candidate(
        self, name: Any
    ) -> tuple[str, str, str] | None:
        """Validate a repo name before cloning; return a skip tuple or None to continue."""
        if not name or not isinstance(name, str):
            return ("skipped", "", "")
        # Simple whitelist check
        if self.names and name not in self.names:
            return ("skipped", name, os.path.join(self.target_dir, name))
        return None

    def _do_clone(self, name: str, dest: str, clone_url: str) -> str:
        """Perform a git clone and return status 'cloned' or 'failed'."""
        rc = self.clone_repo(clone_url, dest, self.shallow)
        status = "cloned" if rc == 0 else "failed"
        if status == "failed":
            from x_make_common_x.helpers import error as _error

            _error(f"git clone failed for {name} (rc={rc})")
        return status

    def _handle_existing(self, dest: str, clone_url: str, name: str) -> str:
        """Handle path-existing cases: force_reclone, non-dir, missing git, or update.

        Returns a status string: 'cloned', 'failed', 'updated', or 'skipped'.
        """
        # force_reclone
        if getattr(self, "force_reclone", False):
            from x_make_common_x.helpers import info as _info

            _info(f"force_reclone enabled; removing existing {dest} and recloning")
            try:
                import shutil

                shutil.rmtree(dest)
            except Exception as e:
                from x_make_common_x.helpers import error as _error

                _error(f"Failed to remove {dest} for force_reclone: {e}")
                return "failed"
            status = self._do_clone(name, dest, clone_url)
            return status

        # destination exists but is not a dir
        if not os.path.isdir(dest):
            from x_make_common_x.helpers import info as _info

            _info(f"Destination exists and is not a directory: {dest}; removing and recloning")
            try:
                import shutil

                shutil.rmtree(dest)
            except Exception as e:
                from x_make_common_x.helpers import error as _error

                _error(f"Failed to remove invalid destination {dest}: {e}")
                return "failed"
            status = self._do_clone(name, dest, clone_url)
            if status == "failed":
                from x_make_common_x.helpers import error as _error

                _error(f"git clone failed for {name} after cleanup (rc?)")
            return status

        # missing .git or invalid repo
        if not (
            os.path.join(dest, ".git")
            and os.path.exists(os.path.join(dest, ".git"))
        ):
            from x_make_common_x.helpers import info as _info

            _info(f"{dest} missing .git or invalid repository; performing reclone cleanup")
            status = self._reclone_cleanup(dest, clone_url)
            return status

        # otherwise attempt update
        status = self._attempt_update(dest, clone_url, name)
        return status

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
            from x_make_common_x.helpers import error as _error

            _error(
                "WARN: ALLOW_WRITE_YAML_CONFIGS=1 set; scaffold write allowed by policy but no-op remains by default"
            )
            return

        # Default safe behavior: log and no-op.
        from x_make_common_x.helpers import info as _info

        _info(
            "INFO: Repository scaffold write disabled by policy; skipping creation of pyproject/pre-commit/CI workflows."
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
                from x_make_common_x.helpers import info as _info
                _info(f"INFO: Skipping {name} (not in whitelist)")
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
        """Run the cloner: fetch repo lists and synchronize into target_dir.

        Returns the target directory on success or an empty string on fatal error.
        """
        if not self.git_available():
            from x_make_common_x.helpers import error as _error

            _error("git is not available on PATH. Please install Git and retry.")
            self.exit_code = 10
            return ""

        # Ensure the target directory exists
        os.makedirs(self.target_dir, exist_ok=True)
        from x_make_common_x.helpers import info as _info

        _info(f"Fetching repositories for user: {self.username}")
        _info(f"Synchronizing repositories in: {self.target_dir}")

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

        _info(f"Found {len(repos)} repositories (after fork filter).")

        # Delegate the per-repo work to _sync_repos to reduce complexity.
        cloned, updated, skipped, failed = self._sync_repos(repos)

        _info(f"Done. cloned={cloned} updated={updated} skipped={skipped} failed={failed}")
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
        from x_make_common_x.helpers import error as _error

        _error(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(_cli_main())
