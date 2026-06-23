"""Публикация событий по тикетам в Kafka-совместимый брокер (Redpanda).

Надёжность важнее «успеха любой ценой»: если очередь недоступна, создание тикета
не должно падать. Поэтому publish_event ловит ошибки брокера и возвращает False —
тикет уже записан в БД, а событие просто не ушло (о чём честно сообщаем).
"""

from __future__ import annotations

import json

from shared import config


def publish_event(event: dict) -> bool:
    """Опубликовать событие в топик KAFKA_TOPIC. Вернуть True при успехе.

    При недоступном брокере не бросает исключение, а возвращает False —
    вызывающий код решает, что делать (у нас: тикет всё равно создан).
    """
    try:
        from kafka import KafkaProducer
    except ImportError:
        # Библиотека не установлена (например, в окружении без Слоя 2) — тихо
        # деградируем: событие не публикуется, но и не роняем процесс.
        return False

    producer = None
    try:
        producer = KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            acks="all",
            retries=1,
            request_timeout_ms=config.KAFKA_TIMEOUT * 1000,
            api_version_auto_timeout_ms=config.KAFKA_TIMEOUT * 1000,
            max_block_ms=config.KAFKA_TIMEOUT * 1000,
        )
        future = producer.send(config.KAFKA_TOPIC, value=event)
        future.get(timeout=config.KAFKA_TIMEOUT)  # дождаться подтверждения
        producer.flush(timeout=config.KAFKA_TIMEOUT)
        return True
    except Exception:  # noqa: BLE001 — брокер недоступен → деградируем, не падаем
        return False
    finally:
        if producer is not None:
            try:
                producer.close(timeout=config.KAFKA_TIMEOUT)
            except Exception:  # noqa: BLE001 — закрытие не должно влиять на результат
                pass
