"""Тесты action-агента (agents/action/action.py).

Проверяем создание тикета (запись в БД + событие) и устойчивость: если очередь
недоступна, тикет всё равно создаётся. Публикацию в Kafka мокаем — реальный
брокер в тестах не нужен.
"""

from __future__ import annotations

import builtins

import pytest

from agents.action import action, kafka_producer
from agents.analyst import tickets_db
from shared import config


@pytest.fixture
def tickets_db_path(tmp_path, monkeypatch):
    db = tmp_path / "tickets.db"
    monkeypatch.setattr(config, "TICKETS_DB_PATH", str(db))
    return db


def test_create_ticket_writes_and_publishes(tickets_db_path, monkeypatch):
    events = []

    def fake_publish(event):
        events.append(event)
        return True

    monkeypatch.setattr(action.kafka_producer, "publish_event", fake_publish)

    result = action.create_ticket("создай заявку на доступ к боевой БД")

    assert result["found"] is True
    assert result["ticket_number"].startswith("REQ-")
    assert result["category"] == "доступы"
    assert result["published"] is True

    # Событие ушло в очередь с нужным типом.
    assert len(events) == 1
    assert events[0]["event"] == "ticket_created"
    assert events[0]["ticket_number"] == result["ticket_number"]

    # Тикет реально записан в БД со статусом «создан» и каналом «агент».
    number = result["ticket_number"]
    rows = tickets_db.run_select(
        f"SELECT status, channel FROM tickets WHERE ticket_number = '{number}'"
    )
    assert rows["rows"][0] == ["создан", "агент"]


def test_create_ticket_survives_queue_down(tickets_db_path, monkeypatch):
    """Очередь недоступна → тикет всё равно создан, published=False."""
    monkeypatch.setattr(action.kafka_producer, "publish_event", lambda _e: False)

    result = action.create_ticket("оформи заявку на новый ноутбук")

    assert result["found"] is True
    assert result["published"] is False
    assert result["category"] == "железо"
    assert "уже зарегистрирована" in result["answer"]


def test_ticket_numbers_increment(tickets_db_path, monkeypatch):
    monkeypatch.setattr(action.kafka_producer, "publish_event", lambda _e: True)
    first = action.create_ticket("создай заявку на доступ к Jira")
    second = action.create_ticket("создай заявку на доступ к Confluence")
    assert first["ticket_number"] != second["ticket_number"]
    assert second["ticket_number"] == "REQ-000002"


def test_create_ticket_empty(tickets_db_path):
    result = action.create_ticket("   ")
    assert result["found"] is False


def test_publish_event_graceful_without_kafka_lib(monkeypatch):
    """Если библиотека kafka недоступна — publish_event тихо вернёт False."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "kafka":
            raise ImportError("kafka не установлен")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert kafka_producer.publish_event({"event": "x"}) is False
