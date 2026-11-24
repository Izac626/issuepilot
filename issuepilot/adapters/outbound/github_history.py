"""ContributionHistory 포트의 GitHub 구현. 커밋 API를 쓰므로 저장소를 복제하지 않는다."""
from __future__ import annotations

from collections import Counter
from itertools import islice

from github.Repository import Repository

MAX_COMMITS_PER_PATH = 100
MAX_OPEN_ISSUES = 300


class GitHubContributionHistory:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo
        self._commit_cache: dict[str, dict[str, int]] = {}
        self._open_cache: dict[str, int] | None = None

    def commit_counts(self, path: str) -> dict[str, int]:
        if path not in self._commit_cache:
            counts: Counter[str] = Counter()
            for commit in islice(self._repo.get_commits(path=path), MAX_COMMITS_PER_PATH):
                # GitHub 계정과 연결된 커밋이면 로그인, 아니면 git 작성자 이름
                name = commit.author.login if commit.author else commit.commit.author.name
                if name:
                    counts[name] += 1
            self._commit_cache[path] = dict(counts)
        return self._commit_cache[path]

    def open_issue_counts(self) -> dict[str, int]:
        if self._open_cache is None:
            counts: Counter[str] = Counter()
            for issue in islice(self._repo.get_issues(state="open"), MAX_OPEN_ISSUES):
                for assignee in issue.assignees:
                    counts[assignee.login] += 1
            self._open_cache = dict(counts)
        return self._open_cache
