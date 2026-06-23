"""Тонкая обёртка над LLM.

Весь остальной код зовёт `ask_llm(prompt)` и ничего не знает про провайдера.
Провайдер выбирается конфигом, под капотом могут быть разные модели — чтобы
сменить, достаточно поменять переменные окружения, а не код.

Режим (config.LLM_MODE):
- "real" — реальный вызов выбранного провайдера.
- "mock" — детерминированная заглушка без сети (для тестов/CI/демо без кредов).

Провайдер при real (config.LLM_PROVIDER):
- "gigachat"   — GigaChat (нужны GIGACHAT_CREDENTIALS).
- "openrouter" — OpenRouter, OpenAI-совместимый API (нужен OPENROUTER_API_KEY).
                 Модель задаётся OPENROUTER_MODEL, по умолчанию deepseek/deepseek-v4-flash.
"""

from __future__ import annotations

import httpx

from shared import config, metrics

_SYSTEM_DEFAULT = (
    "Ты — помощник первой линии ИТ-поддержки компании. "
    "Отвечай кратко, по делу и на русском языке."
)


def _ask_mock(prompt: str) -> str:
    """Заглушка: не ходит в сеть, отвечает предсказуемо.

    Достаточно для тестов и демонстрации пути данных без реального LLM.
    """
    metrics.record_llm_call(provider="mock", mode="mock")
    snippet = prompt.strip().replace("\n", " ")
    if len(snippet) > 200:
        snippet = snippet[:200] + "…"
    return f"[MOCK-LLM] Ответ-заглушка на запрос: {snippet}"


def _ask_gigachat(prompt: str, system: str) -> str:
    """Реальный вызов GigaChat через официальный пакет `gigachat`."""
    # Импорт внутри функции, чтобы тесты в mock-режиме не требовали пакет/сеть.
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole

    if not config.GIGACHAT_CREDENTIALS:
        raise RuntimeError(
            "LLM_MODE=real, но GIGACHAT_CREDENTIALS пуст. "
            "Заполни .env или поставь LLM_MODE=mock."
        )

    chat = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system),
            Messages(role=MessagesRole.USER, content=prompt),
        ],
        model=config.GIGACHAT_MODEL,
    )

    with GigaChat(
        credentials=config.GIGACHAT_CREDENTIALS,
        scope=config.GIGACHAT_SCOPE,
        model=config.GIGACHAT_MODEL,
        verify_ssl_certs=config.GIGACHAT_VERIFY_SSL_CERTS,
    ) as giga:
        response = giga.chat(chat)

    usage = getattr(response, "usage", None)
    metrics.record_llm_call(
        provider="gigachat",
        mode="real",
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )
    return response.choices[0].message.content


def _ask_openrouter(prompt: str, system: str) -> str:
    """Реальный вызов OpenRouter через OpenAI-совместимый chat-эндпоинт."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError(
            "LLM_PROVIDER=openrouter, но OPENROUTER_API_KEY пуст. "
            "Заполни .env или поставь LLM_MODE=mock."
        )

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    # Необязательные заголовки для статистики приложения на openrouter.ai.
    if config.OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = config.OPENROUTER_SITE_URL
    if config.OPENROUTER_APP_NAME:
        headers["X-Title"] = config.OPENROUTER_APP_NAME

    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }

    url = f"{config.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    with httpx.Client(timeout=120) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    usage = data.get("usage") or {}
    metrics.record_llm_call(
        provider="openrouter",
        mode="real",
        prompt_tokens=usage.get("prompt_tokens", 0) or 0,
        completion_tokens=usage.get("completion_tokens", 0) or 0,
    )
    return data["choices"][0]["message"]["content"]


def ask_llm(prompt: str, system: str | None = None) -> str:
    """Задать вопрос LLM и получить текстовый ответ.

    Args:
        prompt: пользовательский/собранный промпт.
        system: системная инструкция (по умолчанию — роль ИТ-поддержки).

    Returns:
        Текст ответа модели.
    """
    system = system or _SYSTEM_DEFAULT
    if config.LLM_MODE == "mock":
        return _ask_mock(prompt)
    if config.LLM_PROVIDER == "openrouter":
        return _ask_openrouter(prompt, system)
    return _ask_gigachat(prompt, system)
