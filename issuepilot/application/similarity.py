"""유사 이슈 검색: 기존 이슈를 임베딩해 새 이슈와 가까운 것을 고른다.

여기서 고른 것은 "후보"일 뿐이다. 중복 여부는 분류기가 본문을 읽고 판정한다.
임베딩 유사도만으로는 주제가 같은 다른 이슈와 진짜 중복을 가를 수 없기 때문이다
(docs/experiment_log.md 실험 #2).
"""
from __future__ import annotations

import math

from ..domain.models import IssueInput, SimilarIssue
from .ports import Embedder, IssueCatalog


def issue_text(title: str, body: str, max_chars: int) -> str:
    return f"{title}\n{body}"[:max_chars]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class EmbeddingSimilarityFinder:
    """SimilarIssueFinder 포트의 구현. IssueCatalog와 Embedder 포트에만 의존한다."""

    def __init__(self, catalog: IssueCatalog, embedder: Embedder, *, top_k: int = 3,
                 min_similarity: float = 0.30, pool_size: int = 100,
                 max_chars: int = 1000, excerpt_chars: int = 500) -> None:
        self._catalog = catalog
        self._embedder = embedder
        self._top_k = top_k
        self._min_similarity = min_similarity
        self._pool_size = pool_size
        self._max_chars = max_chars
        self._excerpt_chars = excerpt_chars

    def find_similar(self, issue: IssueInput) -> list[SimilarIssue]:
        # 중복은 "먼저 등록된 이슈"를 가리켜야 하므로 번호가 앞선 것만 본다 (재분석 때도 동일)
        existing = [e for e in self._catalog.list_existing(issue.number, self._pool_size)
                    if e.number < issue.number]
        if not existing:
            return []
        texts = [issue_text(issue.title, issue.body, self._max_chars)]
        texts += [issue_text(e.title, e.body, self._max_chars) for e in existing]
        query, *vectors = self._embedder.embed(texts)
        scored = sorted(((cosine(query, v), e) for v, e in zip(vectors, existing, strict=True)),
                        key=lambda pair: (-pair[0], pair[1].number))
        return [
            SimilarIssue(number=e.number, title=e.title, similarity=round(min(max(sim, 0.0), 1.0), 4),
                         state=e.state, excerpt=e.body[:self._excerpt_chars])
            for sim, e in scored[:self._top_k] if sim >= self._min_similarity
        ]
