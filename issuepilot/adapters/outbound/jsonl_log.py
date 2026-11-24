"""ResultLog 포트의 JSON Lines 파일 구현."""
from __future__ import annotations

import logging
from pathlib import Path

from ...domain.models import PilotResult

log = logging.getLogger(__name__)


class JsonlResultLog:
    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, result: PilotResult) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(result.model_dump_json() + "\n")
        except OSError as e:   # 로그 실패가 게시 결과를 막지 않게 한다
            log.warning("분류 로그 저장 실패: %s", e)
