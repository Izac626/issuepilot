"""담당자 추천 규칙. 외부 입출력 없음.

해당 영역을 많이 고쳐 본 사람을 우선하되, 이미 맡은 이슈가 많으면 순위를 낮춘다.
추천만 하고 지정하지 않는다 (요구사항 N6).
"""
from __future__ import annotations

from .models import AssigneeCandidate, AssigneeRecommendation

MAX_CANDIDATES = 2
LOAD_PENALTY = 0.2          # 열린 이슈 1건당 점수를 얼마나 깎을지
SECONDARY_PATH_WEIGHT = 0.5  # 2순위 이하 영향 폴더의 커밋 가중치


def is_bot(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith("[bot]") or lowered in {"github-actions", "dependabot", "web-flow"}


def recommend(commits_by_path: list[dict[str, int]],
              open_issues: dict[str, int]) -> AssigneeRecommendation | None:
    """commits_by_path: 영향 폴더 순서대로 {작성자: 커밋 수}. 첫 폴더가 가장 중요하다."""
    commits: dict[str, int] = {}
    weighted: dict[str, float] = {}
    for rank, counts in enumerate(commits_by_path):
        weight = 1.0 if rank == 0 else SECONDARY_PATH_WEIGHT
        for author, n in counts.items():
            if n <= 0 or is_bot(author):
                continue
            commits[author] = commits.get(author, 0) + n
            weighted[author] = weighted.get(author, 0.0) + n * weight
    if not weighted:
        return None
    candidates = [
        AssigneeCandidate(login=a, commits_in_area=commits[a], open_issues=open_issues.get(a, 0),
                          score=round(w / (1 + LOAD_PENALTY * open_issues.get(a, 0)), 3))
        for a, w in weighted.items()
    ]
    candidates.sort(key=lambda c: (-c.score, c.login))
    return AssigneeRecommendation(
        candidates=candidates[:MAX_CANDIDATES],
        reason="영향 폴더의 최근 커밋 수를 기준으로 하고, 열린 담당 이슈가 많을수록 순위를 낮췄습니다.",
    )
