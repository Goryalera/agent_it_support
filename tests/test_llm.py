"""Тесты обёртки над LLM (shared/llm.py)."""

from __future__ import annotations

from shared import config
from shared.llm import ask_llm


def test_ask_llm_mock_returns_text():
    """В mock-режиме ask_llm возвращает непустую строку без обращения в сеть."""
    answer = ask_llm("привет")
    assert isinstance(answer, str)
    assert answer.strip()


def test_ask_llm_mock_echoes_prompt():
    """Заглушка отражает запрос — значит, промпт реально дошёл до ask_llm."""
    answer = ask_llm("как сбросить пароль")
    assert "как сбросить пароль" in answer


def test_ask_llm_dispatches_to_gigachat(monkeypatch):
    """Вне mock-режима с провайдером gigachat ask_llm зовёт бэкенд GigaChat."""
    monkeypatch.setattr(config, "LLM_MODE", "real")
    monkeypatch.setattr(config, "LLM_PROVIDER", "gigachat")

    calls = {}

    def fake_gigachat(prompt: str, system: str) -> str:
        calls["prompt"] = prompt
        calls["system"] = system
        return "ответ от giga"

    monkeypatch.setattr("shared.llm._ask_gigachat", fake_gigachat)

    answer = ask_llm("вопрос", system="ты бот")
    assert answer == "ответ от giga"
    assert calls == {"prompt": "вопрос", "system": "ты бот"}


def test_ask_llm_dispatches_to_openrouter(monkeypatch):
    """С провайдером openrouter ask_llm зовёт бэкенд OpenRouter, не GigaChat."""
    monkeypatch.setattr(config, "LLM_MODE", "real")
    monkeypatch.setattr(config, "LLM_PROVIDER", "openrouter")

    def fail_gigachat(*_a, **_k):
        raise AssertionError("GigaChat не должен вызываться при provider=openrouter")

    monkeypatch.setattr("shared.llm._ask_gigachat", fail_gigachat)
    monkeypatch.setattr("shared.llm._ask_openrouter", lambda p, s: "ответ от deepseek")

    assert ask_llm("вопрос") == "ответ от deepseek"


def test_openrouter_builds_request_and_parses_response(monkeypatch):
    """_ask_openrouter шлёт корректный запрос и достаёт текст из ответа."""
    from shared import llm

    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(config, "OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
    monkeypatch.setattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ответ DeepSeek"}}]}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(llm.httpx, "Client", _FakeClient)

    answer = llm._ask_openrouter("как сбросить пароль", system="ты бот")

    assert answer == "ответ DeepSeek"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "deepseek/deepseek-v4-flash"
    assert captured["json"]["messages"][0] == {"role": "system", "content": "ты бот"}
    assert captured["json"]["messages"][1] == {
        "role": "user",
        "content": "как сбросить пароль",
    }


def test_openrouter_requires_api_key(monkeypatch):
    """Без ключа _ask_openrouter падает с понятной ошибкой."""
    import pytest

    from shared import llm

    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        llm._ask_openrouter("вопрос", system="ты бот")
