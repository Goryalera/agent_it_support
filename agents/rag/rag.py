"""Логика RAG: по вопросу найти контекст в OpenSearch и ответить через LLM.

Retrieval-Augmented Generation: модель отвечает не «из головы», а по найденным
кускам базы знаний. Если релевантного контекста нет — честно говорит, что не
знает.
"""

from __future__ import annotations

from agents.rag import opensearch_client
from shared import config, embeddings
from shared.llm import ask_llm

# Если лучший kNN-скор ниже порога — считаем, что в базе знаний ответа нет.
# Векторы нормированы, OpenSearch отдаёт score = 1/(2 - cosinesim) ∈ (0.33..1].
MIN_SCORE = 0.55

_SYSTEM_PROMPT = (
    "Ты — помощник первой линии ИТ-поддержки компании. "
    "Отвечай только на основе предоставленного контекста из базы знаний. "
    "Если в контексте нет ответа на вопрос — честно скажи, что в базе знаний нет "
    "информации по этому вопросу, и не выдумывай. Отвечай кратко, по делу, на "
    "русском языке, по возможности пошагово."
)

_NO_CONTEXT_ANSWER = (
    "В базе знаний нет информации по этому вопросу. "
    "Рекомендую обратиться в поддержку напрямую."
)


def _build_prompt(question: str, contexts: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(contexts, 1):
        blocks.append(f"[Документ {i}: {c['title']} ({c['source']})]\n{c['text']}")
    context_text = "\n\n".join(blocks)
    return (
        f"Контекст из базы знаний:\n\n{context_text}\n\n"
        f"Вопрос сотрудника: {question}\n\n"
        f"Ответ (только по контексту выше):"
    )


def retrieve(question: str, top_k: int | None = None) -> list[dict]:
    """Найти релевантные куски базы знаний по вопросу (kNN-поиск)."""
    top_k = top_k or config.RAG_TOP_K
    client = opensearch_client.get_client()
    vector = embeddings.embed_text(question)
    return opensearch_client.knn_search(client, config.OPENSEARCH_INDEX, vector, top_k)


def answer_question(question: str, top_k: int | None = None) -> dict:
    """Главная функция RAG: вернуть ответ и список источников.

    Returns:
        {"answer": str, "sources": [{"title","source","score"}], "found": bool}
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "Пустой вопрос.", "sources": [], "found": False}

    hits = retrieve(question, top_k)
    best_score = hits[0]["score"] if hits else 0.0

    if not hits or best_score < MIN_SCORE:
        return {"answer": _NO_CONTEXT_ANSWER, "sources": [], "found": False}

    prompt = _build_prompt(question, hits)
    answer = ask_llm(prompt, system=_SYSTEM_PROMPT)

    # Уникальные источники в порядке релевантности.
    seen: set[str] = set()
    sources = []
    for h in hits:
        if h["source"] in seen:
            continue
        seen.add(h["source"])
        sources.append(
            {"title": h["title"], "source": h["source"], "score": h.get("score")}
        )

    return {"answer": answer, "sources": sources, "found": True}
