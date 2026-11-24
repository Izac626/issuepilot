"""유사 이슈 검색을 가짜 임베더로 검증한다. 모델을 내려받지 않는다."""
import pytest

from issuepilot.application.similarity import EmbeddingSimilarityFinder, cosine
from issuepilot.domain.models import ExistingIssue

VECTORS = {"새": [1.0, 0.0], "같음": [1.0, 0.1], "비슷": [1.0, 1.0], "다름": [0.0, 1.0], "반대": [-1.0, 0.0]}


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        return [VECTORS[t.split("\n")[0]] for t in texts]


class FakeCatalog:
    def __init__(self, issues):
        self.issues, self.asked = issues, None

    def list_existing(self, exclude_number, limit):
        self.asked = (exclude_number, limit)
        return self.issues[:limit]


def existing(*titles):
    return [ExistingIssue(number=i, title=t, body=f"{t} 본문 " * 100, state="closed" if i == 1 else "open")
            for i, t in enumerate(titles, start=1)]


def make(issue, titles, **kw):
    catalog, embedder = FakeCatalog(existing(*titles)), FakeEmbedder()
    return EmbeddingSimilarityFinder(catalog, embedder, **kw), catalog, embedder, issue.model_copy(
        update={"title": "새", "number": 99})


def test_orders_by_similarity_and_applies_threshold(issue):
    finder, catalog, _, new = make(issue, ["다름", "비슷", "같음"], min_similarity=0.5)
    found = finder.find_similar(new)
    assert [s.number for s in found] == [3, 2]          # "다름"(0.0)은 임계값 미만
    assert found[0].similarity > found[1].similarity
    assert catalog.asked == (99, 100)


def test_top_k_limits_candidates(issue):
    finder, _, _, new = make(issue, ["같음", "비슷", "같음"], top_k=1, min_similarity=0.0)
    assert [s.number for s in finder.find_similar(new)] == [1]   # 동점이면 번호가 작은 쪽


def test_carries_state_and_clipped_excerpt(issue):
    finder, _, _, new = make(issue, ["같음"], excerpt_chars=20)
    (found,) = finder.find_similar(new)
    assert found.state == "closed" and len(found.excerpt) == 20


def test_text_is_clipped_before_embedding(issue):
    finder, _, embedder, new = make(issue, ["같음"], max_chars=30)
    finder.find_similar(new)
    assert all(len(t) <= 30 for t in embedder.calls[0])


def test_no_existing_issues_skips_embedding(issue):
    finder, _, embedder, new = make(issue, [])
    assert finder.find_similar(new) == [] and embedder.calls == []


def test_only_earlier_issues_are_candidates(issue):
    catalog = FakeCatalog([ExistingIssue(number=120, title="같음"), ExistingIssue(number=99, title="같음"),
                           ExistingIssue(number=5, title="같음")])
    finder = EmbeddingSimilarityFinder(catalog, FakeEmbedder())
    assert [s.number for s in finder.find_similar(issue.model_copy(update={"title": "새", "number": 99}))] == [5]


def test_negative_similarity_is_dropped_not_crashing(issue):
    finder, _, _, new = make(issue, ["반대"], min_similarity=-1.0)
    assert finder.find_similar(new)[0].similarity == 0.0   # 모델 범위(0~1)로 고정


def test_cosine():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 1]) == 0.0
