# ruff: noqa: S101

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from x_make_github_clones_x.x_cls_make_github_clones_x import (
    RepoRecord,
    x_cls_make_github_clones_x,
)

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


EXPECTED_MISSING_EXIT = 3
EXPECTED_SUCCESS_EXIT = 0
TEST_TOKEN_VALUE = "secrettoken"  # noqa: S105 - deterministic test credential


def _make_repo_record() -> RepoRecord:
    return RepoRecord(
        name="alpha",
        full_name="octocat/alpha",
        clone_url="https://example.invalid/octocat/alpha.git",
        ssh_url="git@example.invalid:octocat/alpha.git",
        fork=False,
    )


def test_fetch_repos_filters_forks_and_names(monkeypatch: MonkeyPatch) -> None:
    client = x_cls_make_github_clones_x(username="octocat", names=["alpha"])

    def fake_request_json(
        _client: x_cls_make_github_clones_x,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> list[dict[str, object]]:
        assert "per_page" in url
        assert headers is not None
        assert headers.get("User-Agent") == client.USER_AGENT
        return [
            {
                "name": "alpha",
                "full_name": "octocat/alpha",
                "clone_url": "https://example.invalid/octocat/alpha.git",
                "fork": False,
            },
            {
                "name": "beta",
                "full_name": "octocat/beta",
                "clone_url": "https://example.invalid/octocat/beta.git",
                "fork": True,
            },
        ]

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "_request_json",
        fake_request_json,
        raising=True,
    )

    repos = client.fetch_repos()
    assert [repo.name for repo in repos] == ["alpha"]


def test_sync_reports_missing_clone_url(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_record = _make_repo_record()
    missing = RepoRecord(
        name="empty",
        full_name="octocat/empty",
        clone_url=None,
        ssh_url=None,
        fork=False,
    )
    client = x_cls_make_github_clones_x(username="octocat", target_dir=str(tmp_path))
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: x_cls_make_github_clones_x,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        return [missing, repo_record]

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    attempts: list[tuple[Path, str]] = []

    def fake_attempt(
        _client: x_cls_make_github_clones_x,
        repo_dir: Path,
        git_url: str,
    ) -> bool:
        attempts.append((repo_dir, git_url))
        return True

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "_attempt_update",
        fake_attempt,
        raising=True,
    )

    exit_code = client.sync()
    assert exit_code == EXPECTED_MISSING_EXIT
    assert client.exit_code == EXPECTED_MISSING_EXIT

    assert attempts == [(tmp_path / repo_record.name, repo_record.clone_url)]

    report_path = client.last_run_report_path
    assert report_path is not None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == EXPECTED_MISSING_EXIT
    assert payload["summary"]["missing_clone_url"] == 1
    repos_entry = payload["repos"][0]
    assert repos_entry["status"] == "missing_clone_url"


def test_sync_success(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_record = _make_repo_record()
    client = x_cls_make_github_clones_x(username="octocat", target_dir=str(tmp_path))
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: x_cls_make_github_clones_x,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        return [repo_record]

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    def fake_attempt(
        _client: x_cls_make_github_clones_x,
        repo_dir: Path,
        git_url: str,
    ) -> bool:
        assert repo_dir == tmp_path / repo_record.name
        assert git_url == repo_record.clone_url
        return True

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "_attempt_update",
        fake_attempt,
        raising=True,
    )

    exit_code = client.sync()
    assert exit_code == EXPECTED_SUCCESS_EXIT
    assert client.exit_code == EXPECTED_SUCCESS_EXIT

    report_path = client.last_run_report_path
    assert report_path is not None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["successful"] == 1
    assert payload["repos"][0]["status"] == "updated"


def test_sync_uses_token_when_allowed(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_record = _make_repo_record()
    monkeypatch.setenv(x_cls_make_github_clones_x.ALLOW_TOKEN_CLONE_ENV, "1")
    client = x_cls_make_github_clones_x(
        username="octocat",
        target_dir=str(tmp_path),
        token=TEST_TOKEN_VALUE,
    )
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: x_cls_make_github_clones_x,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        return [repo_record]

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    urls: list[str] = []

    def fake_attempt(
        _client: x_cls_make_github_clones_x,
        _repo_dir: Path,
        git_url: str,
    ) -> bool:
        urls.append(git_url)
        return True

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "_attempt_update",
        fake_attempt,
        raising=True,
    )

    exit_code = client.sync()
    assert exit_code == EXPECTED_SUCCESS_EXIT
    expected_url = f"https://{TEST_TOKEN_VALUE}@example.invalid/octocat/alpha.git"
    assert urls == [expected_url]

    report_path = client.last_run_report_path
    assert report_path is not None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["successful"] == 1
    repo_entry = payload["repos"][0]
    assert repo_entry["status"] == "updated"
    assert repo_entry["used_token_clone"] is True


def test_sync_records_fetch_error(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = x_cls_make_github_clones_x(username="octocat", target_dir=str(tmp_path))
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: x_cls_make_github_clones_x,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        x_cls_make_github_clones_x,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    exit_code = client.sync()
    assert exit_code == 2

    report_path = client.last_run_report_path
    assert report_path is not None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 2
    assert payload["summary"]["fetch_error"] == "boom"
    assert payload["repos"] == []
