"""Общие фикстуры тестов.

Гоняем LLM в mock-режиме, чтобы тесты не ходили в сеть и не требовали кредов
GigaChat. Тяжёлые зависимости (sentence-transformers, gigachat) в тестах не
импортируются — поиск и эмбеддинги мокаются.
"""

from __future__ import annotations

import pytest

from shared import config


@pytest.fixture(autouse=True)
def _force_mock_llm(monkeypatch):
    """Во всех тестах ask_llm работает заглушкой (без сети)."""
    monkeypatch.setattr(config, "LLM_MODE", "mock")
