"""Сервис оркестратора (точка входа для пользователя).

REST-эндпоинт POST /ask принимает вопрос, прогоняет через граф LangGraph
(который по A2A зовёт RAG-агента) и возвращает ответ.

Запуск:
    uvicorn agents.orchestrator.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from agents.orchestrator.graph import build_graph
from shared.observability import setup_metrics

app = FastAPI(title="AskOps Orchestrator", version="0.1.0")
setup_metrics(app)  # /metrics для Prometheus (Слой 4)
_graph = build_graph()


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "orchestrator"}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    result = await _graph.ainvoke({"question": req.question})
    return AskResponse(answer=result.get("answer", ""))
