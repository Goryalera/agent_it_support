"""Подготовка RAG-агента к старту внутри контейнера.

1. Дожидается готовности OpenSearch (он поднимается дольше, чем агент).
2. Если индекс ещё не создан — запускает индексацию базы знаний.
   Индекс лежит в именованном volume, поэтому при перезапусках повторная
   индексация не нужна (можно форсировать переменной REINDEX=true).

Запуск: python -m agents.rag.startup
"""

from __future__ import annotations

import os
import sys
import time

from agents.rag import indexer, opensearch_client
from shared import config


def wait_for_opensearch(timeout: float = 120.0, interval: float = 3.0) -> None:
    """Опрашивать OpenSearch, пока кластер не ответит (или не выйдет таймаут)."""
    client = opensearch_client.get_client()
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            client.cluster.health(wait_for_status="yellow", timeout="5s")
            print("OpenSearch готов.")
            return
        except Exception as exc:  # noqa: BLE001 — ждём готовности, печатаем причину
            last_err = exc
            print(f"Жду OpenSearch… ({exc.__class__.__name__})")
            time.sleep(interval)
    raise RuntimeError(f"OpenSearch не поднялся за {timeout:.0f}с: {last_err}")


def ensure_index() -> None:
    """Проиндексировать базу знаний, если индекс ещё не создан."""
    client = opensearch_client.get_client()
    reindex = os.environ.get("REINDEX", "").strip().lower() in {"1", "true", "yes", "on"}
    exists = client.indices.exists(index=config.OPENSEARCH_INDEX)
    if exists and not reindex:
        print(f"Индекс '{config.OPENSEARCH_INDEX}' уже существует — пропускаю индексацию.")
        return
    print(f"Индексирую базу знаний в '{config.OPENSEARCH_INDEX}' …")
    indexer.run()


def main() -> None:
    wait_for_opensearch()
    ensure_index()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — стартовый шаг, печатаем и падаем
        print(f"Ошибка подготовки RAG-агента: {exc}", file=sys.stderr)
        sys.exit(1)
