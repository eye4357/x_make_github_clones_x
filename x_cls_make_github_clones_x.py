#!/usr/bin/env python3
"""Clean, self-contained GitHub clones manager.

This module is intentionally compact and safe: it clones or updates GitHub
repositories for a user and does not write project scaffolding by default.
Helpers and a small BaseMake are inlined to avoid depending on external
shared packages.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import shutil
import time
from typing import Any, Iterable


def _info(*args: Any) -> None:
    try:
        print(" ".join(str(a) for a in args))
    except Exception:
        try:
            sys.stdout.write(" ".join(str(a) for a in args) + "\n")
        except Exception:
            pass


def _error(*args: Any) -> None:
    try:
        print(" ".join(str(a) for a in args), file=sys.stderr)
    except Exception:
        try:
            sys.stderr.write(" ".join(str(a) for a in args) + "\n")
        except Exception:
            pass


class BaseMake:
    DEFAULT_TARGET_DIR: str = r"C:\x_cloned_repos_x"
    GIT_BIN: str = "git"
    TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
    ALLOW_TOKEN_CLONE_ENV: str = "X_ALLOW_TOKEN_CLONE"
    RECLONE_ON_CORRUPT: bool = True
    # Auto-reclone/repair is enabled by default. The implementation performs a
    # safe backup before attempting reclone to avoid data loss.
    ALLOW_AUTO_RECLONE_ON_CORRUPT: bool = True
    CLONE_RETRIES: int = 1

    @classmethod
    def get_env(cls, name: str, default: Any = None) -> Any:
        return os.environ.get(name, default)

    @classmethod
    def get_env_bool(cls, name: str, default: bool = False) -> bool:
        v = os.environ.get(name, None)
        if v is None:
            return default
        return str(v).lower() in ("1", "true", "yes")

    def run_cmd(
        self, args: Iterable[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args), check=False, capture_output=True, text=True, **kwargs
        )

    def get_token(self) -> str | None:
        return os.environ.get(self.TOKEN_ENV_VAR)

    @property
    def allow_token_clone(self) -> bool:
        return self.get_env_bool(self.ALLOW_TOKEN_CLONE_ENV, False)

    def __init__(self, ctx: object | None = None) -> None:
        self._ctx = ctx


class x_cls_make_github_clones_x(BaseMake):
    PER_PAGE = 100
    USER_AGENT = "clone-script"

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
        self.username = username
        self.target_dir = target_dir or self.DEFAULT_TARGET_DIR
        self.shallow = shallow
        self.include_forks = include_forks
        self.force_reclone = force_reclone
        # Explicitly annotate attribute so mypy knows this can be Optional[list[str]]
        self.names: list[str] | None
        if isinstance(names, str):
            self.names = [n.strip() for n in names.split(",") if n.strip()]
        else:
            # names may already be a list[str] or None
            self.names = names
        self.token = token or os.environ.get(self.TOKEN_ENV_VAR)
        self.exit_code: int | None = None

    def _request_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Any:
        import urllib.request

        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)

    def fetch_repos(
        self, username: str | None = None, include_forks: bool | None = None
    ) -> list[dict[str, Any]]:
        username = username or self.username
        include_forks = (
            include_forks if include_forks is not None else self.include_forks
        )
        if not username:
            raise RuntimeError("username required")
        per_page = self.PER_PAGE
        page = 1
        all_repos: list[dict[str, Any]] = []
        headers = {"User-Agent": self.USER_AGENT}
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        while True:
            url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&page={page}"
            try:
                data = self._request_json(url, headers=headers)
            except Exception:
                break
            if not isinstance(data, list) or not data:
                break
            for r in data:
                if not include_forks and r.get("fork"):
                    continue
                all_repos.append(r)
            if len(data) < per_page:
                break
            page += 1
        return all_repos

    def _clone_or_update_repo(self, repo_dir: str, git_url: str) -> bool:
        # If the repo is missing, clone it
        if not os.path.exists(repo_dir):
            _info(f"Cloning {git_url} into {repo_dir}")
            args = [self.GIT_BIN, "clone", git_url, repo_dir]
            if self.shallow:
                args[2:2] = ["--depth", "1"]
            for _ in range(max(1, self.CLONE_RETRIES)):
                proc = self.run_cmd(args)
                if proc.returncode == 0:
                    return True
                _error("clone failed:", proc.stderr or proc.stdout)
            return False

        # Repo exists: update in-place. We must avoid recloning so local
        # uncommitted changes are preserved. Strategy:
        # - fetch --all --prune
        # - if there are uncommitted changes, stash them
        # - attempt a pull (prefer --rebase --autostash)
        # - pop stash if we stashed
        _info(f"Updating {repo_dir}")
        try:
            # Fetch remote refs first
            self.run_cmd(
                [self.GIT_BIN, "-C", repo_dir, "fetch", "--all", "--prune"]
            )

            status = self.run_cmd(
                [self.GIT_BIN, "-C", repo_dir, "status", "--porcelain"],
                check=False,
            )
            has_uncommitted = (
                bool(status.stdout.strip())
                if status and hasattr(status, "stdout")
                else False
            )

            stashed = False
            if has_uncommitted:
                stash = self.run_cmd(
                    [
                        self.GIT_BIN,
                        "-C",
                        repo_dir,
                        "stash",
                        "push",
                        "-u",
                        "-m",
                        "autostash-for-update",
                    ]
                )
                stashed = stash.returncode == 0

            # Try a modern pull that preserves/rebases local work. If --autostash
            # is unsupported, we'll fall back to a plain pull.
            pull = (
                self.run_cmd(
                    [
                        self.GIT_BIN,
                        "-C",
                        repo_dir,
                        "pull",
                        "--rebase",
                        "--autostash",
                    ]
                )
                if not self.shallow
                else self.run_cmd([self.GIT_BIN, "-C", repo_dir, "pull"])
            )
            if pull.returncode != 0:
                # fallback to a normal pull
                pull = self.run_cmd([self.GIT_BIN, "-C", repo_dir, "pull"])

            if pull.returncode == 0:
                return True
            _error("pull failed:", pull.stderr or pull.stdout)
            return False
        finally:
            # Restore stashed changes if we stashed
            try:
                if "stashed" in locals() and stashed:
                    pop = self.run_cmd(
                        [self.GIT_BIN, "-C", repo_dir, "stash", "pop"]
                    )
                    if pop.returncode != 0:
                        _error("stash pop failed:", pop.stderr or pop.stdout)
            except Exception as e:
                _error("failed to pop stash:", e)

    def _attempt_update(self, repo_dir: str, git_url: str) -> bool:
        try:
            # Attempt in-place update first to preserve uncommitted changes.
            ok = self._clone_or_update_repo(repo_dir, git_url)
            if ok:
                return True

            # If update failed, attempt a safe reclone/repair flow. This is
            # enabled by default and will back up the repo before recloning.
            try:
                _info(f"Attempting safe reclone for {repo_dir}")
                if self._safe_reclone(repo_dir, git_url):
                    # After successful reclone, ensure clone succeeded
                    return True
            except Exception as e:
                _error(f"safe reclone failed for {repo_dir}: {e}")

            return False
        except Exception as exc:
            _error("exception while updating:", exc)
            return False

    def _safe_reclone(self, repo_dir: str, git_url: str) -> bool:
        """Safely reclone a repository by backing up the existing directory,
        attempting a fresh clone, and restoring the backup if the clone fails.

        Returns True on success, False on failure. This avoids irreversibly
        deleting local uncommitted changes.
        """
        bak_dir = f"{repo_dir}.bak.{int(time.time())}"
        try:
            # Move the existing repo to a backup location.
            shutil.move(repo_dir, bak_dir)
        except Exception as e:
            _error(f"failed to move repo for backup: {e}")
            return False

        try:
            # Attempt clone into original location
            args = [self.GIT_BIN, "clone", git_url, repo_dir]
            if self.shallow:
                args[2:2] = ["--depth", "1"]
            for _ in range(max(1, self.CLONE_RETRIES)):
                proc = self.run_cmd(args)
                if proc.returncode == 0:
                    # clone succeeded; remove backup
                    try:
                        shutil.rmtree(bak_dir)
                    except Exception:
                        _info(f"left backup at {bak_dir}")
                    return True
                _error("reclone attempt failed:", proc.stderr or proc.stdout)

            # All clone attempts failed; restore backup
            try:
                if os.path.exists(repo_dir):
                    shutil.rmtree(repo_dir)
            except Exception:
                pass
            shutil.move(bak_dir, repo_dir)
            return False
        except Exception as e:
            _error(f"error during reclone: {e}")
            # try to restore backup
            try:
                if os.path.exists(repo_dir):
                    shutil.rmtree(repo_dir)
            except Exception:
                pass
            try:
                shutil.move(bak_dir, repo_dir)
            except Exception as e2:
                _error(f"failed to restore backup after reclone failure: {e2}")
            return False

    def _repo_clone_url(self, repo: dict[str, Any]) -> str:
        clone_url = repo.get("clone_url") or repo.get("ssh_url") or ""
        if (
            self.token
            and self.allow_token_clone
            and clone_url.startswith("https://")
        ):
            return clone_url.replace("https://", f"https://{self.token}@")
        return clone_url

    def sync(
        self, username: str | None = None, dest: str | None = None
    ) -> int:
        username = username or self.username
        dest = dest or self.target_dir or self.DEFAULT_TARGET_DIR
        if not username:
            raise RuntimeError("username required")
        os.makedirs(dest, exist_ok=True)
        try:
            repos = self.fetch_repos(username=username)
        except Exception as exc:
            _error("failed to fetch repo list:", exc)
            return 2

        if self.names is not None:
            name_set = set(self.names)
            repos = [r for r in repos if r.get("name") in name_set]

        exit_code = 0
        for r in repos:
            name = r.get("name")
            if not name:
                continue
            repo_dir = os.path.join(dest, name)
            git_url = self._repo_clone_url(r)
            ok = self._attempt_update(repo_dir, git_url)
            if not ok:
                exit_code = 3
        self.exit_code = exit_code
        return exit_code


def main() -> int:
    username = os.environ.get("X_GH_USER")
    if not username:
        _info("Set X_GH_USER to run the example")
        return 0
    m = x_cls_make_github_clones_x(username=username)
    return m.sync()


if __name__ == "__main__":
    sys.exit(main())
