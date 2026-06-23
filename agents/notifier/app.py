"""Сервис агента-нотификатора.

FastAPI-обёртка вокруг consumer: в фоне крутится поток-потребитель Kafka, а REST
даёт /health и /notifications (последние уведомления — для проверки и UI).

Запуск:
    uvicorn agents.notifier.app:app --host 0.0.0.0 --port 8004
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agents.notifier import consumer
from shared.observability import setup_metrics

_stop_event = threading.Event()
_consumer_thread: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Поднять фоновый поток-потребитель на старте, остановить на выключении."""
    global _consumer_thread
    _stop_event.clear()
    _consumer_thread = threading.Thread(
        target=consumer.run_consumer, args=(_stop_event,), daemon=True
    )
    _consumer_thread.start()
    yield
    _stop_event.set()


app = FastAPI(title="AskOps Notifier", version="0.1.0", lifespan=lifespan)
setup_metrics(app)  # /metrics для Prometheus (Слой 4)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "notifier"}


@app.get("/notifications")
def notifications(limit: int = 50) -> dict:
    """Последние «отправленные» уведомления (из лог-файла)."""
    return {"notifications": consumer.read_recent(limit)}
