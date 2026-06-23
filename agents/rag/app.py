"""Сервис RAG-агента.

Два интерфейса в одном процессе:
- REST (FastAPI): POST /ask и GET /health — для прямой проверки агента.
- A2A (смонтирован в корень): Agent Card на /.well-known/agent.json и
  A2A-эндпоинт — основной канал общения с оркестратором.

Запуск:
    uvicorn agents.rag.app:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI
from pydantic import BaseModel

from agents.rag.a2a_server import RagAgentExecutor, build_agent_card
from agents.rag.rag import answer_question
from shared import config
from shared.observability import setup_metrics


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]
    found: bool


app = FastAPI(title="AskOps RAG Agent", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "rag"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Прямой REST-доступ к RAG (минуя A2A) — удобно для отладки и тестов."""
    # sync-функция: FastAPI выполнит её в threadpool, не блокируя event loop.
    result = answer_question(req.question)
    return AskResponse(**result)


# /metrics для Prometheus — до монтирования A2A в корень, иначе путь перехватится.
setup_metrics(app)


# ── A2A: монтируем в корень ──────────────────────────────────────────────────
# Agent Card указывает на публичный URL агента (внутри compose-сети — http://rag:8001).
_agent_card = build_agent_card(url=config.RAG_AGENT_URL)
_request_handler = DefaultRequestHandler(
    agent_executor=RagAgentExecutor(),
    task_store=InMemoryTaskStore(),
)
_a2a_app = A2AStarletteApplication(
    agent_card=_agent_card,
    http_handler=_request_handler,
)
# Стартлет-приложение A2A обслуживает /.well-known/agent.json и A2A-RPC в корне.
# REST-маршруты выше (/health, /ask) объявлены раньше и имеют приоритет.
app.mount("/", _a2a_app.build())
