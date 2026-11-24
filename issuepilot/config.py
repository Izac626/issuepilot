"""실행 설정. 모델·한도 관련 환경 변수는 여기서만 읽는다."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parent
load_dotenv(ROOT / ".env")

ALLOWED_EFFORTS = {"low", "medium", "high"}


@dataclass(frozen=True)
class Settings:
    model: str = "claude-opus-5-5"
    effort: str = "low"
    max_retries: int = 2
    max_output_tokens: int = 16000
    # 비용과 프롬프트 크기 상한. 넘는 부분은 잘라내고 코멘트에 알린다.
    max_title_chars: int = 300
    max_body_chars: int = 8000
    max_similar_excerpt_chars: int = 500
    log_path: Path = ROOT / "data" / "pilot_log.jsonl"
    # 유사 이슈 검색 (중복 후보). 임계값 근거는 docs/experiment_log.md 실험 #2
    embed_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embed_cache_dir: Path = ROOT / ".cache" / "fastembed"
    similar_top_k: int = 3
    similar_min_similarity: float = 0.30
    similar_pool_size: int = 100

    @property
    def has_api_key(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))


def load_settings() -> Settings:
    effort = os.environ.get("PILOT_EFFORT", "low")
    if effort not in ALLOWED_EFFORTS:
        raise SystemExit(f"PILOT_EFFORT는 {sorted(ALLOWED_EFFORTS)} 중 하나여야 합니다: {effort!r}")
    cache_dir = os.environ.get("PILOT_EMBED_CACHE")
    return Settings(
        model=os.environ.get("PILOT_MODEL", "claude-opus-5-5"), effort=effort,
        **({"embed_cache_dir": Path(cache_dir)} if cache_dir else {}),
    )
