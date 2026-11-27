"""신뢰할 수 없는 텍스트 처리.

이슈 제목·본문은 누구나 쓸 수 있는 입력이고, LLM이 만든 자유 서술 문장은
그 입력의 영향을 받는다. 두 방향 모두 여기서 정화한다.
"""
from __future__ import annotations

import re
import unicodedata

_TAG_NAMES = r"(new_issue|similar_issues|repo_context)"
# 공백을 끼우거나 전각 꺾쇠를 쓴 변형까지 잡는다
_PROMPT_TAGS = re.compile(rf"[<＜]\s*/?\s*{_TAG_NAMES}\s*[>＞]", re.IGNORECASE)
_HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)   # 닫히지 않은 주석은 끝까지
_HTML = re.compile(r"<!--.*?(?:-->|\Z)|<[^>]{0,500}>", re.DOTALL)
_URL = re.compile(r"(?:[a-z][a-z0-9+.\-]{1,15}://|www\.)\S+", re.IGNORECASE)
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_WS = re.compile(r"\s+")
_ISSUE_REF = re.compile(r"#(?=\d)")
ZWSP = "\u200b"


def clip(text: str, limit: int) -> tuple[str, bool]:
    """limit 글자로 자른다. (결과, 잘렸는지)"""
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def strip_invisible(text: str) -> str:
    """화면에 보이지 않는 문자를 지운다 (제어 문자, 폭 없는 문자, 방향 전환, 유니코드 태그).

    사람 눈에 안 보이는 글자로 지시를 숨기거나 표시 순서를 뒤집는 것을 막는다.
    """
    return "".join(ch for ch in text
                   if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf", "Co", "Cs"))


def for_prompt(text: str) -> str:
    """프롬프트에 넣을 이슈 텍스트.

    - 구획 태그를 흉내 낸 문자열 무력화
    - HTML 주석과 보이지 않는 문자 제거: 모델은 사람이 화면에서 보는 것만 본다
    """
    text = _HTML_COMMENT.sub("", strip_invisible(text))
    return _PROMPT_TAGS.sub("[tag]", text)


def for_comment(text: str, limit: int = 200) -> str:
    """LLM이 만든 문장을 GitHub 코멘트에 넣기 전에 정화한다.

    - 줄바꿈과 표 구분자 제거 (표·마크다운 구조 깨짐 방지)
    - HTML, 링크, URL 제거 후 남은 꺾쇠와 &는 엔티티로 바꿈 (피싱 링크·숨은 마커·주석 방지)
    - @멘션과 #이슈 참조 무력화 (임의 사용자 호출, 다른 저장소에 역참조 남기기 방지)
    - 보이지 않는 문자 제거
    """
    text = _WS.sub(" ", strip_invisible(text))   # 줄바꿈을 낀 태그도 한 줄로 만든 뒤 지운다
    text = _MD_LINK.sub(r"\1", text)
    text = _HTML.sub("", text)
    text = _URL.sub("[링크 생략]", text)
    text = text.replace("|", "/").replace("`", "'")
    text = _WS.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("@", "@" + ZWSP)
    return _ISSUE_REF.sub("#" + ZWSP, text)
