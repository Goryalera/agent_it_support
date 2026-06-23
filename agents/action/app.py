"""Сервис action-агента.

Два интерфейса в одном процессе (как у RAG и аналитика):
- REST (FastAPI): POST /ask и GET /health — для прямой проверки.
- A2A (смонтирован в корень): Agent Card на /.well-known/agent.json и
  A2A-эндпоинт — основной канал общения с оркестратором.

Запуск:
    uvicorn agents.action.app:app --host 0.0.0.0 --port 8003
"""

from __future__ import annotations

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI
from pydantic import BaseModel

from agents.action.a2a_server import ActionAgentExecutor, build_agent_card
from agents.action.action import create_ticket
from shared import config
from shared.observability import setup_metrics


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    ticket_number: str
    category: str
    priority: str
    published: bool
    found: bool


app = FastAPI(title="AskOps Action Agent", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "action"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Прямой REST-доступ к action-агенту (минуя A2A) — для отладки и тестов."""
    result = create_ticket(req.question)
    return AskResponse(
        answer=result["answer"],
        ticket_number=result.get("ticket_number", ""),
        category=result.get("category", ""),
        priority=result.get("priority", ""),
        published=result.get("published", False),
        found=result["found"],
    )


# /metrics для Prometheus — до монтирования A2A в корень.
setup_metrics(app)


# ── A2A: монтируем в корень ──────────────────────────────────────────────────
_agent_card = build_agent_card(url=config.ACTION_AGENT_URL)
_request_handler = DefaultRequestHandler(
    agent_executor=ActionAgentExecutor(),
    task_store=InMemoryTaskStore(),
)
_a2a_app = A2AStarletteApplication(
    agent_card=_agent_card,
    http_handler=_request_handler,
)
# REST-маршруты (/health, /ask) объявлены раньше и имеют приоритет над mount.
app.mount("/", _a2a_app.build())
