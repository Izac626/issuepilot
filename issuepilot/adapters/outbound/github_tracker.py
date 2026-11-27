"""IssueTracker 포트의 GitHub 구현."""
from __future__ import annotations

import os
import subprocess
from itertools import islice

from github import Auth, Github
from github.Repository import Repository

from ...domain.models import ExistingIssue, IssueInput, RepoContext

EXPAND_DIRS = {"src", "app", "apps", "packages", "lib"}   # 한 단계 더 펼칠 폴더
SKIP_DIRS = {"tests", "test", "node_modules"}
MAX_EXISTING_BODY_CHARS = 2000
MAX_SCANNED_ISSUES = 300   # PR이 섞여 나오므로 limit보다 넉넉히 훑되 상한을 둔다
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}


def is_own_comment(comment, marker: str) -> bool:
    """IssuePilot이 쓴 코멘트인가. 마커는 누구나 적을 수 있으므로 작성자도 확인한다.

    기본 토큰이면 봇 계정, 개인 토큰이면 저장소 구성원이 작성자다. 외부인이 마커를
    흉내 낸 코멘트를 갱신 대상으로 삼지 않는다.
    """
    if not (comment.body or "").startswith(marker):
        return False
    if comment.user.type == "Bot":
        return True
    return comment.raw_data.get("author_association") in TRUSTED_ASSOCIATIONS


def github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:  # 로컬 개발: gh CLI 로그인 토큰 사용
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("GitHub 토큰이 없습니다. GITHUB_TOKEN을 설정하거나 gh auth login을 실행하세요.") from None


def list_dirs(repo: Repository) -> list[str]:
    dirs: list[str] = []
    for item in repo.get_contents(""):
        if item.type != "dir" or item.name.startswith(".") or item.name in SKIP_DIRS:
            continue
        if item.name in EXPAND_DIRS:
            subs = [c.path for c in repo.get_contents(item.path)
                    if c.type == "dir" and not c.name.startswith((".", "_"))]
            dirs.extend(subs or [item.path])
        else:
            dirs.append(item.path)
    return dirs


class GitHubIssueTracker:
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    @property
    def repo(self) -> Repository:
        return self._repo

    @classmethod
    def connect(cls, repo_name: str) -> GitHubIssueTracker:
        return cls(Github(auth=Auth.Token(github_token())).get_repo(repo_name))

    def fetch(self, issue_number: int) -> tuple[IssueInput, RepoContext]:
        gh_issue = self._repo.get_issue(issue_number)
        issue = IssueInput(
            number=gh_issue.number,
            title=gh_issue.title,
            body=gh_issue.body or "",
            author=gh_issue.user.login,
            created_at=gh_issue.created_at.isoformat(),
        )
        ctx = RepoContext(
            repo=self._repo.full_name,
            available_labels=[l.name for l in self._repo.get_labels()],
            top_level_dirs=list_dirs(self._repo),
        )
        return issue, ctx

    def list_existing(self, exclude_number: int, limit: int) -> list[ExistingIssue]:
        """IssueCatalog 포트. 최근 이슈부터, PR과 대상 이슈는 뺀다."""
        found: list[ExistingIssue] = []
        recent = self._repo.get_issues(state="all", sort="created", direction="desc")
        for gh_issue in islice(recent, MAX_SCANNED_ISSUES):
            if gh_issue.pull_request is not None or gh_issue.number == exclude_number:
                continue
            found.append(ExistingIssue(
                number=gh_issue.number, title=gh_issue.title,
                body=(gh_issue.body or "")[:MAX_EXISTING_BODY_CHARS],
                state="closed" if gh_issue.state == "closed" else "open"))
            if len(found) >= limit:
                break
        return found

    def add_labels(self, issue_number: int, labels: list[str]) -> None:
        self._repo.get_issue(issue_number).add_to_labels(*labels)

    def upsert_comment(self, issue_number: int, body: str, marker: str) -> None:
        gh_issue = self._repo.get_issue(issue_number)
        existing = next((c for c in gh_issue.get_comments() if is_own_comment(c, marker)), None)
        if existing:
            existing.edit(body)
        else:
            gh_issue.create_comment(body)
