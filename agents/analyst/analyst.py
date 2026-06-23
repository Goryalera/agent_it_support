"""Логика аналитик-агента: вопрос → NL→SQL → безопасный SELECT → сводка.

Главная функция `answer_question` собирает конвейер и возвращает и текстовый
ответ, и сам SQL (для прозрачности — видно, что именно выполнил агент).
"""

from __future__ import annotations

from agents.analyst import nl2sql, tickets_db


def _format_answer(summary: str, sql: str) -> str:
    """Текстовый ответ + показанный SQL — прозрачность того, что выполнил агент."""
    return f"{summary.strip()}\n\nЗапрос: {sql}"


def answer_question(question: str) -> dict:
    """Ответить на вопрос по статистике тикетов.

    Returns:
        {"answer": str, "sql": str, "row_count": int, "found": bool}
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "Пустой вопрос.", "sql": "", "row_count": 0, "found": False}

    # 1. LLM генерирует SQL по схеме и вопросу.
    raw_sql = nl2sql.generate_sql(question)

    # 2. Безопасное выполнение: валидация + read-only + authorizer + лимит.
    try:
        result = tickets_db.run_select(raw_sql)
    except tickets_db.UnsafeSQLError as exc:
        return {
            "answer": (
                "Не могу выполнить этот запрос по соображениям безопасности: "
                f"{exc}. Переформулируйте вопрос."
            ),
            "sql": raw_sql.strip(),
            "row_count": 0,
            "found": False,
        }
    except Exception as exc:  # noqa: BLE001 — ошибка БД/SQL → понятный ответ, не трейсбек
        return {
            "answer": (
                "Не удалось выполнить запрос к базе тикетов. "
                "Возможно, вопрос вне доступных данных."
            ),
            "sql": raw_sql.strip(),
            "row_count": 0,
            "found": False,
            "error": str(exc),
        }

    # 3. LLM делает короткую текстовую сводку по результату.
    summary = nl2sql.summarize(question, result)

    return {
        "answer": _format_answer(summary, result["sql"]),
        "sql": result["sql"],
        "row_count": result["row_count"],
        "found": True,
    }
