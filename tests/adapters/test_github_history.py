from types import SimpleNamespace as NS

from issuepilot.adapters.outbound.github_history import GitHubContributionHistory
from issuepilot.adapters.outbound.github_tracker import GitHubIssueTracker


def commit(login=None, name="git-name"):
    return NS(author=NS(login=login) if login else None, commit=NS(author=NS(name=name)))


class FakeRepo:
    def __init__(self, commits=(), issues=()):
        self._commits, self._issues, self.calls = list(commits), list(issues), []

    def get_commits(self, path):
        self.calls.append(("commits", path))
        return iter(self._commits)

    def get_issues(self, **kw):
        self.calls.append(("issues", kw))
        return iter(self._issues)


def test_counts_by_login_or_git_author_name():
    repo = FakeRepo(commits=[commit("kim"), commit("kim"), commit(name="park-ops"), commit(name="")])
    assert GitHubContributionHistory(repo).commit_counts("src/api") == {"kim": 2, "park-ops": 1}


def test_commit_counts_are_cached_per_path():
    repo = FakeRepo(commits=[commit("kim")])
    history = GitHubContributionHistory(repo)
    history.commit_counts("web"), history.commit_counts("web"), history.commit_counts("docs")
    assert repo.calls == [("commits", "web"), ("commits", "docs")]


def test_commit_scan_is_bounded():
    repo = FakeRepo(commits=[commit("kim")] * 500)
    assert GitHubContributionHistory(repo).commit_counts("web") == {"kim": 100}


def test_open_issue_counts_by_assignee():
    issues = [NS(assignees=[NS(login="kim"), NS(login="lee")]), NS(assignees=[NS(login="kim")]), NS(assignees=[])]
    history = GitHubContributionHistory(FakeRepo(issues=issues))
    assert history.open_issue_counts() == {"kim": 2, "lee": 1}
    assert history.open_issue_counts() == {"kim": 2, "lee": 1}   # 두 번째는 캐시


def gh_issue(number, pr=False, state="open", body="b"):
    return NS(number=number, title=f"t{number}", body=body, state=state, pull_request=NS() if pr else None)


def test_list_existing_skips_prs_and_target_and_respects_limit():
    repo = FakeRepo(issues=[gh_issue(9), gh_issue(8, pr=True), gh_issue(7, state="closed"), gh_issue(6), gh_issue(5)])
    found = GitHubIssueTracker(repo).list_existing(exclude_number=9, limit=2)
    assert [(e.number, e.state) for e in found] == [(7, "closed"), (6, "open")]
    assert repo.calls[0][1] == {"state": "all", "sort": "created", "direction": "desc"}


def test_list_existing_clips_body_and_handles_empty():
    repo = FakeRepo(issues=[gh_issue(1, body="x" * 5000), gh_issue(2, body=None)])
    found = GitHubIssueTracker(repo).list_existing(exclude_number=0, limit=10)
    assert len(found[0].body) == 2000 and found[1].body == ""
