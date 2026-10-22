import pytest

from app.github_import import GitHubImportError, parse_github_url


def test_parses_bare_repo_url():
    assert parse_github_url("https://github.com/pallets/flask") == ("pallets", "flask", None)


def test_parses_url_with_branch():
    assert parse_github_url("https://github.com/pallets/flask/tree/main") == ("pallets", "flask", "main")


def test_strips_git_suffix():
    assert parse_github_url("github.com/pallets/flask.git") == ("pallets", "flask", None)


def test_rejects_non_github():
    with pytest.raises(GitHubImportError):
        parse_github_url("https://gitlab.com/foo/bar")
    with pytest.raises(GitHubImportError):
        parse_github_url("not a url")
