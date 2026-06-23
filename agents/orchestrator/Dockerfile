# Оркестратор: LangGraph-граф + A2A-клиент + REST /ask.
# Контекст сборки — корень репозитория (см. docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY agents/orchestrator/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY shared ./shared
COPY agents/__init__.py ./agents/__init__.py
COPY agents/orchestrator ./agents/orchestrator

EXPOSE 8000

CMD ["uvicorn", "agents.orchestrator.app:app", "--host", "0.0.0.0", "--port", "8000"]
