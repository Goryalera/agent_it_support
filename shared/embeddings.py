"""Эмбеддинги через локальную модель sentence-transformers.

Работает офлайн (после первой загрузки весов). Размерность вектора задаётся
выбранной моделью и должна совпадать с полем `knn_vector` в индексе OpenSearch
(см. config.EMBEDDING_DIM).
"""

from __future__ import annotations

from functools import lru_cache

from shared import config


@lru_cache(maxsize=1)
def _get_model():
    """Лениво загружаем модель один раз на процесс (тяжёлая инициализация)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBEDDING_MODEL)


def embed_text(text: str) -> list[float]:
    """Посчитать эмбеддинг одного текста."""
    return embed_texts([text])[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Посчитать эмбеддинги для списка текстов (батчем — быстрее)."""
    model = _get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,  # косинусная близость через нормированные векторы
        convert_to_numpy=True,
    )
    return [vec.tolist() for vec in vectors]


def embedding_dim() -> int:
    """Размерность эмбеддингов (из конфигурации)."""
    return config.EMBEDDING_DIM
