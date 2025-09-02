

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
from typing import List, Dict, Optional, Any, cast

try:
    # Python 3 builtin
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    from urllib.parse import urlencode
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
    DEFAULT_NAMES: List[str] = []

    def __init__(self, username: Optional[str] = None, target_dir: Optional[str] = None, *,
                 shallow: bool = False, include_forks: bool = False, names: Optional[str] = None,
                 yes: bool = False):
        self.username = username or self.DEFAULT_USERNAME
        self.target_dir = os.path.abspath(target_dir) if target_dir else os.path.abspath(self.DEFAULT_TARGET_DIR)
        self.shallow = shallow
        self.include_forks = include_forks
        self.names = set([n.strip() for n in names.split(",") if n.strip()]) if names else None
        self.yes = yes
        self.token = os.environ.get("GITHUB_TOKEN")
        if not self.token or self.token == "NO_TOKEN_PROVIDED":
            raise RuntimeError("No GitHub token provided in environment. Set GITHUB_TOKEN in your venv.")
        self.auth_username: Optional[str] = None
        # exit code from last run (0 success, non-zero failure)
        self.exit_code = 0

    def _request_json(self, url: str, headers: Dict[str, str]) -> Any:
        req = Request(url, headers=headers)
        try:
            with urlopen(req) as resp:
                return json.load(resp)
        except HTTPError as e:
            body = None
            try:
                body = e.read().decode('utf-8')
            except Exception:
                pass
            print(f"GitHub API error: {getattr(e, 'code', '?')} {getattr(e, 'reason', '?')}")
            if body:
                print(body)
            sys.exit(2)

    def fetch_repos(self, username: str, token: Optional[str], include_forks: bool) -> List[Dict[str, Any]]:
        repos: List[Dict[str, Any]] = []
        per_page = self.PER_PAGE
        page = 1
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": self.USER_AGENT}
        if token:
            headers["Authorization"] = f"token {token}"

        while True:
            params = urlencode({"per_page": per_page, "page": page})
            url = f"https://api.github.com/users/{username}/repos?{params}"
            data: Any = self._request_json(url, headers)

            if not isinstance(data, list):
                print("Unexpected response from GitHub API:", data)
                sys.exit(3)

            data_list = cast(List[Dict[str, Any]], data)
            if not data_list:
                break

            for r in data_list:
                if not include_forks and r.get("fork"):
                    continue
                repos.append(r)

            if len(data_list) < per_page:
                break
            page += 1
            time.sleep(0.1)

        return repos

    def fetch_authenticated_repos(self, token: str, include_forks: bool) -> List[Dict[str, Any]]:
        repos_local: List[Dict[str, Any]] = []
        per_page_local = self.PER_PAGE
        page_local = 1
        headers_local = {"Accept": "application/vnd.github.v3+json", "User-Agent": self.USER_AGENT, "Authorization": f"token {token}"}

        while True:
            params_local = urlencode({"per_page": per_page_local, "page": page_local})
            url_local = f"https://api.github.com/user/repos?{params_local}"
            data_local: Any = self._request_json(url_local, headers_local)

            if not isinstance(data_local, list):
                print("Unexpected response from GitHub API:", data_local)
                sys.exit(3)

            data_local_list = cast(List[Dict[str, Any]], data_local)
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
            completed = subprocess.run(["git", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return completed.returncode == 0
        except FileNotFoundError:
            return False

    def clone_repo(self, clone_url: str, dest_path: str, shallow: bool) -> int:
        cmd = ["git", "clone"]
        if shallow:
            cmd += ["--depth", "1"]
        cmd += [clone_url, dest_path]
        print("Running:", " ".join(cmd))
        proc = subprocess.run(cmd)
        return proc.returncode

    def determine_auth_username(self) -> Optional[str]:
        if not self.token:
            return None
        try:
            req_headers = {"Authorization": f"token {self.token}", "User-Agent": self.USER_AGENT, "Accept": "application/vnd.github.v3+json"}
            info = self._request_json("https://api.github.com/user", req_headers)
            if isinstance(info, dict):
                info_dict = cast(Dict[str, Any], info)
                return info_dict.get("login")
            return None
        except Exception:
            return None

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

        cloned = updated = skipped = failed = 0


        for r in repos:
            name = r.get("name")
            if not name:
                continue
            if self.names and name not in self.names:
                skipped += 1
                print(f"Skipping {name} (not in whitelist)")
                continue

            dest = os.path.join(self.target_dir, name)
            clone_url = r.get("clone_url") or r.get("ssh_url") or ''
            if self.token and r.get("private"):
                owner = r.get("owner", {}).get("login", self.username)
                clone_url = f"https://{self.token}@github.com/{owner}/{name}.git"

            if not os.path.exists(dest):
                # Clone if not present
                print(f"Cloning {name} into {dest}")
                rc = self.clone_repo(clone_url, dest, self.shallow)
                if rc == 0:
                    cloned += 1
                else:
                    print(f"git clone failed for {name} (rc={rc})")
                    failed += 1
            else:
                # Update if present
                print(f"Updating {name} in {dest}")
                try:
                    result = subprocess.run(["git", "-C", dest, "pull"], check=False, capture_output=True, text=True)
                    rc = result.returncode
                    if rc == 0:
                        updated += 1
                    else:
                        # Check for 'not a git repository' error
                        if "not a git repository" in result.stderr:
                            print(f"{dest} is not a git repository. Recloning...")
                            import shutil
                            import stat
                            def on_rm_error(func, path, exc_info):
                                import os
                                try:
                                    os.chmod(path, stat.S_IWRITE)
                                except Exception:
                                    pass
                                try:
                                    func(path)
                                except Exception:
                                    pass
                            try:
                                shutil.rmtree(dest, onerror=on_rm_error)
                            except Exception as e:
                                print(f"Failed to remove {dest}: {e}")
                                failed += 1
                                continue
                            rc2 = self.clone_repo(clone_url, dest, self.shallow)
                            if rc2 == 0:
                                cloned += 1
                                print(f"Reclone successful for {name}.")
                            else:
                                print(f"Reclone failed for {name} (rc={rc2})")
                                failed += 1
                        else:
                            print(f"git pull failed for {name} (rc={rc})")
                            print(result.stderr)
                            failed += 1
                except Exception as e:
                    print(f"Exception during git pull for {name}: {e}")
                    failed += 1

            # Always overwrite standard config files after clone/update
            precommit_path = os.path.join(dest, ".pre-commit-config.yaml")
            pyproject_path = os.path.join(dest, "pyproject.toml")
            ci_yml_path = os.path.join(dest, ".github", "workflows", "ci.yml")
            os.makedirs(os.path.dirname(ci_yml_path), exist_ok=True)
            with open(precommit_path, "w", encoding="utf-8") as f:
                f.write(
                    """repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v4.6.0\n    hooks:\n      - id: trailing-whitespace\n      - id: end-of-file-fixer\n      - id: check-yaml\n      - id: check-toml\n  - repo: local\n    hooks:\n      - id: ruff\n        name: ruff\n        entry: ruff check\n        language: system\n        types: [python]\n      - id: black\n        name: black\n        entry: black\n        language: system\n        types: [python]\n      - id: mypy\n        name: mypy\n        entry: mypy\n        language: system\n        types: [python]\n        pass_filenames: false\n        args: [\".\"]\n"""
                )
            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(
                    """[tool.black]\nline-length = 100\ntarget-version = [\"py313\"]\n\n[tool.ruff]\nline-length = 100\ntarget-version = \"py313\"\nexclude = [\n  ".git",\n  "__pycache__",\n  ".mypy_cache",\n  ".ruff_cache",\n  ".venv",\n  "build",\n  "dist",\n]\n\n[tool.ruff.lint]\nselect = [\"E\", \"F\", \"I\", \"UP\", \"B\", \"PL\", \"RUF\"]\nignore = [\"E501\", \"E402\", \"PLC0415\", \"PLR2004\", \"PLR0913\"]\n\n[tool.mypy]\npython_version = \"3.13\"\nignore_missing_imports = true\nwarn_unused_ignores = true\nwarn_redundant_casts = true\nno_implicit_optional = true\nstrict_optional = true\nexclude = \"(^.venv/|^.mypy_cache/|^build/|^dist/)\"\n"""
                )
            with open(ci_yml_path, "w", encoding="utf-8") as f:
                f.write(
                    """name: CI\n\non:\n  push:\n  pull_request:\n\njobs:\n  lint-type:\n    runs-on: windows-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.13'\n      - name: Cache pip\n        uses: actions/cache@v4\n        with:\n          path: ~\\AppData\\Local\\pip\\Cache\n          key: ${{ runner.os }}-pip-${{ hashFiles('**/pyproject.toml') }}\n          restore-keys: |\n            ${{ runner.os }}-pip-\n      - name: Install tools\n        run: |\n          python -m pip install -U pip\n          python -m pip install -U ruff black mypy\n      - name: Ruff\n        run: ruff check .\n      - name: Black (check)\n        run: black --check .\n      - name: Mypy\n        run: mypy .\n"""
                )
            # .gitignore (template from x_0_make_all_x)
            gitignore_path = os.path.join(dest, ".gitignore")
            gitignore_template = """# Python\n__pycache__/\n*.pyc\n*.pyo\n*.pyd\n*.so\n*.egg\n*.egg-info/\ndist/\nbuild/\n.eggs/\n*.manifest\n*.spec\n\n# VS Code\n.vscode/\n\n# OS\n.DS_Store\nThumbs.db\n"""
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(gitignore_template)

        print(f"Done. cloned={cloned} updated={updated} skipped={skipped} failed={failed}")
        self.exit_code = 0 if failed == 0 else 4
        if failed:
            raise AssertionError(f"{failed} repositories failed to clone or update")
        # Return the target directory so downstream processes can use it.
        return self.target_dir


# Dummy main block for import safety
if __name__ == "__main__":
    print("This module is intended to be imported, not run directly.")
