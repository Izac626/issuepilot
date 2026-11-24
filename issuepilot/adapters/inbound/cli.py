"""인바운드 어댑터: 명령행과 GitHub Actions 환경 변수.

  python -m issuepilot --repo owner/name --issue 12 [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import re

from github import GithubException

from ...bootstrap import build_triage

log = logging.getLogger("issuepilot")


def parse_issue_number(raw: str | None) -> int | None:
    """환경 변수로 들어온 이슈 번호를 검증한다. ASCII 숫자가 아니면 None."""
    if raw and re.fullmatch(r"[1-9][0-9]{0,8}", raw):
        return int(raw)
    return None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="issuepilot")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    ap.add_argument("--issue", type=int, default=parse_issue_number(os.environ.get("ISSUE_NUMBER")))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.repo or not a.issue:
        ap.error("--repo와 --issue가 필요합니다")
    try:
        outcome = build_triage(a.repo).run(a.issue, dry_run=a.dry_run)
    except GithubException as e:
        log.error("GitHub API 오류: %s %s", e.status, (e.data or {}).get("message", ""))
        return 2
    print(f"labels={outcome.labels}\n\n{outcome.comment}")
    return 0 if outcome.ok else 1
