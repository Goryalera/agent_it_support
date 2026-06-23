"""Индексатор базы знаний.

Читает все markdown-файлы из docs/knowledge_base/, бьёт каждый на куски,
считает эмбеддинги и кладёт куски (текст + вектор) в индекс OpenSearch.

Запуск:
    python -m agents.rag.indexer
"""

from __future__ import annotations

import sys
from pathlib import Path

from agents.rag import opensearch_client
from shared import config, embeddings

# docs/knowledge_base относительно корня репозитория
KB_DIR = Path(__file__).resolve().parents[2] / "docs" / "knowledge_base"

# Размер куска в символах и перекрытие между кусками.
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


def read_documents(kb_dir: Path = KB_DIR) -> list[dict]:
    """Прочитать все .md документы. Возвращает [{doc_id, source, title, text}]."""
    docs = []
    for path in sorted(kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        title = _extract_title(text, fallback=path.stem)
        docs.append(
            {
                "doc_id": path.stem,
                "source": path.name,
                "title": title,
                "text": text,
            }
        )
    return docs


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Разбить текст на перекрывающиеся куски, стараясь резать по абзацам."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
        else:
            if buf:
                chunks.append(buf)
            # Очень длинный абзац режем жёстко по размеру.
            if len(para) > size:
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i : i + size])
                buf = ""
            else:
                buf = para
    if buf:
        chunks.append(buf)
    return chunks or [text[:size]]


def build_chunk_docs(documents: list[dict]) -> list[dict]:
    """Превратить документы в куски с эмбеддингами, готовые для OpenSearch."""
    chunk_docs: list[dict] = []
    texts: list[str] = []
    meta: list[dict] = []

    for doc in documents:
        for idx, chunk in enumerate(chunk_text(doc["text"])):
            # В текст куска для эмбеддинга подмешиваем заголовок — улучшает поиск.
            texts.append(f"{doc['title']}\n\n{chunk}")
            meta.append(
                {
                    "doc_id": doc["doc_id"],
                    "source": doc["source"],
                    "title": doc["title"],
                    "chunk_index": idx,
                    "text": chunk,
                }
            )

    vectors = embeddings.embed_texts(texts)
    for m, vec in zip(meta, vectors, strict=True):
        chunk_docs.append({**m, "embedding": vec})
    return chunk_docs


def run() -> int:
    """Полная переиндексация. Возвращает число залитых кусков."""
    print(f"Читаю документы из {KB_DIR} …")
    documents = read_documents()
    if not documents:
        print("ВНИМАНИЕ: в базе знаний нет документов (.md). Нечего индексировать.")
        return 0
    print(f"Документов: {len(documents)}. Считаю эмбеддинги и режу на куски …")
    chunk_docs = build_chunk_docs(documents)
    print(f"Кусков: {len(chunk_docs)}. Подключаюсь к OpenSearch …")

    client = opensearch_client.get_client()
    opensearch_client.recreate_index(
        client, config.OPENSEARCH_INDEX, embeddings.embedding_dim()
    )
    written = opensearch_client.bulk_index(client, config.OPENSEARCH_INDEX, chunk_docs)
    print(f"Готово. Записано кусков в индекс '{config.OPENSEARCH_INDEX}': {written}")
    return written


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 — индексатор запускают вручную, печатаем причину
        print(f"Ошибка индексации: {exc}", file=sys.stderr)
        sys.exit(1)
