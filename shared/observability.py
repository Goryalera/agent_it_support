"""Подключение Prometheus-метрик к FastAPI-приложению (Слой 4).

`setup_metrics(app)` вешает prometheus-fastapi-instrumentator: он собирает
HTTP-метрики (латентность, число запросов, ошибки по эндпоинтам) и публикует их
на `/metrics`. Кастомные метрики LLM/токенов — в shared/metrics.py.

Деградирует мягко: если библиотека не установлена, просто ничего не делает —
агент работает как раньше, только без /metrics.
"""

from __future__ import annotations


def setup_metrics(app) -> None:
    """Включить /metrics на приложении, если доступен инструментатор."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
    except ImportError:
        return
    # instrument — вешает middleware на сбор метрик; expose — добавляет GET /metrics.
    # Для агентов с A2A важно вызвать это ДО app.mount("/", …), иначе монтированное
    # приложение перехватит путь /metrics.
    Instrumentator().instrument(app).expose(app, include_in_schema=False)
