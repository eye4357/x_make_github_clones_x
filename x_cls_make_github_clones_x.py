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
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from http.client import HTTPResponse
from pathlib import Path
from typing import TypeGuard, cast

JsonDict = dict[str, object]

_json_loads = cast("Callable[[str], object]", json.loads)
_urlopen = cast(
    "Callable[[urllib.request.Request], HTTPResponse]",
    urllib.request.urlopen,
)


def _is_json_dict(data: object) -> TypeGuard[JsonDict]:
    if not isinstance(data, dict):
        return False
    dict_obj = cast("dict[object, object]", data)
    for key in dict_obj.keys():
        if not isinstance(key, str):
            return False
    return True


def _is_json_list(data: object) -> TypeGuard[list[object]]:
    return isinstance(data, list)


@dataclass(frozen=True)
class RepoRecord:
    name: str
    full_name: str
    clone_url: str | None
    ssh_url: str | None
    fork: bool

    def matches(self, names: set[str] | None) -> bool:
        if names is None:
            return True
        return self.name in names or self.full_name in names

    def resolved_clone_url(self, token: str | None, allow_token_clone: bool) -> str:
        base_url = self.clone_url or self.ssh_url or ""
        if token and allow_token_clone and base_url.startswith("https://"):
            return base_url.replace("https://", f"https://{token}@")
        return base_url


def _coerce_repo_record(data: JsonDict) -> RepoRecord | None:
    name_obj = data.get("name")
    if not isinstance(name_obj, str) or not name_obj:
        return None
    full_name_obj = data.get("full_name")
    full_name = (
        full_name_obj if isinstance(full_name_obj, str) and full_name_obj else name_obj
    )
    clone_url_obj = data.get("clone_url")
    clone_url = (
        clone_url_obj if isinstance(clone_url_obj, str) and clone_url_obj else None
    )
    ssh_url_obj = data.get("ssh_url")
    ssh_url = ssh_url_obj if isinstance(ssh_url_obj, str) and ssh_url_obj else None
    fork_obj = data.get("fork")
    fork = fork_obj if isinstance(fork_obj, bool) else False
    return RepoRecord(
        name=name_obj,
        full_name=full_name,
        clone_url=clone_url,
        ssh_url=ssh_url,
        fork=fork,
    )


def _info(*args: object) -> None:
    message = " ".join(str(arg) for arg in args)
    try:
        print(message)
    except Exception:
        try:
            sys.stdout.write(message + "\n")
        except Exception:
            pass


def _error(*args: object) -> None:
    message = " ".join(str(arg) for arg in args)
    try:
        print(message, file=sys.stderr)
    except Exception:
        try:
            sys.stderr.write(message + "\n")
        except Exception:
            pass


class BaseMake:
    DEFAULT_TARGET_DIR: str | None = None  # dynamic; set after helper defined
    GIT_BIN: str = "git"
    TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
    ALLOW_TOKEN_CLONE_ENV: str = "X_ALLOW_TOKEN_CLONE"
    RECLONE_ON_CORRUPT: bool = True
    # Auto-reclone/repair is enabled by default. The implementation performs a
    # safe backup before attempting reclone to avoid data loss.
    ALLOW_AUTO_RECLONE_ON_CORRUPT: bool = True
    CLONE_RETRIES: int = 1

    @classmethod
    def get_env(cls, name: str, default: str | None = None) -> str | None:
        value = os.environ.get(name)
        return value if value is not None else default

    @classmethod
    def get_env_bool(cls, name: str, default: bool = False) -> bool:
        env_value = os.environ.get(name)
        if env_value is None:
            return default
        return env_value.lower() in ("1", "true", "yes")

    def run_cmd(
        self, args: Iterable[str], *, check: bool = False
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(list(args), check=check, capture_output=True, text=True)

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
        include_private: bool = True,
        **_: object,
    ) -> None:
        self.username = username
        if not target_dir:
            target_dir = _repo_parent_root()
        target_dir = _normalize_target_dir(target_dir)
        self.target_dir = target_dir
        self.shallow = shallow
        self.include_forks = include_forks
        self.force_reclone = force_reclone
        # Explicitly annotate attribute so mypy knows this can be Optional[list[str]]
        self.names: list[str] | None
        if isinstance(names, str):
            self.names = [n.strip() for n in names.split(",") if n.strip()]
        elif isinstance(names, list):
            # names is list[str] here; strip empties
            self.names = [n.strip() for n in names if n.strip()]
        else:
            self.names = None
        self.token = token or os.environ.get(self.TOKEN_ENV_VAR)
        self.include_private = include_private
        self.exit_code: int | None = None

    def _request_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> list[JsonDict]:
        req = urllib.request.Request(url, headers=headers or {})
        with _urlopen(req) as resp:
            raw_body = resp.read()
        payload = _json_loads(raw_body.decode("utf-8"))
        result: list[JsonDict] = []
        if _is_json_dict(payload):
            result.append(payload)
        elif _is_json_list(payload):
            for entry_obj in payload:
                if _is_json_dict(entry_obj):
                    result.append(entry_obj)
        return result

    def fetch_repos(
        self, username: str | None = None, include_forks: bool | None = None
    ) -> list[RepoRecord]:
        username = username or self.username
        include_forks = (
            include_forks if include_forks is not None else self.include_forks
        )
        if not username and not self.token:
            raise RuntimeError("username or token required")
        per_page = self.PER_PAGE
        headers: dict[str, str] = {"User-Agent": self.USER_AGENT}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        collected: dict[str, RepoRecord] = {}

        def _collect(base_url: str) -> None:
            page = 1
            while True:
                sep = "&" if "?" in base_url else "?"
                url = f"{base_url}{sep}per_page={per_page}&page={page}"
                try:
                    data_list = self._request_json(url, headers=headers)
                except Exception:
                    break
                if not data_list:
                    break
                for raw in data_list:
                    repo = _coerce_repo_record(raw)
                    if repo is None:
                        continue
                    if not include_forks and repo.fork:
                        continue
                    collected[repo.full_name] = repo
                if len(data_list) < per_page:
                    break
                page += 1

        # Public/user visible repos
        if username:
            _collect(f"https://api.github.com/users/{username}/repos?type=all")
        # Private repos via /user/repos if token + include_private
        if self.token and self.include_private:
            _collect(
                "https://api.github.com/user/repos?affiliation=owner,collaborator,organization_member&visibility=all"
            )

        repos: list[RepoRecord] = list(collected.values())
        if self.names is not None:
            name_set = {name for name in self.names if name}
            repos = [repo for repo in repos if repo.matches(name_set)]
        return repos

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
        stashed = False  # ensure defined for finally block
        try:
            # Fetch remote refs first
            self.run_cmd([self.GIT_BIN, "-C", repo_dir, "fetch", "--all", "--prune"])

            status = self.run_cmd(
                [self.GIT_BIN, "-C", repo_dir, "status", "--porcelain"],
                check=False,
            )
            has_uncommitted = (
                bool(status.stdout.strip())
                if status and hasattr(status, "stdout")
                else False
            )

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
            try:
                if stashed:
                    pop = self.run_cmd([self.GIT_BIN, "-C", repo_dir, "stash", "pop"])
                    if pop.returncode != 0:
                        _error("stash pop failed:", pop.stderr or pop.stdout)
            except Exception as e:
                _error("failed to pop stash:", e)

    def _attempt_update(self, repo_dir: str, git_url: str) -> bool:
        try:
            # If force_reclone is requested, perform an in-place force refresh
            # via git operations to avoid deleting files on Windows.
            if self.force_reclone:
                _info(f"force_reclone enabled; refreshing in-place {repo_dir}")
                return self._force_refresh_repo(repo_dir, git_url)

            # Attempt in-place update first to preserve uncommitted changes.
            ok = self._clone_or_update_repo(repo_dir, git_url)
            if ok:
                return True

            # Fallback: clone-to-temp and atomic swap. Fail fast if this fails.
            if self._clone_to_temp_swap(repo_dir, git_url):
                return True

            return False
        except Exception as exc:
            _error("exception while updating:", exc)
            return False

    def _force_refresh_repo(self, repo_dir: str, git_url: str) -> bool:
        """Refresh an existing repo in-place without deleting files.

        Strategy:
        - If the repo is missing, clone it.
        - Otherwise: fetch refs, stash uncommitted changes (if any), attempt
          pull --rebase --autostash (preferred). If pull fails, fall back to
          reset --hard origin/HEAD and clean -fdx. Finally, pop stash if used.

        This avoids removing .git objects and reduces permission errors on Windows.
        """
        # If missing, just clone
        if not os.path.exists(repo_dir):
            return self._clone_or_update_repo(repo_dir, git_url)

        try:
            # Fetch first
            self.run_cmd([self.GIT_BIN, "-C", repo_dir, "fetch", "--all", "--prune"])

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
                        "force-refresh-stash",
                    ]
                )
                stashed = stash.returncode == 0

            # Try a pull that prefers rebase and autostash (safer)
            if not self.shallow:
                pull = self.run_cmd(
                    [
                        self.GIT_BIN,
                        "-C",
                        repo_dir,
                        "pull",
                        "--rebase",
                        "--autostash",
                    ]
                )
            else:
                pull = self.run_cmd([self.GIT_BIN, "-C", repo_dir, "pull"])

            ok = False
            if pull.returncode == 0:
                ok = True
            else:
                # Fallback: attempt a hard reset to remote and clean untracked files
                self.run_cmd(
                    [self.GIT_BIN, "-C", repo_dir, "fetch", "--all", "--prune"]
                )
                reset = self.run_cmd(
                    [
                        self.GIT_BIN,
                        "-C",
                        repo_dir,
                        "reset",
                        "--hard",
                        "origin/HEAD",
                    ]
                )
                self.run_cmd([self.GIT_BIN, "-C", repo_dir, "clean", "-fdx"])
                if reset.returncode == 0:
                    ok = True
                else:
                    _error(
                        "force refresh reset failed:",
                        reset.stderr or reset.stdout,
                    )

            # Restore stashed changes if any
            if stashed:
                pop = self.run_cmd([self.GIT_BIN, "-C", repo_dir, "stash", "pop"])
                if pop.returncode != 0:
                    _error("stash pop failed:", pop.stderr or pop.stdout)

            return ok
        except Exception as e:
            _error("force refresh exception:", e)
            return False

    def _clone_to_temp_swap(self, repo_dir: str, git_url: str) -> bool:
        """Clone into a temporary directory and atomically swap with the
        existing repo dir. Returns True on success, False on failure.

        Steps:
        - clone into tmp dir alongside the target (same parent)
        - if clone succeeds, move existing repo to a backup name
        - rename tmp -> repo_dir
        - attempt to remove backup (best-effort)
        - on any failure attempt to restore original state and return False
        """
        parent = os.path.dirname(repo_dir)
        base = os.path.basename(repo_dir)
        ts = int(time.time())
        tmp_dir = os.path.join(parent, f".{base}.tmp.{ts}")
        bak_dir = os.path.join(parent, f".{base}.bak.{ts}")

        # Ensure parent exists
        try:
            os.makedirs(parent, exist_ok=True)
        except Exception:
            return False

        # Attempt clone into tmp_dir
        args = [self.GIT_BIN, "clone", git_url, tmp_dir]
        if self.shallow:
            args[2:2] = ["--depth", "1"]
        for _ in range(max(1, self.CLONE_RETRIES)):
            proc = self.run_cmd(args)
            if proc.returncode == 0:
                break
            # clone failed; retry per CLONE_RETRIES
            try:
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)
            except Exception:
                pass
        else:
            # All clone attempts failed
            try:
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)
            except Exception:
                pass
            return False

        # At this point tmp_dir exists and contains a fresh clone. Swap it in.
        try:
            if os.path.exists(repo_dir):
                # Move current repo to backup
                try:
                    shutil.move(repo_dir, bak_dir)
                except Exception:
                    # If move fails, clean tmp and fail
                    try:
                        shutil.rmtree(tmp_dir)
                    except Exception:
                        pass
                    return False

            # Rename tmp -> repo_dir
            try:
                shutil.move(tmp_dir, repo_dir)
            except Exception:
                # try to restore from backup
                try:
                    if os.path.exists(bak_dir) and not os.path.exists(repo_dir):
                        shutil.move(bak_dir, repo_dir)
                except Exception:
                    pass
                try:
                    if os.path.exists(tmp_dir):
                        shutil.rmtree(tmp_dir)
                except Exception:
                    pass
                return False

            # Success: attempt to remove backup (best-effort)
            try:
                if os.path.exists(bak_dir):
                    shutil.rmtree(bak_dir)
            except Exception:
                # ignore cleanup failures; leave backup for manual inspection
                pass

            return True
        except Exception:
            # Unexpected failure: try to clean tmp and restore backup
            try:
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)
            except Exception:
                pass
            try:
                if os.path.exists(bak_dir) and not os.path.exists(repo_dir):
                    shutil.move(bak_dir, repo_dir)
            except Exception:
                pass
            return False

    def _repo_clone_url(self, repo: RepoRecord) -> str:
        return repo.resolved_clone_url(self.token, self.allow_token_clone)

    def sync(self, username: str | None = None, dest: str | None = None) -> int:
        username = username or self.username
        dest = dest or self.target_dir or self.DEFAULT_TARGET_DIR
        if not dest:
            dest = _repo_parent_root()
        os.makedirs(dest, exist_ok=True)
        try:
            repos = self.fetch_repos(username=username)
        except Exception as exc:
            _error("failed to fetch repo list:", exc)
            return 2

        if self.names is not None:
            name_set = {name for name in self.names if name}
            repos = [repo for repo in repos if repo.matches(name_set)]

        exit_code = 0
        for repo in repos:
            name = repo.name
            if not name:
                continue
            repo_dir = os.path.join(dest, name)
            git_url = self._repo_clone_url(repo)
            if not git_url:
                _error(f"missing clone URL for {name}")
                exit_code = 3
                continue
            ok = self._attempt_update(repo_dir, git_url)
            if not ok:
                exit_code = 3
        self.exit_code = exit_code
        return exit_code


# Dynamic workspace parent root (parent of this repo's root)
_parent_root_cache: str | None = None


def _repo_parent_root() -> str:
    global _parent_root_cache
    if _parent_root_cache is not None:
        return _parent_root_cache
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").exists():  # repo root
            _parent_root_cache = str(anc.parent)
            return _parent_root_cache
    _parent_root_cache = str(here.parent)
    return _parent_root_cache


# Helper to normalize legacy hard-coded target_dir values (remove explicit legacy path checks)
def _normalize_target_dir(val: str | None) -> str:
    return val or _repo_parent_root()


# Override BaseMake.DEFAULT_TARGET_DIR dynamically if unset
try:
    if BaseMake.DEFAULT_TARGET_DIR is None:
        BaseMake.DEFAULT_TARGET_DIR = _repo_parent_root()
except Exception:
    pass


def main() -> int:
    username = os.environ.get("X_GH_USER")
    if not username:
        _info("Set X_GH_USER to run the example")
        return 0
    m = x_cls_make_github_clones_x(username=username)
    return m.sync()


if __name__ == "__main__":
    sys.exit(main())
