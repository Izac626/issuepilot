"""Embedder 포트의 로컬 ONNX 모델 구현 (fastembed).

모델은 처음 쓸 때 한 번 내려받아 cache_dir에 둔다. 이슈 내용은 외부로 나가지 않는다.
"""
from __future__ import annotations

from pathlib import Path


class FastEmbedEmbedder:
    def __init__(self, model_name: str, cache_dir: Path | None = None) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from fastembed import TextEmbedding  # 무거운 의존성이라 실제로 쓸 때 불러온다

            self._model = TextEmbedding(
                self._model_name, cache_dir=str(self._cache_dir) if self._cache_dir else None)
        return [vector.tolist() for vector in self._model.embed(texts)]
