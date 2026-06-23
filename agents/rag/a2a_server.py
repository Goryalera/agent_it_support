"""A2A-обвязка RAG-агента: Agent Card и исполнитель (AgentExecutor).

RAG-агент выступает A2A-сервером. Agent Card описывает его возможности
(«отвечаю на вопросы по базе знаний»), исполнитель принимает A2A-сообщение,
прогоняет вопрос через RAG и отдаёт текстовый ответ.

Совместимо с a2a-sdk 0.2.x.
"""

from __future__ import annotations

import asyncio

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from agents.rag.rag import answer_question


def build_agent_card(url: str) -> AgentCard:
    """Собрать Agent Card RAG-агента."""
    skill = AgentSkill(
        id="kb_qa",
        name="Ответы по базе знаний",
        description=(
            "Отвечаю на вопросы сотрудников по корпоративной базе знаний "
            "ИТ-поддержки (VPN, доступы, пароли, оборудование и т.п.)."
        ),
        tags=["rag", "knowledge-base", "it-support"],
        examples=[
            "Не подключается VPN с домашнего ноутбука",
            "Как получить доступ к Jira?",
            "Забыл пароль от корпоративной почты",
        ],
    )
    return AgentCard(
        name="AskOps RAG Agent",
        description="Отвечаю на вопросы по корпоративной базе знаний ИТ-поддержки.",
        url=url,
        version="0.1.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )


class RagAgentExecutor(AgentExecutor):
    """Исполнитель A2A: вопрос → RAG → текстовый ответ."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = context.get_user_input() or ""
        # RAG-конвейер синхронный (эмбеддинги, OpenSearch, LLM) — уводим в поток,
        # чтобы не блокировать event loop сервера.
        result = await asyncio.to_thread(answer_question, question)
        await event_queue.enqueue_event(new_agent_text_message(result["answer"]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("Отмена задач не поддерживается в V1.")
