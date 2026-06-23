"""Сервис аналитик-агента.

Два интерфейса в одном процессе (как у RAG-агента):
- REST (FastAPI): POST /ask и GET /health — для прямой проверки.
- A2A (смонтирован в корень): Agent Card на /.well-known/agent.json и
  A2A-эндпоинт — основной канал общения с оркестратором.

Запуск:
    uvicorn agents.analyst.app:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI
from pydantic import BaseModel

from agents.analyst.a2a_server import AnalystAgentExecutor, build_agent_card
from agents.analyst.analyst import answer_question
from shared import config
from shared.observability import setup_metrics


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sql: str
    row_count: int
    found: bool


app = FastAPI(title="AskOps Analyst Agent", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "analyst"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Прямой REST-доступ к аналитику (минуя A2A) — для отладки и тестов."""
    result = answer_question(req.question)
    return AskResponse(
        answer=result["answer"],
        sql=result.get("sql", ""),
        row_count=result.get("row_count", 0),
        found=result["found"],
    )


# /metrics для Prometheus — до монтирования A2A в корень.
setup_metrics(app)


# ── A2A: монтируем в корень ──────────────────────────────────────────────────
_agent_card = build_agent_card(url=config.ANALYST_AGENT_URL)
_request_handler = DefaultRequestHandler(
    agent_executor=AnalystAgentExecutor(),
    task_store=InMemoryTaskStore(),
)
_a2a_app = A2AStarletteApplication(
    agent_card=_agent_card,
    http_handler=_request_handler,
)
# REST-маршруты (/health, /ask) объявлены раньше и имеют приоритет над mount.
app.mount("/", _a2a_app.build())
