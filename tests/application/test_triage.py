"""유스케이스를 가짜 어댑터로 검증한다. 네트워크·API 호출 없음."""
from issuepilot.application.triage import TriageIssue
from issuepilot.domain.comment import MARKER
from issuepilot.domain.errors import ClassificationFailed
from issuepilot.domain.models import (
    AssigneeCandidate,
    AssigneeRecommendation,
    ClassifierUsage,
    SimilarIssue,
)


class FakeTracker:
    def __init__(self, issue, ctx):
        self.issue, self.ctx = issue, ctx
        self.labels, self.comments = [], []

    def fetch(self, issue_number):
        return self.issue, self.ctx

    def add_labels(self, issue_number, labels):
        self.labels += labels

    def upsert_comment(self, issue_number, body, marker):
        self.comments.append((body, marker))


class FakeClassifier:
    def __init__(self, raw=None, error=None):
        self.raw, self.error, self.seen_similar = raw, error, None

    def classify(self, issue, ctx, similar):
        self.seen_similar = similar
        if self.error:
            raise self.error
        return self.raw, ClassifierUsage(model="fake", input_tokens=10, output_tokens=5, latency_ms=1)


class FakeLog:
    def __init__(self):
        self.rows = []

    def append(self, result):
        self.rows.append(result)


def test_publishes_labels_and_comment(issue, ctx, raw):
    tracker, log = FakeTracker(issue, ctx), FakeLog()
    outcome = TriageIssue(tracker, FakeClassifier(raw(labels=["backend", "auth"])), result_log=log).run(7)
    assert outcome.ok
    assert tracker.labels == ["bug", "backend", "auth", "P1"]
    assert len(tracker.comments) == 1 and tracker.comments[0][1] == MARKER
    assert len(log.rows) == 1 and log.rows[0].model == "fake"


def test_untrusted_classifier_output_is_filtered(issue, ctx, raw):
    tracker = FakeTracker(issue, ctx)
    TriageIssue(tracker, FakeClassifier(raw(labels=["admin", "wontfix", "backend"]))).run(7)
    assert tracker.labels == ["bug", "backend", "P1"]


def test_dry_run_writes_nothing_to_tracker(issue, ctx, raw):
    tracker = FakeTracker(issue, ctx)
    outcome = TriageIssue(tracker, FakeClassifier(raw())).run(7, dry_run=True)
    assert outcome.ok and outcome.comment and tracker.labels == [] and tracker.comments == []


def test_failure_posts_failure_comment_without_labels(issue, ctx):
    tracker, log = FakeTracker(issue, ctx), FakeLog()
    outcome = TriageIssue(tracker, FakeClassifier(error=ClassificationFailed("본문 내용이 섞인 메시지")),
                          result_log=log).run(7)
    assert not outcome.ok and tracker.labels == [] and log.rows == []
    body = tracker.comments[0][0]
    assert "실패" in body and "본문 내용" not in body      # 예외 메시지는 코멘트에 노출하지 않는다


def test_optional_ports_are_used_when_present(issue, ctx, raw):
    sim = [SimilarIssue(number=3, title="비슷한 이슈", similarity=0.93, state="open")]

    class Finder:
        def find_similar(self, issue):
            return sim

    class Recommender:
        def recommend(self, affected_paths):
            assert affected_paths == ["src/auth"]
            return AssigneeRecommendation(
                candidates=[AssigneeCandidate(login="kim-dev", commits_in_area=7, open_issues=1, score=0.9)],
                reason="커밋 최다")

    tracker = FakeTracker(issue, ctx)
    classifier = FakeClassifier(raw(duplicates=[{"number": 3, "is_duplicate": True, "reason": "같은 증상"}]))
    outcome = TriageIssue(tracker, classifier, finder=Finder(), recommender=Recommender()).run(7)
    assert classifier.seen_similar == sim
    assert "#3" in outcome.comment and "kim-dev" in outcome.comment


class Boom:
    def find_similar(self, issue):
        raise RuntimeError("model download failed")

    def recommend(self, affected_paths):
        raise RuntimeError("api down")


def test_finder_or_recommender_failure_does_not_block_classification(issue, ctx, raw):
    tracker = FakeTracker(issue, ctx)
    outcome = TriageIssue(tracker, FakeClassifier(raw()), finder=Boom(), recommender=Boom()).run(7)
    assert outcome.ok and outcome.result.similar == [] and outcome.result.assignee is None
    assert len(tracker.comments) == 1 and "bug" in tracker.labels


def test_result_keeps_similar_candidates_and_comment_shows_similarity(issue, ctx, raw):
    class Finder:
        def find_similar(self, issue):
            return [SimilarIssue(number=3, title="t", similarity=0.72, state="open")]

    dup = raw(duplicates=[{"number": 3, "is_duplicate": True, "reason": "같은 원인"},
                          {"number": 99, "is_duplicate": True, "reason": "지어낸 번호"}])
    outcome = TriageIssue(FakeTracker(issue, ctx), FakeClassifier(dup), finder=Finder()).run(7, dry_run=True)
    assert [s.number for s in outcome.result.similar] == [3]
    assert "#3 (유사도 0.72)" in outcome.comment and "#99" not in outcome.comment
