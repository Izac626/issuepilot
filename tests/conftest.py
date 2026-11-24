import os

import pytest

from issuepilot.domain.models import Classification, IssueInput, PilotResult, RawClassification, RepoContext


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="RUN_LIVE=1일 때만 실행")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def ctx() -> RepoContext:
    return RepoContext(
        repo="owner/repo",
        available_labels=["bug", "feature", "question", "docs", "backend", "frontend", "auth", "P0", "P1", "P2"],
        top_level_dirs=["src/auth", "src/api", "web", "docs"],
    )


@pytest.fixture
def issue() -> IssueInput:
    return IssueInput(number=7, title="로그인이 안 됩니다", body="본문", author="alice",
                      created_at="2026-11-24T00:00:00+09:00")


@pytest.fixture
def result(issue) -> PilotResult:
    c = Classification(type="bug", labels=["backend", "auth"], priority="P1", priority_reason="주요 기능 장애",
                       affected_paths=["src/auth"], summary_ko="로그인 실패", missing_info=["environment"])
    return PilotResult(issue=issue, classification=c, model="test-model",
                       input_tokens=10, output_tokens=5, latency_ms=1)


@pytest.fixture
def raw():
    def make(**over) -> RawClassification:
        base = dict(type="bug", labels=["backend"], priority="P1", priority_reason="r",
                    affected_paths=["src/auth"], summary_ko="s", duplicates=[], missing_info=[])
        return RawClassification(**{**base, **over})
    return make
