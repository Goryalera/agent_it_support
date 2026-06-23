"""Тесты агента-нотификатора (agents/notifier/consumer.py).

Проверяем форматирование уведомления и запись/чтение лог-файла. Сам Kafka-цикл
(run_consumer) требует брокера и здесь не гоняется — он тонкий и проверяется на
живом стенде профилем «action».
"""

from __future__ import annotations

import pytest

from agents.notifier import consumer
from shared import config


@pytest.fixture
def notif_file(tmp_path, monkeypatch):
    f = tmp_path / "notifications.log"
    monkeypatch.setattr(config, "NOTIFICATIONS_FILE", str(f))
    return f


def test_format_notification_has_key_fields():
    line = consumer.format_notification(
        {
            "ticket_number": "REQ-000001",
            "category": "доступы",
            "priority": "высокий",
            "text": "доступ к боевой БД",
        }
    )
    assert "REQ-000001" in line
    assert "доступы" in line
    assert "доступ к боевой БД" in line


def test_record_and_read_recent(notif_file):
    consumer.record_notification(
        {"ticket_number": "REQ-1", "category": "ПО", "priority": "средний", "text": "1С"}
    )
    consumer.record_notification(
        {"ticket_number": "REQ-2", "category": "сеть", "priority": "низкий", "text": "vpn"}
    )

    recent = consumer.read_recent()
    assert len(recent) == 2
    assert "REQ-2" in recent[-1]


def test_read_recent_empty(notif_file):
    assert consumer.read_recent() == []
