# Аналитик-агент: NL→SQL по базе тикетов (SQLite) + A2A-сервер.
# Контекст сборки — корень репозитория (см. docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY agents/analyst/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY shared ./shared
COPY agents/__init__.py ./agents/__init__.py
COPY agents/analyst ./agents/analyst

EXPOSE 8002

# Сгенерировать базу тикетов (если нужно), затем поднять сервис.
CMD ["sh", "-c", "python -m agents.analyst.startup && uvicorn agents.analyst.app:app --host 0.0.0.0 --port 8002"]
