"""Тесты логики RAG (agents/rag/rag.py).

Эмбеддинги и OpenSearch замоканы, LLM в mock-режиме (см. conftest). Проверяем
два ключевых поведения: находит документ по релевантному запросу и честно
говорит «не знаю», когда релевантного контекста нет.
"""

from __future__ import annotations

import pytest

from agents.rag import rag


@pytest.fixture
def _no_embeddings(monkeypatch):
    """Эмбеддинг вопроса не считаем по-настоящему — отдаём фиктивный вектор."""
    monkeypatch.setattr(rag.embeddings, "embed_text", lambda _text: [0.0, 0.0, 0.0])


def _fake_search(hits):
    return lambda *_args, **_kwargs: hits


def test_rag_finds_document(monkeypatch, _no_embeddings):
    """Релевантный kNN-хит → found=True, ответ от LLM, источник в списке."""
    hits = [
        {
            "doc_id": "vpn-setup",
            "source": "vpn-setup.md",
            "title": "Подключение к VPN",
            "chunk_index": 0,
            "text": "Запустите GlobalProtect и войдите на vpn.company.ru с MFA.",
            "score": 0.92,
        }
    ]
    monkeypatch.setattr(rag.opensearch_client, "knn_search", _fake_search(hits))

    result = rag.answer_question("не подключается VPN")

    assert result["found"] is True
    assert result["answer"].strip()
    assert result["sources"][0]["source"] == "vpn-setup.md"


def test_rag_says_unknown_when_no_relevant_context(monkeypatch, _no_embeddings):
    """Лучший скор ниже порога → честное «не знаю», источников нет."""
    hits = [
        {
            "doc_id": "vpn-setup",
            "source": "vpn-setup.md",
            "title": "Подключение к VPN",
            "chunk_index": 0,
            "text": "что-то нерелевантное",
            "score": 0.10,  # ниже rag.MIN_SCORE
        }
    ]
    monkeypatch.setattr(rag.opensearch_client, "knn_search", _fake_search(hits))

    result = rag.answer_question("как работает телепортация")

    assert result["found"] is False
    assert result["sources"] == []
    assert "нет информации" in result["answer"]


def test_rag_empty_question(monkeypatch, _no_embeddings):
    """Пустой вопрос не уходит в поиск/LLM."""
    monkeypatch.setattr(
        rag.opensearch_client,
        "knn_search",
        _fake_search([]),
    )
    result = rag.answer_question("   ")
    assert result["found"] is False
