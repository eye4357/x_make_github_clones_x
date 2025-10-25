# ruff: noqa: S101

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from x_make_github_clones_x import x_cls_make_github_clones_x
from x_make_github_clones_x.x_cls_make_github_clones_x import RepoRecord

GithubClonesRunner = x_cls_make_github_clones_x

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


EXPECTED_MISSING_EXIT = 3
EXPECTED_SUCCESS_EXIT = 0
EXPECTED_FETCH_ERROR_EXIT = 2
TEST_TOKEN_VALUE = "secrettoken"  # noqa: S105 - deterministic test credential


def _make_repo_record() -> RepoRecord:
    return RepoRecord(
        name="alpha",
        full_name="octocat/alpha",
        clone_url="https://example.invalid/octocat/alpha.git",
        ssh_url="git@example.invalid:octocat/alpha.git",
        fork=False,
    )


def _load_report(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return cast("dict[str, object]", raw)


def _get_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload[key]
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _get_dict_list(payload: dict[str, object], key: str) -> list[dict[str, object]]:
    value = payload[key]
    assert isinstance(value, list)
    dict_entries: list[dict[str, object]] = []
    for entry in value:
        assert isinstance(entry, dict)
        dict_entry = cast("dict[str, object]", entry)
        dict_entries.append(dict_entry)
    return dict_entries


def test_fetch_repos_filters_forks_and_names(monkeypatch: MonkeyPatch) -> None:
    client = GithubClonesRunner(username="octocat", names=["alpha"])

    def fake_request_json(
        _client: object,
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
        GithubClonesRunner,
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
    client = GithubClonesRunner(username="octocat", target_dir=str(tmp_path))
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: object,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        return [missing, repo_record]

    monkeypatch.setattr(
        GithubClonesRunner,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    attempts: list[tuple[Path, str]] = []

    def fake_attempt(
        _client: object,
        repo_dir: Path,
        git_url: str,
    ) -> bool:
        attempts.append((repo_dir, git_url))
        return True

    monkeypatch.setattr(
        GithubClonesRunner,
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
    payload = _load_report(report_path)

    exit_value = payload.get("exit_code")
    assert isinstance(exit_value, int)
    assert exit_value == EXPECTED_MISSING_EXIT

    summary = _get_dict(payload, "summary")
    missing_value = summary.get("missing_clone_url")
    assert isinstance(missing_value, int)
    assert missing_value == 1

    repos_entries = _get_dict_list(payload, "repos")
    first_repo = repos_entries[0]
    status_value = first_repo.get("status")
    assert isinstance(status_value, str)
    assert status_value == "missing_clone_url"


def test_sync_success(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_record = _make_repo_record()
    client = GithubClonesRunner(username="octocat", target_dir=str(tmp_path))
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: object,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        return [repo_record]

    monkeypatch.setattr(
        GithubClonesRunner,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    def fake_attempt(
        _client: object,
        repo_dir: Path,
        git_url: str,
    ) -> bool:
        assert repo_dir == tmp_path / repo_record.name
        assert git_url == repo_record.clone_url
        return True

    monkeypatch.setattr(
        GithubClonesRunner,
        "_attempt_update",
        fake_attempt,
        raising=True,
    )

    exit_code = client.sync()
    assert exit_code == EXPECTED_SUCCESS_EXIT
    assert client.exit_code == EXPECTED_SUCCESS_EXIT

    report_path = client.last_run_report_path
    assert report_path is not None
    payload = _load_report(report_path)

    summary = _get_dict(payload, "summary")
    successful_value = summary.get("successful")
    assert isinstance(successful_value, int)
    assert successful_value == 1

    repos_entries = _get_dict_list(payload, "repos")
    status_value = repos_entries[0].get("status")
    assert isinstance(status_value, str)
    assert status_value == "updated"


def test_sync_uses_token_when_allowed(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_record = _make_repo_record()
    monkeypatch.setenv(GithubClonesRunner.ALLOW_TOKEN_CLONE_ENV, "1")
    client = GithubClonesRunner(
        username="octocat",
        target_dir=str(tmp_path),
        token=TEST_TOKEN_VALUE,
    )
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: object,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        return [repo_record]

    monkeypatch.setattr(
        GithubClonesRunner,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    urls: list[str] = []

    def fake_attempt(
        _client: object,
        _repo_dir: Path,
        git_url: str,
    ) -> bool:
        urls.append(git_url)
        return True

    monkeypatch.setattr(
        GithubClonesRunner,
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
    payload = _load_report(report_path)

    summary = _get_dict(payload, "summary")
    successful_value = summary.get("successful")
    assert isinstance(successful_value, int)
    assert successful_value == 1

    repos_entries = _get_dict_list(payload, "repos")
    repo_entry = repos_entries[0]
    status_value = repo_entry.get("status")
    assert isinstance(status_value, str)
    assert status_value == "updated"
    used_token_value = repo_entry.get("used_token_clone")
    assert isinstance(used_token_value, bool)
    assert used_token_value is True


def test_sync_records_fetch_error(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    client = GithubClonesRunner(username="octocat", target_dir=str(tmp_path))
    client.set_report_base_dir(tmp_path)

    def fake_fetch(
        _client: object,
        _username: str | None = None,
        **_kwargs: object,
    ) -> list[RepoRecord]:
        message = "boom"
        raise RuntimeError(message)

    monkeypatch.setattr(
        GithubClonesRunner,
        "fetch_repos",
        fake_fetch,
        raising=True,
    )

    exit_code = client.sync()
    assert exit_code == EXPECTED_FETCH_ERROR_EXIT

    report_path = client.last_run_report_path
    assert report_path is not None
    payload = _load_report(report_path)

    exit_value = payload.get("exit_code")
    assert isinstance(exit_value, int)
    assert exit_value == EXPECTED_FETCH_ERROR_EXIT

    summary = _get_dict(payload, "summary")
    fetch_error_value = summary.get("fetch_error")
    assert isinstance(fetch_error_value, str)
    assert fetch_error_value == "boom"

    repos_entries = payload.get("repos")
    assert isinstance(repos_entries, list)
    assert repos_entries == []
