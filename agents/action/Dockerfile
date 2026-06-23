# Action-агент: создаёт тикеты в SQLite + публикует события в Kafka/Redpanda.
# Контекст сборки — корень репозитория (см. docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY agents/action/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY shared ./shared
COPY agents/__init__.py ./agents/__init__.py
COPY agents/action ./agents/action
# tickets_db нужен для записи тикетов в общую базу (read-write).
COPY agents/analyst/__init__.py ./agents/analyst/__init__.py
COPY agents/analyst/tickets_db.py ./agents/analyst/tickets_db.py

EXPOSE 8003

CMD ["uvicorn", "agents.action.app:app", "--host", "0.0.0.0", "--port", "8003"]
