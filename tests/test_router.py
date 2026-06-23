"""Тесты роутера оркестратора (agents/orchestrator/router.py).

Проверяем оба пути решения: LLM-классификацию и запасное правило по ключевым
словам. В mock-режиме (см. conftest) ask_llm возвращает заглушку, не похожую на
маршрут, поэтому classify_intent честно падает на ключевые слова — это и делает
маршрутизацию детерминированной в тестах.
"""

from __future__ import annotations

import pytest

from agents.orchestrator import router


@pytest.mark.parametrize(
    "question,expected",
    [
        ("сколько инцидентов по доступам за май", router.ROUTE_ANALYST),
        ("среднее время решения по приоритетам", router.ROUTE_ANALYST),
        ("покажи динамику обращений за месяц", router.ROUTE_ANALYST),
        ("топ-3 категории за год", router.ROUTE_ANALYST),
        ("как настроить VPN на ноутбуке", router.ROUTE_RAG),
        ("забыл пароль от корпоративной почты", router.ROUTE_RAG),
        ("как получить доступ к Jira", router.ROUTE_RAG),
        ("создай заявку на доступ к боевой БД", router.ROUTE_ACTION),
        ("оформи заявку на новый ноутбук", router.ROUTE_ACTION),
        ("заведи тикет на установку 1С", router.ROUTE_ACTION),
    ],
)
def test_keyword_fallback_routing(question, expected):
    # mock-LLM не даёт валидного маршрута → срабатывает правило по ключевым словам.
    assert router.classify_intent(question) == expected


def test_empty_question_defaults_to_rag():
    assert router.classify_intent("   ") == router.ROUTE_RAG


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("analyst", router.ROUTE_ANALYST),
        ("rag", router.ROUTE_RAG),
        ("action", router.ROUTE_ACTION),
        ("Маршрут: analyst", router.ROUTE_ANALYST),
        ("'rag'", router.ROUTE_RAG),
        ("не знаю", None),
        ("", None),
    ],
)
def test_parse_llm_route(raw, expected):
    assert router._parse_llm_route(raw) == expected


def test_llm_decision_overrides_keywords(monkeypatch):
    """Если LLM дал валидный маршрут — он главнее ключевых слов."""
    monkeypatch.setattr(router, "ask_llm", lambda _q, system=None: "analyst")
    # Вопрос «как настроить» по словам ушёл бы в rag, но LLM сказал analyst.
    assert router.classify_intent("как настроить отчёт") == router.ROUTE_ANALYST


def test_fallback_when_llm_raises(monkeypatch):
    """LLM упал (нет кредов/сети) → решаем по ключевым словам, запрос не падает."""

    def boom(*_a, **_k):
        raise RuntimeError("нет доступа к LLM")

    monkeypatch.setattr(router, "ask_llm", boom)
    assert router.classify_intent("сколько тикетов за май") == router.ROUTE_ANALYST
    assert router.classify_intent("как настроить vpn") == router.ROUTE_RAG
