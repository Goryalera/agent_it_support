"""Тесты аналитик-агента: безопасность NL→SQL и конвейер ответа.

Главное здесь — проверить «горячую точку безопасности»: модель может сгенерировать
любой SQL, но наружу пройдёт только безопасный SELECT. LLM в mock-режиме
(см. conftest), генерацию SQL мокаем напрямую.
"""

from __future__ import annotations

import sqlite3

import pytest

from agents.analyst import analyst, tickets_db
from shared import config


@pytest.fixture
def tiny_db(tmp_path, monkeypatch):
    """Маленькая база тикетов во временном файле."""
    db = tmp_path / "tickets.db"
    monkeypatch.setattr(config, "TICKETS_DB_PATH", str(db))
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE tickets "
        "(ticket_number TEXT, category TEXT, resolution_minutes INTEGER)"
    )
    conn.executemany(
        "INSERT INTO tickets VALUES (?,?,?)",
        [
            ("INC-1", "доступы", 10),
            ("INC-2", "доступы", 20),
            ("INC-3", "сеть", 30),
        ],
    )
    conn.commit()
    conn.close()
    return db


# ── Безопасность валидации (без обращения к БД) ──────────────────────────────


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE tickets",
        "DELETE FROM tickets",
        "UPDATE tickets SET text='x'",
        "INSERT INTO tickets VALUES (1)",
        "SELECT 1; DROP TABLE tickets",
        "PRAGMA table_info(tickets)",
        "ATTACH DATABASE 'x' AS y",
        "",
        "   ",
    ],
)
def test_validate_select_rejects_unsafe(bad_sql):
    with pytest.raises(tickets_db.UnsafeSQLError):
        tickets_db.validate_select(bad_sql)


@pytest.mark.parametrize(
    "good_sql",
    [
        "SELECT COUNT(*) FROM tickets",
        "select category from tickets",
        "WITH t AS (SELECT * FROM tickets) SELECT COUNT(*) FROM t",
        "```sql\nSELECT category FROM tickets\n```",
        "SELECT * FROM tickets;",  # завершающая ';' срезается, остаётся один оператор
    ],
)
def test_validate_select_accepts_safe(good_sql):
    cleaned = tickets_db.validate_select(good_sql)
    assert cleaned.lower().startswith(("select", "with"))
    assert ";" not in cleaned


# ── Исполнение (read-only + authorizer + лимит) ──────────────────────────────


def test_run_select_returns_rows(tiny_db):
    result = tickets_db.run_select(
        "SELECT category, COUNT(*) c FROM tickets GROUP BY category ORDER BY c DESC"
    )
    assert result["columns"] == ["category", "c"]
    assert result["rows"][0] == ["доступы", 2]
    assert result["row_count"] == 2


def test_run_select_applies_limit(tiny_db):
    result = tickets_db.run_select("SELECT ticket_number FROM tickets", limit=2)
    assert result["row_count"] == 2


def test_run_select_blocks_write_via_validation(tiny_db):
    with pytest.raises(tickets_db.UnsafeSQLError):
        tickets_db.run_select("DELETE FROM tickets")


def test_readonly_connection_physically_blocks_writes(tiny_db):
    """Даже в обход валидации read-only коннект не даст изменить базу."""
    conn = tickets_db.connect_ro()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM tickets")
    conn.close()


# ── Конвейер answer_question ─────────────────────────────────────────────────


def test_answer_question_happy_path(tiny_db, monkeypatch):
    monkeypatch.setattr(
        analyst.nl2sql,
        "generate_sql",
        lambda _q: "SELECT category, COUNT(*) FROM tickets GROUP BY category",
    )
    monkeypatch.setattr(
        analyst.nl2sql, "summarize", lambda _q, _r: "Больше всего по доступам."
    )
    result = analyst.answer_question("сколько тикетов по категориям")

    assert result["found"] is True
    assert "доступам" in result["answer"]
    assert "SELECT" in result["sql"].upper()


def test_answer_question_rejects_unsafe_sql(tiny_db, monkeypatch):
    """LLM сгенерировал опасный SQL → агент честно отказывает, базу не трогает."""
    monkeypatch.setattr(analyst.nl2sql, "generate_sql", lambda _q: "DROP TABLE tickets")

    result = analyst.answer_question("удали все тикеты")

    assert result["found"] is False
    assert "безопасност" in result["answer"].lower()


def test_answer_question_empty(tiny_db):
    result = analyst.answer_question("   ")
    assert result["found"] is False
