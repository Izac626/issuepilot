import pytest
from pydantic import ValidationError

from issuepilot.domain import policy
from issuepilot.domain.models import SimilarIssue


def test_area_labels_exclude_type_and_priority(ctx):
    assert policy.area_labels(ctx) == ["docs", "backend", "frontend", "auth"]


def test_normalize_keeps_only_known_labels_and_paths(ctx, raw):
    c = policy.normalize(raw(labels=["backend", "bug", "P0", "made-up", "backend"],
                             affected_paths=["src/auth", "../../etc", "src/auth"]), ctx, [])
    assert c.labels == ["backend"] and c.affected_paths == ["src/auth"]


def test_normalize_caps_lists_and_summary(ctx, raw):
    ctx.available_labels += ["a", "b", "c", "d"]
    c = policy.normalize(raw(labels=["a", "b", "c", "d"], summary_ko="가" * 300), ctx, [])
    assert len(c.labels) == 3 and len(c.summary_ko) == 100


def test_normalize_drops_duplicates_not_in_retrieved_set(ctx, raw):
    sim = [SimilarIssue(number=3, title="t", similarity=0.9, state="open")]
    r = raw(duplicates=[{"number": 3, "is_duplicate": True, "reason": "같음"},
                        {"number": 999, "is_duplicate": True, "reason": "지어낸 번호"}])
    assert [d.number for d in policy.normalize(r, ctx, sim).duplicates] == [3]


def test_normalize_missing_info_only_for_bugs(ctx, raw):
    assert policy.normalize(raw(type="feature", missing_info=["environment"]), ctx, []).missing_info == []
    assert policy.normalize(raw(missing_info=["environment"] * 2), ctx, []).missing_info == ["environment"]


def test_raw_classification_rejects_invalid_enum(raw):
    with pytest.raises(ValidationError):
        raw(priority="P9")


def test_labels_to_apply_only_existing_ones(result):
    assert policy.labels_to_apply(result, ["bug", "auth", "P1", "other"]) == ["bug", "auth", "P1"]
