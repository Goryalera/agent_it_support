"""Работа с OpenSearch: подключение, создание kNN-индекса, поиск.

Поле под вектор имеет тип `knn_vector` с размерностью EMBEDDING_DIM. Индекс
создаётся с `index.knn: true`, поиск — kNN по косинусной близости.
"""

from __future__ import annotations

from opensearchpy import OpenSearch, helpers

from shared import config


def get_client() -> OpenSearch:
    """Клиент OpenSearch для локального режима (без TLS и авторизации)."""
    return OpenSearch(
        hosts=[{"host": config.OPENSEARCH_HOST, "port": config.OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )


def index_mapping(dim: int) -> dict:
    """Маппинг индекса: текст куска + его вектор-эмбеддинг (knn_vector)."""
    return {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "source": {"type": "keyword"},
                "title": {"type": "text"},
                "chunk_index": {"type": "integer"},
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene",
                    },
                },
            }
        },
    }


def recreate_index(client: OpenSearch, index: str, dim: int) -> None:
    """Удалить (если есть) и создать индекс заново — для чистой переиндексации."""
    if client.indices.exists(index=index):
        client.indices.delete(index=index)
    client.indices.create(index=index, body=index_mapping(dim))


def bulk_index(client: OpenSearch, index: str, docs: list[dict]) -> int:
    """Массово залить документы. Возвращает число успешно записанных."""
    actions = [{"_index": index, "_source": doc} for doc in docs]
    success, _ = helpers.bulk(client, actions, refresh=True)
    return success


def knn_search(
    client: OpenSearch, index: str, vector: list[float], top_k: int
) -> list[dict]:
    """kNN-поиск top_k ближайших кусков по вектору запроса."""
    body = {
        "size": top_k,
        "query": {"knn": {"embedding": {"vector": vector, "k": top_k}}},
        "_source": ["doc_id", "source", "title", "chunk_index", "text"],
    }
    resp = client.search(index=index, body=body)
    hits = resp.get("hits", {}).get("hits", [])
    results = []
    for h in hits:
        item = dict(h["_source"])
        item["score"] = h.get("_score")
        results.append(item)
    return results
