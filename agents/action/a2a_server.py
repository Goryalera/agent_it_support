"""A2A-обвязка action-агента: Agent Card и исполнитель.

Action-агент — A2A-сервер. Agent Card описывает его возможности («создаю заявки и
тикеты»). Исполнитель принимает запрос-действие, создаёт тикет и публикует событие.

Совместимо с a2a-sdk 0.2.x (та же схема, что у RAG и аналитика).
"""

from __future__ import annotations

import asyncio

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from agents.action.action import create_ticket


def build_agent_card(url: str) -> AgentCard:
    """Собрать Agent Card action-агента."""
    skill = AgentSkill(
        id="create_ticket",
        name="Создание заявок и тикетов",
        description=(
            "Создаю заявки и тикеты по запросу сотрудника (доступ, оборудование, "
            "ПО). Записываю тикет в систему и публикую событие в очередь — "
            "ответственных уведомит нотификатор."
        ),
        tags=["action", "tickets", "kafka", "it-support"],
        examples=[
            "Создай заявку на доступ к боевой БД",
            "Оформи заявку на новый ноутбук",
            "Заведи тикет на установку 1С",
        ],
    )
    return AgentCard(
        name="AskOps Action Agent",
        description="Создаю заявки и тикеты, публикую события в очередь.",
        url=url,
        version="0.1.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


class ActionAgentExecutor(AgentExecutor):
    """Исполнитель A2A: запрос-действие → создание тикета + событие → ответ."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        request_text = context.get_user_input() or ""
        # Запись в SQLite и публикация в Kafka синхронны — уводим в поток.
        result = await asyncio.to_thread(create_ticket, request_text)
        await event_queue.enqueue_event(new_agent_text_message(result["answer"]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Отмена задач не поддерживается.")
