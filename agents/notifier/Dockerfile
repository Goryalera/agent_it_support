# Агент-нотификатор: consumer Kafka/Redpanda + маленький FastAPI (/health, /notifications).
# Контекст сборки — корень репозитория (см. docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY agents/notifier/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY shared ./shared
COPY agents/__init__.py ./agents/__init__.py
COPY agents/notifier ./agents/notifier

EXPOSE 8004

CMD ["uvicorn", "agents.notifier.app:app", "--host", "0.0.0.0", "--port", "8004"]
