# RAG-агент: kNN-поиск в OpenSearch + LLM + A2A-сервер.
# Контекст сборки — корень репозитория (см. docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Зависимости отдельным слоем — кэшируются, пока requirements не меняются.
COPY agents/rag/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Заранее скачиваем модель эмбеддингов в образ, чтобы агент работал офлайн
# и не качал веса при первом запросе.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# Код и база знаний.
COPY shared ./shared
COPY agents/__init__.py ./agents/__init__.py
COPY agents/rag ./agents/rag
COPY docs/knowledge_base ./docs/knowledge_base

EXPOSE 8001

# Дождаться OpenSearch и проиндексировать (если нужно), затем поднять сервис.
CMD ["sh", "-c", "python -m agents.rag.startup && uvicorn agents.rag.app:app --host 0.0.0.0 --port 8001"]
