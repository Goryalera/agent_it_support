"""A2A-клиент оркестратора: вызов RAG-агента по протоколу A2A.

Оркестратор резолвит Agent Card RAG-агента по его URL, формирует A2A-сообщение
с вопросом и извлекает текстовый ответ. Совместимо с a2a-sdk 0.2.x.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart

from shared import config


def _texts_from_parts(parts) -> list[str]:
    out: list[str] = []
    for p in parts or []:
        root = getattr(p, "root", p)
        text = getattr(root, "text", None)
        if text:
            out.append(text)
    return out


def _extract_text(response) -> str:
    """Достать текст из ответа A2A — поддерживает и Message, и Task."""
    root = getattr(response, "root", response)
    result = getattr(root, "result", None)
    if result is None:
        error = getattr(root, "error", None)
        return f"[Ошибка A2A] {error}" if error else "[Пустой ответ A2A]"

    texts: list[str] = []
    texts.extend(_texts_from_parts(getattr(result, "parts", None)))

    status = getattr(result, "status", None)
    if status is not None:
        msg = getattr(status, "message", None)
        if msg is not None:
            texts.extend(_texts_from_parts(getattr(msg, "parts", None)))

    for art in getattr(result, "artifacts", None) or []:
        texts.extend(_texts_from_parts(getattr(art, "parts", None)))

    return "\n".join(t for t in texts if t).strip() or "[Пустой ответ агента]"


async def ask_agent(question: str, agent_url: str) -> str:
    """Задать вопрос произвольному A2A-агенту по его URL и вернуть текст ответа.

    Базовый вызов: резолвим Agent Card, шлём сообщение, достаём текст. Конкретные
    специалисты (RAG, аналитик) — тонкие обёртки сверху с нужным URL по умолчанию.
    """
    async with httpx.AsyncClient(timeout=120) as httpx_client:
        resolver = A2ACardResolver(httpx_client=httpx_client, base_url=agent_url)
        agent_card = await resolver.get_agent_card()
        client = A2AClient(httpx_client=httpx_client, agent_card=agent_card)

        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=question))],
            messageId=uuid4().hex,
        )
        request = SendMessageRequest(
            id=uuid4().hex,
            params=MessageSendParams(message=message),
        )
        response = await client.send_message(request)
        return _extract_text(response)


async def ask_rag(question: str, agent_url: str | None = None) -> str:
    """Задать вопрос RAG-агенту по A2A (база знаний)."""
    return await ask_agent(question, agent_url or config.RAG_AGENT_URL)


async def ask_analyst(question: str, agent_url: str | None = None) -> str:
    """Задать вопрос аналитик-агенту по A2A (статистика тикетов)."""
    return await ask_agent(question, agent_url or config.ANALYST_AGENT_URL)


async def ask_action(question: str, agent_url: str | None = None) -> str:
    """Отправить запрос-действие action-агенту по A2A (создание тикетов)."""
    return await ask_agent(question, agent_url or config.ACTION_AGENT_URL)
