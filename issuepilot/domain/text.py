"""신뢰할 수 없는 텍스트 처리.

이슈 제목·본문은 누구나 쓸 수 있는 입력이고, LLM이 만든 자유 서술 문장은
그 입력의 영향을 받는다. 두 방향 모두 여기서 정화한다.
"""
from __future__ import annotations

import re

_PROMPT_TAGS = re.compile(r"</?\s*(new_issue|similar_issues|repo_context)\s*>", re.IGNORECASE)
_HTML = re.compile(r"<!--.*?-->|<[^>\n]{0,200}>", re.DOTALL)
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_WS = re.compile(r"\s+")
ZWSP = "\u200b"


def clip(text: str, limit: int) -> tuple[str, bool]:
    """limit 글자로 자른다. (결과, 잘렸는지)"""
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def for_prompt(text: str) -> str:
    """프롬프트에 넣을 이슈 텍스트. 구획 태그를 흉내 낸 문자열을 무력화한다."""
    return _PROMPT_TAGS.sub("[tag]", text)


def for_comment(text: str, limit: int = 200) -> str:
    """LLM이 만든 문장을 GitHub 코멘트에 넣기 전에 정화한다.

    - 줄바꿈과 표 구분자 제거 (표·마크다운 구조 깨짐 방지)
    - HTML, 링크, URL 제거 (피싱 링크·숨은 마커 방지)
    - @멘션 무력화 (임의 사용자 호출 방지)
    """
    text = _MD_LINK.sub(r"\1", text)
    text = _HTML.sub("", text)
    text = _URL.sub("[링크 생략]", text)
    text = text.replace("|", "/").replace("`", "'")
    text = text.replace("@", "@" + ZWSP)
    text = _WS.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
