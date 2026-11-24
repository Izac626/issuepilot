"""분류 결과에 적용하는 업무 규칙. 외부 입출력 없음.

LLM의 판단은 신뢰하지 않는다. 저장소에 실제로 있는 라벨·폴더, 검색으로 찾은
이슈 번호만 통과시키고 나머지는 버린다.
"""
from __future__ import annotations

from .models import Classification, PilotResult, RawClassification, RepoContext, SimilarIssue

NON_AREA_LABELS = frozenset({"bug", "feature", "question", "P0", "P1", "P2"})
MAX_LABELS = 3
MAX_PATHS = 3
MAX_SUMMARY_CHARS = 100


def area_labels(ctx: RepoContext) -> list[str]:
    """유형·우선순위 라벨을 뺀, 영역 라벨 후보."""
    return [l for l in ctx.available_labels if l not in NON_AREA_LABELS]


def normalize(raw: RawClassification, ctx: RepoContext, similar: list[SimilarIssue]) -> Classification:
    allowed = area_labels(ctx)
    known_numbers = {s.number for s in similar}
    return Classification(
        type=raw.type,
        labels=[l for l in dict.fromkeys(raw.labels) if l in allowed][:MAX_LABELS],
        priority=raw.priority,
        priority_reason=raw.priority_reason,
        affected_paths=[p for p in dict.fromkeys(raw.affected_paths) if p in ctx.top_level_dirs][:MAX_PATHS],
        summary_ko=raw.summary_ko[:MAX_SUMMARY_CHARS],
        duplicates=[d for d in raw.duplicates if d.number in known_numbers],
        missing_info=list(dict.fromkeys(raw.missing_info)) if raw.type == "bug" else [],
    )


def labels_to_apply(result: PilotResult, available: list[str]) -> list[str]:
    """이슈에 붙일 라벨. 저장소에 존재하는 것만."""
    c = result.classification
    return [l for l in dict.fromkeys([c.type, *c.labels, c.priority]) if l in available]
