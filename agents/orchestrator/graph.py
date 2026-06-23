"""Граф оркестратора на LangGraph.

Поток: принять запрос → роутер выбирает специалиста → вызвать его по A2A →
вернуть ответ. Маршрутизация настоящая: роутер выбирает между RAG-агентом
(вопросы на знание), аналитик-агентом (статистика/отчёты) и action-агентом
(запросы-действия — создать заявку). Решение принимает `router.classify_intent`
(LLM + запасное правило по словам).

Action-агент относится к Слою 2 и поднимается профилем docker-compose. Если его
сервис не запущен, узел `call_action` не роняет запрос, а возвращает понятное
сообщение — оркестратор остаётся устойчивым к отсутствию опционального агента.
"""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.orchestrator import router
from agents.orchestrator.a2a_client import ask_action, ask_analyst, ask_rag


class AskState(TypedDict, total=False):
    question: str
    route: str
    answer: str


async def route_node(state: AskState) -> AskState:
    """Выбрать специалиста по интенту вопроса (LLM-классификация + fallback)."""
    # classify_intent синхронный (зовёт ask_llm) — уводим в поток, чтобы не
    # блокировать event loop оркестратора.
    route = await asyncio.to_thread(router.classify_intent, state["question"])
    return {"route": route}


async def call_rag_node(state: AskState) -> AskState:
    """Вопрос на знание → RAG-агент по A2A."""
    answer = await ask_rag(state["question"])
    return {"answer": answer}


async def call_analyst_node(state: AskState) -> AskState:
    """Вопрос про статистику/отчёт → аналитик-агент по A2A."""
    answer = await ask_analyst(state["question"])
    return {"answer": answer}


async def call_action_node(state: AskState) -> AskState:
    """Запрос-действие → action-агент по A2A (Слой 2, профиль docker-compose).

    Action-агент опционален: если он не поднят, не роняем запрос, а честно
    сообщаем, что выполнение действий сейчас недоступно.
    """
    try:
        answer = await ask_action(state["question"])
    except Exception:  # noqa: BLE001 — опциональный агент недоступен → мягкий отказ
        answer = (
            "Создание заявок сейчас недоступно: action-агент не запущен. "
            "Поднимите его профилем «action» (docker compose --profile action up) "
            "или обратитесь в поддержку напрямую."
        )
    return {"answer": answer}


def _select_route(state: AskState) -> str:
    return state.get("route", router.ROUTE_RAG)


def build_graph():
    """Скомпилировать граф оркестратора с реальной маршрутизацией."""
    graph = StateGraph(AskState)
    graph.add_node("route", route_node)
    graph.add_node("call_rag", call_rag_node)
    graph.add_node("call_analyst", call_analyst_node)
    graph.add_node("call_action", call_action_node)

    graph.add_edge(START, "route")
    # Роутер выбирает ветку: знание → RAG, статистика → аналитик, действие → action.
    graph.add_conditional_edges(
        "route",
        _select_route,
        {
            router.ROUTE_RAG: "call_rag",
            router.ROUTE_ANALYST: "call_analyst",
            router.ROUTE_ACTION: "call_action",
        },
    )
    graph.add_edge("call_rag", END)
    graph.add_edge("call_analyst", END)
    graph.add_edge("call_action", END)

    return graph.compile()
