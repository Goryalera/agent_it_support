"""Чтение конфигурации из переменных окружения в одном месте.

Все модули берут настройки отсюда, а не из os.environ напрямую — так проще
менять и тестировать.
"""

from __future__ import annotations

import os


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ── LLM ─────────────────────────────────────────────────────────────────────
# Режим: real — реальный вызов провайдера; mock — заглушка (тесты/CI/демо).
LLM_MODE = _get("LLM_MODE", "real").strip().lower()
# Провайдер при LLM_MODE=real: gigachat | openrouter.
LLM_PROVIDER = _get("LLM_PROVIDER", "gigachat").strip().lower()

# ── GigaChat ────────────────────────────────────────────────────────────────
GIGACHAT_CREDENTIALS = _get("GIGACHAT_CREDENTIALS")
GIGACHAT_SCOPE = _get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_MODEL = _get("GIGACHAT_MODEL", "GigaChat")
GIGACHAT_VERIFY_SSL_CERTS = _get_bool("GIGACHAT_VERIFY_SSL_CERTS", False)

# ── OpenRouter (OpenAI-совместимый API) ─────────────────────────────────────
OPENROUTER_API_KEY = _get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = _get("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
OPENROUTER_BASE_URL = _get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# Необязательные заголовки для рейтинга приложения на openrouter.ai.
OPENROUTER_SITE_URL = _get("OPENROUTER_SITE_URL")
OPENROUTER_APP_NAME = _get("OPENROUTER_APP_NAME", "AskOps")

# ── Эмбеддинги ──────────────────────────────────────────────────────────────
EMBEDDING_MODEL = _get(
    "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
EMBEDDING_DIM = _get_int("EMBEDDING_DIM", 384)

# ── OpenSearch ──────────────────────────────────────────────────────────────
OPENSEARCH_HOST = _get("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = _get_int("OPENSEARCH_PORT", 9200)
OPENSEARCH_INDEX = _get("OPENSEARCH_INDEX", "askops-kb")

# ── RAG-агент ───────────────────────────────────────────────────────────────
RAG_HOST = _get("RAG_HOST", "0.0.0.0")
RAG_PORT = _get_int("RAG_PORT", 8001)
RAG_AGENT_URL = _get("RAG_AGENT_URL", "http://localhost:8001")
RAG_TOP_K = _get_int("RAG_TOP_K", 4)

# ── Аналитик-агент (Слой 1) ─────────────────────────────────────────────────
ANALYST_HOST = _get("ANALYST_HOST", "0.0.0.0")
ANALYST_PORT = _get_int("ANALYST_PORT", 8002)
ANALYST_AGENT_URL = _get("ANALYST_AGENT_URL", "http://localhost:8002")
# Путь к SQLite-базе тикетов (read-only для аналитика).
TICKETS_DB_PATH = _get("TICKETS_DB_PATH", "data/tickets.db")
# Сколько строк максимум возвращает сгенерированный SELECT (защита от тяжёлых выборок).
ANALYST_MAX_ROWS = _get_int("ANALYST_MAX_ROWS", 200)
# Сколько строк тикетов генерировать синтетически.
TICKETS_COUNT = _get_int("TICKETS_COUNT", 5000)

# ── Action-агент и очередь событий (Слой 2) ─────────────────────────────────
ACTION_HOST = _get("ACTION_HOST", "0.0.0.0")
ACTION_PORT = _get_int("ACTION_PORT", 8003)
ACTION_AGENT_URL = _get("ACTION_AGENT_URL", "http://localhost:8003")
# Kafka-совместимый брокер (Redpanda). Один топик на события по тикетам.
KAFKA_BOOTSTRAP_SERVERS = _get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = _get("KAFKA_TOPIC", "ticket-events")
# Таймаут на установку соединения с брокером (сек) — чтобы создание тикета не
# зависало, если очередь недоступна.
KAFKA_TIMEOUT = _get_int("KAFKA_TIMEOUT", 5)

# ── Агент-нотификатор (Слой 2) ──────────────────────────────────────────────
NOTIFIER_HOST = _get("NOTIFIER_HOST", "0.0.0.0")
NOTIFIER_PORT = _get_int("NOTIFIER_PORT", 8004)
# Куда нотификатор «отправляет» уведомления (в простом виде — файл + консоль).
NOTIFICATIONS_FILE = _get("NOTIFICATIONS_FILE", "data/notifications.log")
KAFKA_CONSUMER_GROUP = _get("KAFKA_CONSUMER_GROUP", "askops-notifier")

# ── Оркестратор ─────────────────────────────────────────────────────────────
ORCHESTRATOR_HOST = _get("ORCHESTRATOR_HOST", "0.0.0.0")
ORCHESTRATOR_PORT = _get_int("ORCHESTRATOR_PORT", 8000)
ORCHESTRATOR_URL = _get("ORCHESTRATOR_URL", "http://localhost:8000")
