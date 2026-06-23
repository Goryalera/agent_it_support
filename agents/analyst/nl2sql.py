"""NL→SQL: вопрос на естественном языке → безопасный SELECT → текстовая сводка.

LLM получает схему таблицы и вопрос, генерирует SQL. Дальше за безопасность
отвечает `tickets_db` (валидация + read-only + authorizer) — модели мы не верим.
"""

from __future__ import annotations

from agents.analyst import tickets_db
from shared.llm import ask_llm

_SQL_SYSTEM = (
    "Ты — аналитик данных. По вопросу пользователя сгенерируй ОДИН SQL-запрос "
    "для SQLite. Разрешён только SELECT (или WITH … SELECT), без изменения данных. "
    "Используй только описанную таблицу и колонки. Не добавляй пояснений и "
    "markdown — верни ТОЛЬКО текст SQL-запроса, без точки с запятой в конце."
)

_SUMMARY_SYSTEM = (
    "Ты — аналитик ИТ-поддержки. По вопросу и результату SQL-запроса дай короткий "
    "ответ на русском языке: одно-два предложения с конкретными числами из данных. "
    "Не выдумывай ничего сверх результата запроса."
)


def generate_sql(question: str) -> str:
    """Попросить LLM сгенерировать SELECT по вопросу (с описанием схемы)."""
    prompt = (
        f"{tickets_db.schema_description()}\n\n"
        f"Вопрос: {question}\n\n"
        f"SQL-запрос (только SELECT):"
    )
    return ask_llm(prompt, system=_SQL_SYSTEM)


def _format_result_for_llm(result: dict, max_rows: int = 30) -> str:
    """Компактно отформатировать результат запроса для промпта-сводки."""
    cols = result["columns"]
    rows = result["rows"][:max_rows]
    lines = [" | ".join(cols)]
    for r in rows:
        lines.append(" | ".join("" if v is None else str(v) for v in r))
    extra = ""
    if result["row_count"] > max_rows:
        extra = f"\n… и ещё {result['row_count'] - max_rows} строк."
    return "\n".join(lines) + extra


def summarize(question: str, result: dict) -> str:
    """Превратить табличный результат в короткий текстовый ответ через LLM."""
    table = _format_result_for_llm(result)
    prompt = (
        f"Вопрос: {question}\n\n"
        f"Результат SQL-запроса ({result['row_count']} строк):\n{table}\n\n"
        f"Краткий ответ:"
    )
    return ask_llm(prompt, system=_SUMMARY_SYSTEM)
