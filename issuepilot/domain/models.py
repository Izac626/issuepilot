"""도메인 모델이자 포트 사이를 오가는 데이터 계약 (v1.2, 2026-11-26)

이 모듈은 pydantic 외의 외부 라이브러리와 다른 계층을 import하지 않는다.

규칙: 필드 추가만 허용. 삭제·타입 변경 시 SCHEMA_VERSION을 올리고
docs/02_아키텍처_인터페이스.md 변경 이력에 기록한다.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.2"

IssueType = Literal["bug", "feature", "question", "docs"]
Priority = Literal["P0", "P1", "P2"]
MissingInfo = Literal["repro_steps", "environment", "expected_behavior", "actual_behavior"]


# ---------- ① collector 출력 ----------
class IssueInput(BaseModel):
    number: int
    title: str
    body: str = ""
    author: str
    created_at: str  # ISO 8601


class RepoContext(BaseModel):
    repo: str                              # "owner/name"
    available_labels: list[str]            # 저장소에 실제 존재하는 라벨
    top_level_dirs: list[str]              # 예: ["src/auth", "src/api", "web", "docs"]
    recent_issue_numbers: list[int] = []   # 임베딩 저장소에 있는 이슈 번호


# ---------- ② retriever 입출력 ----------
class ExistingIssue(BaseModel):
    """저장소에 이미 있는 이슈. 유사 이슈 검색의 대상 (v1.2)."""
    number: int
    title: str
    body: str = ""
    state: Literal["open", "closed"] = "open"


class SimilarIssue(BaseModel):
    number: int
    title: str
    similarity: float = Field(ge=0, le=1)
    state: Literal["open", "closed"]
    excerpt: str = ""              # 본문 앞부분. 중복 판정 근거로 LLM에 전달 (v1.2)


# ---------- ③ classifier (LLM) 출력 ----------
class DuplicateJudgement(BaseModel):
    number: int
    is_duplicate: bool
    reason: str


class Classification(BaseModel):
    type: IssueType
    labels: list[str] = Field(max_length=3, description="available_labels 안에서만 선택")
    priority: Priority
    priority_reason: str
    affected_paths: list[str] = Field(max_length=3, description="top_level_dirs 기준 경로")
    summary_ko: str = Field(max_length=100)
    duplicates: list[DuplicateJudgement] = []
    missing_info: list[MissingInfo] = []   # type == "bug"일 때만 의미 있음


class RawClassification(BaseModel):
    """분류기(LLM)가 내놓는 원본 판단. 길이·허용값 제한은 domain.policy가 적용한다."""
    type: IssueType
    labels: list[str]
    priority: Priority
    priority_reason: str
    affected_paths: list[str]
    summary_ko: str
    duplicates: list[DuplicateJudgement]
    missing_info: list[MissingInfo]


class ClassifierUsage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    retries: int = 0
    truncated: bool = False


# ---------- ④ assigner 출력 ----------
class AssigneeCandidate(BaseModel):
    login: str
    commits_in_area: int
    open_issues: int
    score: float


class AssigneeRecommendation(BaseModel):
    candidates: list[AssigneeCandidate] = Field(max_length=2)
    reason: str


# ---------- ⑤ publisher 입력 ----------
class PilotResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    issue: IssueInput
    classification: Classification
    assignee: AssigneeRecommendation | None = None
    similar: list[SimilarIssue] = []   # 검색된 유사 이슈 후보 (v1.2)
    model: str                     # 사용한 모델 ID
    input_tokens: int
    output_tokens: int
    latency_ms: int
    retries: int = 0
    truncated: bool = False        # 본문이 길이 상한으로 잘렸는지 (v1.1)


# ---------- 평가셋 정답 행 ----------
class GoldRow(BaseModel):
    """eval/eval_set.csv 한 행. 컬럼 설명은 eval/eval_set_README.md 참고."""
    id: int
    title: str
    body: str
    gold_type: IssueType
    gold_labels: list[str]
    gold_priority: Priority
    gold_duplicate_of: int | None = None
    gold_missing_info: list[MissingInfo] = []
    gold_affected_path: str = ""
    source: Literal["manual", "fastapi", "streamlit"] = "manual"
