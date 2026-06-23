"""Тест графа оркестратора с настоящей маршрутизацией (agents/orchestrator/graph.py).

A2A-вызовы специалистов замоканы. Проверяем, что роутер уводит вопрос на знание
к RAG, а вопрос про статистику — к аналитику, и что вызывается только нужная
ветка. В mock-режиме LLM (см. conftest) роутер решает по ключевым словам.
"""

from __future__ import annotations

import asyncio

from agents.orchestrator import graph as graph_module


def test_graph_routes_knowledge_question_to_rag(monkeypatch):
    async def fake_ask_rag(question, agent_url=None):
        return "Оформите заявку на портале ServiceDesk."

    async def must_not_call(question, agent_url=None):
        raise AssertionError("Аналитик не должен вызываться для вопроса на знание.")

    monkeypatch.setattr(graph_module, "ask_rag", fake_ask_rag)
    monkeypatch.setattr(graph_module, "ask_analyst", must_not_call)

    graph = graph_module.build_graph()
    result = asyncio.run(graph.ainvoke({"question": "как получить доступ к Jira"}))

    assert result["route"] == "rag"
    assert result["answer"] == "Оформите заявку на портале ServiceDesk."


def test_graph_routes_stats_question_to_analyst(monkeypatch):
    async def must_not_call(question, agent_url=None):
        raise AssertionError("RAG не должен вызываться для вопроса про статистику.")

    async def fake_ask_analyst(question, agent_url=None):
        return "За май — 42 инцидента по доступам."

    monkeypatch.setattr(graph_module, "ask_rag", must_not_call)
    monkeypatch.setattr(graph_module, "ask_analyst", fake_ask_analyst)

    graph = graph_module.build_graph()
    result = asyncio.run(
        graph.ainvoke({"question": "сколько инцидентов по доступам за май"})
    )

    assert result["route"] == "analyst"
    assert result["answer"] == "За май — 42 инцидента по доступам."


def test_graph_routes_action_request_to_action(monkeypatch):
    async def fake_ask_action(question, agent_url=None):
        return "Заявка создана: REQ-000001."

    monkeypatch.setattr(graph_module, "ask_action", fake_ask_action)

    graph = graph_module.build_graph()
    result = asyncio.run(
        graph.ainvoke({"question": "создай заявку на доступ к боевой БД"})
    )

    assert result["route"] == "action"
    assert result["answer"] == "Заявка создана: REQ-000001."


def test_action_node_degrades_gracefully_when_agent_down(monkeypatch):
    """Action-агент опционален: если он недоступен, запрос не падает."""

    async def boom(question, agent_url=None):
        raise ConnectionError("action-агент не запущен")

    monkeypatch.setattr(graph_module, "ask_action", boom)

    graph = graph_module.build_graph()
    result = asyncio.run(graph.ainvoke({"question": "оформи заявку на ноутбук"}))

    assert result["route"] == "action"
    assert "недоступно" in result["answer"]
