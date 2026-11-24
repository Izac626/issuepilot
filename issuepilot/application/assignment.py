"""담당자 추천: 이력을 모아 도메인 규칙에 넘긴다."""
from __future__ import annotations

from ..domain import assignment
from ..domain.models import AssigneeRecommendation
from .ports import ContributionHistory


class HistoryAssigneeRecommender:
    """AssigneeRecommender 포트의 구현. ContributionHistory 포트에만 의존한다."""

    def __init__(self, history: ContributionHistory) -> None:
        self._history = history

    def recommend(self, affected_paths: list[str]) -> AssigneeRecommendation | None:
        if not affected_paths:
            return None
        commits = [self._history.commit_counts(p) for p in affected_paths]
        if not any(commits):
            return None
        return assignment.recommend(commits, self._history.open_issue_counts())
