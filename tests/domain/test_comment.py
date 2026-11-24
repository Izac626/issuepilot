from issuepilot.domain.comment import MARKER, render_comment, render_failure
from issuepilot.domain.text import ZWSP


def test_comment_has_marker_and_sections(result):
    body = render_comment(result)
    assert body.startswith(MARKER)
    assert "**P1**" in body and "`src/auth`" in body
    assert "@alice" in body and "실행 환경" in body


def test_comment_sanitizes_model_text(result):
    result.classification.summary_ko = "요약 @victim https://evil.example <!-- issue-pilot -->"
    result.classification.priority_reason = "이유 | 표 깨기\n### 가짜 제목"
    body = render_comment(result)
    assert "@victim" not in body and f"@{ZWSP}victim" in body
    assert "evil.example" not in body
    assert body.count(MARKER) == 1
    assert "\n### 가짜 제목" not in body


def test_comment_notes_truncation(result):
    result.truncated = True
    assert "앞부분만 분석" in render_comment(result)


def test_failure_comment_is_sanitized():
    body = render_failure("APIError @x https://evil.example")
    assert body.startswith(MARKER) and "evil.example" not in body and "@x" not in body
