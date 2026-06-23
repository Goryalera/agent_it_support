"""Агент-нотификатор: слушает топик событий и «отправляет» уведомления.

В простом виде «отправка» — это запись в лог-файл и вывод в консоль. Так видно
завершённую событийную цепочку: action-агент создал тикет → опубликовал событие
→ нотификатор поймал его из очереди и сообщил.

Надёжность: цикл переживает недоступность брокера — при ошибке ждёт и
переподключается, а не падает. Это иллюстрирует поведение системы, если consumer
или брокер временно недоступны.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from shared import config


def notifications_path() -> Path:
    """Путь к файлу уведомлений (относительный — от корня репозитория)."""
    raw = Path(config.NOTIFICATIONS_FILE)
    if raw.is_absolute():
        return raw
    return Path(__file__).resolve().parents[2] / raw


def format_notification(event: dict) -> str:
    """Собрать человекочитаемую строку уведомления из события."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    number = event.get("ticket_number", "—")
    category = event.get("category", "—")
    priority = event.get("priority", "—")
    text = event.get("text", "")
    return (
        f"[{ts}] 🔔 Новый тикет {number} "
        f"(категория «{category}», приоритет «{priority}»): {text}"
    )


def record_notification(event: dict) -> str:
    """«Отправить» уведомление: дописать в файл и вывести в консоль."""
    line = format_notification(event)
    path = notifications_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)
    return line


def read_recent(limit: int = 50) -> list[str]:
    """Прочитать последние уведомления из файла (для UI/эндпоинта)."""
    path = notifications_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[-limit:]


def run_consumer(stop_event: threading.Event | None = None) -> None:
    """Бесконечный цикл потребления событий с переподключением при сбоях."""
    from kafka import KafkaConsumer

    while stop_event is None or not stop_event.is_set():
        try:
            consumer = KafkaConsumer(
                config.KAFKA_TOPIC,
                bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(","),
                group_id=config.KAFKA_CONSUMER_GROUP,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
                consumer_timeout_ms=1000,
            )
            print(
                f"Нотификатор подключился к {config.KAFKA_BOOTSTRAP_SERVERS}, "
                f"слушаю топик '{config.KAFKA_TOPIC}'.",
                flush=True,
            )
            while stop_event is None or not stop_event.is_set():
                # poll-цикл: consumer_timeout_ms заставляет итератор завершиться,
                # давая шанс проверить stop_event между батчами.
                for message in consumer:
                    record_notification(message.value)
            consumer.close()
            return
        except Exception as exc:  # noqa: BLE001 — брокер недоступен → ждём и пробуем снова
            print(
                f"Нотификатор: брокер недоступен ({exc.__class__.__name__}), "
                "повтор через 5с …",
                flush=True,
            )
            time.sleep(5)


if __name__ == "__main__":
    run_consumer()
