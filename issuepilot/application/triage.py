"""유스케이스: 이슈 하나를 분석해 라벨과 코멘트를 게시한다."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..domain import comment, policy
from ..domain.errors import ClassificationFailed
from ..domain.models import AssigneeRecommendation, IssueInput, PilotResult, SimilarIssue
from .ports import AssigneeRecommender, IssueClassifier, IssueTracker, ResultLog, SimilarIssueFinder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TriageOutcome:
    ok: bool
    labels: list[str]
    comment: str
    result: PilotResult | None = None


class TriageIssue:
    def __init__(self, tracker: IssueTracker, classifier: IssueClassifier,
                 finder: SimilarIssueFinder | None = None,
                 recommender: AssigneeRecommender | None = None,
                 result_log: ResultLog | None = None) -> None:
        self._tracker = tracker
        self._classifier = classifier
        self._finder = finder
        self._recommender = recommender
        self._log = result_log

    # 중복 탐지와 담당자 추천은 부가 기능이다. 실패해도 분류는 게시한다.
    def _find_similar(self, issue: IssueInput) -> list[SimilarIssue]:
        if not self._finder:
            return []
        try:
            return self._finder.find_similar(issue)
        except Exception as e:  # noqa: BLE001
            log.warning("유사 이슈 검색 실패, 중복 판정 없이 진행: %s", type(e).__name__)
            return []

    def _recommend(self, affected_paths: list[str]) -> AssigneeRecommendation | None:
        if not self._recommender:
            return None
        try:
            return self._recommender.recommend(affected_paths)
        except Exception as e:  # noqa: BLE001
            log.warning("담당자 추천 실패, 추천 없이 진행: %s", type(e).__name__)
            return None

    def run(self, issue_number: int, dry_run: bool = False) -> TriageOutcome:
        issue, ctx = self._tracker.fetch(issue_number)
        similar = self._find_similar(issue)

        try:
            raw, usage = self._classifier.classify(issue, ctx, similar)
        except ClassificationFailed as e:
            log.error("이슈 #%d 분류 실패: %s", issue_number, e)
            body = comment.render_failure(type(e).__name__)
            if not dry_run:
                self._tracker.upsert_comment(issue_number, body, comment.MARKER)
            return TriageOutcome(ok=False, labels=[], comment=body)

        classification = policy.normalize(raw, ctx, similar)
        assignee = self._recommend(classification.affected_paths)
        result = PilotResult(issue=issue, classification=classification, assignee=assignee,
                             similar=similar, **usage.model_dump())
        labels = policy.labels_to_apply(result, ctx.available_labels)
        body = comment.render_comment(result)

        if not dry_run:
            if labels:
                self._tracker.add_labels(issue_number, labels)
            self._tracker.upsert_comment(issue_number, body, comment.MARKER)
        if self._log:
            self._log.append(result)
        log.info("이슈 #%d %s: tokens=%d/%d latency=%dms retries=%d", issue_number,
                 "dry-run" if dry_run else "published", usage.input_tokens, usage.output_tokens,
                 usage.latency_ms, usage.retries)
        return TriageOutcome(ok=True, labels=labels, comment=body, result=result)
