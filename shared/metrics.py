"""Кастомные метрики LLM для Prometheus (Слой 4).

HTTP-метрики агентов (латентность, число вызовов, ошибки) даёт
prometheus-fastapi-instrumentator на эндпоинте /metrics. Здесь — то, что он не
знает: вызовы LLM и расход токенов.

Модуль деградирует мягко: если `prometheus_client` не установлен (например, в
окружении тестов), все функции становятся no-op и ничего не ломают.
"""

from __future__ import annotations

try:
    from prometheus_client import Counter

    _ENABLED = True
except ImportError:  # prometheus_client не установлен — метрики выключены
    _ENABLED = False

if _ENABLED:
    LLM_REQUESTS = Counter(
        "askops_llm_requests_total",
        "Число вызовов LLM",
        ["provider", "mode"],
    )
    LLM_TOKENS = Counter(
        "askops_llm_tokens_total",
        "Расход токенов LLM",
        ["provider", "kind"],  # kind: prompt | completion
    )


def record_llm_call(
    provider: str,
    mode: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Учесть один вызов LLM и потраченные токены (если метрики включены)."""
    if not _ENABLED:
        return
    LLM_REQUESTS.labels(provider=provider, mode=mode).inc()
    if prompt_tokens:
        LLM_TOKENS.labels(provider=provider, kind="prompt").inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS.labels(provider=provider, kind="completion").inc(completion_tokens)
