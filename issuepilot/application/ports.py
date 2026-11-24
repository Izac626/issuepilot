"""포트: 유스케이스가 바깥 세계에 요구하는 인터페이스.

어댑터는 이 Protocol을 구현한다. 유스케이스는 구현체를 모른다.
"""
from __future__ import annotations

from typing import Protocol

from ..domain.models import (
    AssigneeRecommendation,
    ClassifierUsage,
    ExistingIssue,
    IssueInput,
    PilotResult,
    RawClassification,
    RepoContext,
    SimilarIssue,
)


class IssueTracker(Protocol):
    """이슈 저장소 (예: GitHub)."""

    def fetch(self, issue_number: int) -> tuple[IssueInput, RepoContext]: ...
    def add_labels(self, issue_number: int, labels: list[str]) -> None: ...
    def upsert_comment(self, issue_number: int, body: str, marker: str) -> None:
        """marker가 들어 있는 기존 코멘트가 있으면 갱신하고, 없으면 새로 단다."""
        ...


class IssueClassifier(Protocol):
    """이슈를 읽고 원본 판단을 돌려준다 (예: LLM). 실패하면 ClassificationFailed."""

    def classify(self, issue: IssueInput, ctx: RepoContext,
                 similar: list[SimilarIssue]) -> tuple[RawClassification, ClassifierUsage]: ...


class SimilarIssueFinder(Protocol):
    def find_similar(self, issue: IssueInput) -> list[SimilarIssue]: ...


class IssueCatalog(Protocol):
    """저장소의 기존 이슈 목록. 최근 것부터."""

    def list_existing(self, exclude_number: int, limit: int) -> list[ExistingIssue]: ...


class Embedder(Protocol):
    """문장을 벡터로 바꾼다 (예: 로컬 임베딩 모델)."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ContributionHistory(Protocol):
    """누가 어느 폴더를 고쳐 왔는지, 지금 얼마나 맡고 있는지."""

    def commit_counts(self, path: str) -> dict[str, int]:
        """해당 폴더의 최근 커밋 수. {작성자: 건수}"""
        ...

    def open_issue_counts(self) -> dict[str, int]:
        """열린 이슈 담당 건수. {담당자: 건수}"""
        ...


class AssigneeRecommender(Protocol):
    def recommend(self, affected_paths: list[str]) -> AssigneeRecommendation | None: ...


class ResultLog(Protocol):
    def append(self, result: PilotResult) -> None: ...
