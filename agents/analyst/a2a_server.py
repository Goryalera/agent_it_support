"""A2A-обвязка аналитик-агента: Agent Card и исполнитель.

Аналитик — A2A-сервер. Agent Card описывает его возможности («отвечаю на вопросы
по статистике тикетов, делаю отчёты»). Исполнитель принимает вопрос, прогоняет
через NL→SQL-конвейер и отдаёт текстовый ответ.

Совместимо с a2a-sdk 0.2.x (та же схема, что у RAG-агента).
"""

from __future__ import annotations

import asyncio

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from agents.analyst.analyst import answer_question


def build_agent_card(url: str) -> AgentCard:
    """Собрать Agent Card аналитик-агента."""
    skill = AgentSkill(
        id="ticket_analytics",
        name="Аналитика по тикетам",
        description=(
            "Отвечаю на вопросы по статистике обращений и делаю отчёты: "
            "сколько тикетов по категориям, динамика, среднее время решения "
            "и т.п. Под капотом — безопасный NL→SQL (только чтение)."
        ),
        tags=["analytics", "nl2sql", "reports", "it-support"],
        examples=[
            "Сколько инцидентов по доступам за май",
            "Средне время решения по приоритетам",
            "Топ-3 категории обращений за последний месяц",
        ],
    )
    return AgentCard(
        name="AskOps Analyst Agent",
        description="Отвечаю на вопросы по статистике тикетов и делаю отчёты (NL→SQL).",
        url=url,
        version="0.1.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


class AnalystAgentExecutor(AgentExecutor):
    """Исполнитель A2A: вопрос → NL→SQL → текстовый ответ со сводкой."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = context.get_user_input() or ""
        # NL→SQL-конвейер синхронный (LLM + SQLite) — уводим в поток.
        result = await asyncio.to_thread(answer_question, question)
        await event_queue.enqueue_event(new_agent_text_message(result["answer"]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Отмена задач не поддерживается.")
