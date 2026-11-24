"""분석 코멘트 본문 생성. 외부 입출력 없음."""
from __future__ import annotations

from .models import PilotResult
from .text import for_comment

MARKER = "<!-- issue-pilot -->"

MISSING_KO = {
    "repro_steps": "문제를 다시 일으키는 구체적인 절차",
    "environment": "실행 환경 (브라우저, OS, 버전 등)",
    "expected_behavior": "원래 기대한 동작",
    "actual_behavior": "실제로 일어난 동작",
}
TYPE_KO = {"bug": "버그", "feature": "기능 요청", "question": "질문", "docs": "문서"}


def render_comment(result: PilotResult) -> str:
    c = result.classification
    lines = [
        MARKER,
        "### 🤖 IssuePilot 자동 분석",
        "",
        f"**요약** {for_comment(c.summary_ko, 120)}",
        "",
        "| 항목 | 결과 |",
        "|---|---|",
        f"| 유형 | {TYPE_KO[c.type]} (`{c.type}`) |",
        f"| 영역 | {', '.join(f'`{l}`' for l in c.labels) or '판단 보류'} |",
        f"| 우선순위 | **{c.priority}** — {for_comment(c.priority_reason)} |",
        f"| 영향 영역 | {', '.join(f'`{p}`' for p in c.affected_paths) or '판단 보류'} |",
    ]
    dups = [d for d in c.duplicates if d.is_duplicate]
    if dups:
        similarity = {s.number: s.similarity for s in result.similar}
        lines += ["", "**중복 가능성** (자동으로 닫지 않습니다)"]
        for d in dups:
            score = f" (유사도 {similarity[d.number]:.2f})" if d.number in similarity else ""
            lines.append(f"- #{d.number}{score} — {for_comment(d.reason)}")
    if result.assignee and result.assignee.candidates:
        lines += ["", "**담당자 추천** (자동 지정하지 않습니다)"]
        lines += [f"- `{for_comment(a.login, 40)}` — 해당 영역 커밋 {a.commits_in_area}건, 열린 이슈 {a.open_issues}건"
                  for a in result.assignee.candidates]
    if c.missing_info:
        lines += ["", f"@{result.issue.author} 님, 빠른 확인을 위해 아래 정보를 추가해 주시면 감사하겠습니다."]
        lines += [f"- [ ] {MISSING_KO[m]}" for m in c.missing_info]
    if result.truncated:
        lines += ["", "<sub>본문이 길어 앞부분만 분석했습니다.</sub>"]
    lines += ["", f"<sub>자동 생성된 분석이며 틀릴 수 있습니다. 라벨은 자유롭게 수정해 주세요. · {result.model}</sub>"]
    return "\n".join(lines)


def render_failure(reason: str) -> str:
    return (f"{MARKER}\n### 🤖 IssuePilot\n자동 분석에 실패했습니다. 수동으로 분류해 주세요.\n\n"
            f"<sub>{for_comment(reason, 60)}</sub>")
