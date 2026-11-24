"""IssueClassifier 포트의 Anthropic(Claude) 구현."""
from __future__ import annotations

import time
from pathlib import Path

import anthropic
from pydantic import ValidationError

from ...config import Settings
from ...domain import policy, text
from ...domain.errors import ClassificationFailed
from ...domain.models import ClassifierUsage, IssueInput, RawClassification, RepoContext, SimilarIssue

SYSTEM_PROMPT = (Path(__file__).resolve().parent / "prompts" / "system.md").read_text(encoding="utf-8")


def build_context_block(ctx: RepoContext) -> str:
    return (
        f"<repo_context>\n저장소: {ctx.repo}\n"
        f"영역 라벨: {', '.join(policy.area_labels(ctx))}\n"
        f"폴더: {', '.join(ctx.top_level_dirs)}\n</repo_context>"
    )


def build_issue_block(issue: IssueInput, similar: list[SimilarIssue], settings: Settings) -> tuple[str, bool]:
    """사용자 메시지를 만든다. (메시지, 본문이 잘렸는지)"""
    title, _ = text.clip(issue.title, settings.max_title_chars)
    body, truncated = text.clip(issue.body, settings.max_body_chars)
    parts = []
    if similar:
        lines = []
        for s in similar:
            excerpt, _ = text.clip(s.excerpt, settings.max_similar_excerpt_chars)
            lines.append(f"- #{s.number} ({s.state}, 유사도 {s.similarity:.2f}): {text.for_prompt(s.title)}")
            if excerpt.strip():
                lines.append("  본문: " + " ".join(text.for_prompt(excerpt).split()))
        parts.append("<similar_issues>\n" + "\n".join(lines) + "\n</similar_issues>")
    parts.append(
        f"<new_issue>\n제목: {text.for_prompt(title)}\n\n본문:\n"
        f"{text.for_prompt(body) or '(본문 없음)'}"
        f"{' [이하 생략됨]' if truncated else ''}\n</new_issue>"
    )
    parts.append("위 새 이슈를 분류해 주세요.")
    return "\n\n".join(parts), truncated


class AnthropicClassifier:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None) -> None:
        self._settings = settings
        self._client = client or anthropic.Anthropic()

    def classify(self, issue: IssueInput, ctx: RepoContext,
                 similar: list[SimilarIssue]) -> tuple[RawClassification, ClassifierUsage]:
        s = self._settings
        system = [
            {"type": "text", "text": SYSTEM_PROMPT},
            {"type": "text", "text": build_context_block(ctx), "cache_control": {"type": "ephemeral"}},
        ]
        user_text, truncated = build_issue_block(issue, similar, s)
        tokens_in = tokens_out = 0
        last_error = ""
        start = time.monotonic()
        for attempt in range(s.max_retries + 1):
            try:
                resp = self._client.messages.parse(
                    model=s.model,
                    max_tokens=s.max_output_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user_text}],
                    output_config={"effort": s.effort},
                    output_format=RawClassification,
                )
            except ValidationError as e:
                last_error = f"schema validation ({e.error_count()} errors)"
                continue
            except anthropic.APIError as e:
                # SDK가 재시도한 뒤에도 실패한 경우. 요청 내용이 섞일 수 있어 종류만 남긴다.
                raise ClassificationFailed(type(e).__name__) from e
            usage = resp.usage
            tokens_in += usage.input_tokens + (usage.cache_read_input_tokens or 0) \
                + (usage.cache_creation_input_tokens or 0)
            tokens_out += usage.output_tokens
            if resp.stop_reason == "refusal":
                raise ClassificationFailed("model refused the request")
            if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
                last_error = f"stop_reason={resp.stop_reason}"
                continue
            return resp.parsed_output, ClassifierUsage(
                model=s.model, input_tokens=tokens_in, output_tokens=tokens_out,
                latency_ms=int((time.monotonic() - start) * 1000), retries=attempt, truncated=truncated)
        raise ClassificationFailed(f"no valid output after {s.max_retries + 1} attempts: {last_error}")
