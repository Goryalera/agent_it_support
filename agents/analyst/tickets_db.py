"""Доступ к базе тикетов (SQLite) для аналитика — только чтение и только SELECT.

Это «горячая точка безопасности» аналитик-агента (прямой пункт вакансии про
безопасность агентов). LLM генерирует SQL, но мы НЕ доверяем ему слепо:

1. Коннект открывается в режиме read-only (`mode=ro`) — даже валидный
   INSERT/UPDATE физически не выполнится.
2. Запрос проходит статическую валидацию `validate_select`: ровно один
   оператор, начинается с SELECT/WITH, без запрещённых ключевых слов.
3. На время выполнения вешается SQLite-authorizer, который пропускает только
   операции чтения (SELECT/READ) — defense-in-depth поверх режима ro.
4. Результат ограничен лимитом строк.

Любое нарушение — исключение `UnsafeSQLError`, наружу уходит понятный отказ, а не
произвольный SQL от модели.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shared import config

# Категории, команды, статусы, приоритеты, каналы — единый словарь для генератора
# данных и для описания схемы, которое уходит в LLM.
CATEGORIES = ["доступы", "сеть", "железо", "ПО", "учётки"]
PRIORITIES = ["низкий", "средний", "высокий", "критический"]
STATUSES = ["создан", "в работе", "ожидает", "решён", "закрыт"]
CHANNELS = ["почта", "портал", "телефон", "чат", "лично"]
TEAMS = [
    "Service Desk",
    "Сетевая команда",
    "Команда железа",
    "Команда ПО",
    "Команда доступов",
]

# Команда-исполнитель по категории — единый источник для генератора и action-агента.
TEAM_BY_CATEGORY = {
    "доступы": "Команда доступов",
    "учётки": "Service Desk",
    "ПО": "Команда ПО",
    "сеть": "Сетевая команда",
    "железо": "Команда железа",
}


def team_for_category(category: str) -> str:
    """Команда-исполнитель для категории (с разумным значением по умолчанию)."""
    return TEAM_BY_CATEGORY.get(category, "Service Desk")

TABLE_NAME = "tickets"

# DDL таблицы тикетов — единый источник схемы для генератора и action-агента.
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    ticket_number      TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    closed_at          TEXT,
    category           TEXT NOT NULL,
    priority           TEXT NOT NULL,
    status             TEXT NOT NULL,
    team               TEXT NOT NULL,
    channel            TEXT NOT NULL,
    resolution_minutes INTEGER,
    text               TEXT NOT NULL
);
"""

# Запрещённые ключевые слова — любое из них в запросе считаем небезопасным.
# Регистр игнорируем; проверяем по границам слова, чтобы не ловить подстроки
# (например, "created_at" не должен срабатывать на "create").
_FORBIDDEN_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "truncate",
    "attach",
    "detach",
    "pragma",
    "vacuum",
    "reindex",
    "grant",
    "revoke",
    "commit",
    "rollback",
    "begin",
}


class UnsafeSQLError(ValueError):
    """Сгенерированный SQL не прошёл проверку безопасности."""


def schema_description() -> str:
    """Человекочитаемое описание схемы — уходит в промпт LLM для NL→SQL."""
    return (
        f"Таблица `{TABLE_NAME}` — заявки (тикеты) ИТ-поддержки. Колонки:\n"
        "- ticket_number (TEXT) — номер тикета, напр. 'INC-000123'.\n"
        "- created_at (TEXT, ISO-дата 'YYYY-MM-DD HH:MM:SS') — когда создан.\n"
        "- closed_at (TEXT или NULL) — когда закрыт; NULL, если ещё не закрыт.\n"
        f"- category (TEXT) — категория, одно из: {', '.join(CATEGORIES)}.\n"
        f"- priority (TEXT) — приоритет, одно из: {', '.join(PRIORITIES)}.\n"
        f"- status (TEXT) — статус, одно из: {', '.join(STATUSES)}.\n"
        f"- team (TEXT) — команда-исполнитель, одно из: {', '.join(TEAMS)}.\n"
        f"- channel (TEXT) — канал обращения, одно из: {', '.join(CHANNELS)}.\n"
        "- resolution_minutes (INTEGER или NULL) — время решения в минутах.\n"
        "- text (TEXT) — текст обращения сотрудника.\n"
        "\n"
        "Даты хранятся как строки ISO. Для фильтра по месяцу используй "
        "strftime('%Y-%m', created_at) = 'YYYY-MM'. Сегодня — это максимум "
        "created_at в таблице."
    )


def db_path() -> Path:
    """Абсолютный путь к файлу базы тикетов."""
    raw = Path(config.TICKETS_DB_PATH)
    if raw.is_absolute():
        return raw
    # Относительный путь считаем от корня репозитория.
    return Path(__file__).resolve().parents[2] / raw


def connect_rw(path: Path | None = None) -> sqlite3.Connection:
    """Коннект на запись — только для генератора данных (создаёт файл)."""
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def connect_ro(path: Path | None = None) -> sqlite3.Connection:
    """Коннект только на чтение (SQLite URI `mode=ro`).

    Физически запрещает любые изменения базы — первый рубеж защиты.
    """
    path = path or db_path()
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _strip_sql(sql: str) -> str:
    """Убрать markdown-обёртки и лишние точки с запятой по краям."""
    s = sql.strip()
    if s.startswith("```"):
        # ```sql\n ... \n```
        s = s.split("\n", 1)[-1] if "\n" in s else s
        s = s.replace("```sql", "").replace("```SQL", "").replace("```", "")
    return s.strip().rstrip(";").strip()


def validate_select(sql: str) -> str:
    """Проверить, что запрос — безопасный одиночный SELECT. Вернуть очищенный SQL.

    Raises:
        UnsafeSQLError: если запрос пустой, состоит из нескольких операторов,
            не начинается с SELECT/WITH или содержит запрещённое ключевое слово.
    """
    cleaned = _strip_sql(sql)
    if not cleaned:
        raise UnsafeSQLError("Пустой SQL-запрос.")

    # Несколько операторов через ';' — запрещаем (после strip остаётся максимум один).
    if ";" in cleaned:
        raise UnsafeSQLError("Разрешён только один SQL-оператор.")

    lowered = cleaned.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise UnsafeSQLError("Разрешены только запросы SELECT (или WITH … SELECT).")

    # Поиск запрещённых ключевых слов по границам слова.
    tokens = set(_tokenize(lowered))
    bad = tokens & _FORBIDDEN_KEYWORDS
    if bad:
        raise UnsafeSQLError(f"Запрещённые операции в запросе: {', '.join(sorted(bad))}.")

    return cleaned


def _tokenize(text: str) -> list[str]:
    """Грубая токенизация по не-буквам — для проверки ключевых слов."""
    token = []
    out = []
    for ch in text:
        if ch.isalpha() or ch == "_":
            token.append(ch)
        else:
            if token:
                out.append("".join(token))
                token = []
    if token:
        out.append("".join(token))
    return out


def _read_only_authorizer(action, arg1, arg2, db_name, trigger):
    """SQLite-authorizer: пропускаем только чтение, остальное запрещаем.

    Вызывается движком на каждую операцию подготавливаемого запроса.
    Возвращаем sqlite3.SQLITE_OK для безопасных, иначе SQLITE_DENY.
    """
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,  # разрешаем агрегаты/strftime и т.п.
    }
    if action in allowed:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def next_ticket_number(conn: sqlite3.Connection, prefix: str = "REQ") -> str:
    """Сгенерировать следующий номер тикета с заданным префиксом.

    Считаем максимальный существующий номер с этим префиксом и прибавляем 1.
    Используется action-агентом при создании новых заявок.
    """
    cur = conn.execute(
        f"SELECT ticket_number FROM {TABLE_NAME} WHERE ticket_number LIKE ? "
        "ORDER BY ticket_number DESC LIMIT 1",
        (f"{prefix}-%",),
    )
    row = cur.fetchone()
    last = 0
    if row is not None:
        try:
            last = int(str(row[0]).split("-")[-1])
        except (ValueError, IndexError):
            last = 0
    return f"{prefix}-{last + 1:06d}"


def ensure_table(conn: sqlite3.Connection) -> None:
    """Создать таблицу тикетов, если её ещё нет (без наполнения данными)."""
    conn.execute(CREATE_TABLE_SQL)


def insert_ticket(ticket: dict) -> None:
    """Записать новый тикет в базу (write-коннект). Для action-агента."""
    columns = (
        "ticket_number",
        "created_at",
        "closed_at",
        "category",
        "priority",
        "status",
        "team",
        "channel",
        "resolution_minutes",
        "text",
    )
    placeholders = ", ".join(f":{c}" for c in columns)
    conn = connect_rw()
    try:
        ensure_table(conn)
        conn.execute(
            f"INSERT INTO {TABLE_NAME} ({', '.join(columns)}) VALUES ({placeholders})",
            {c: ticket.get(c) for c in columns},
        )
        conn.commit()
    finally:
        conn.close()


def run_select(sql: str, limit: int | None = None) -> dict:
    """Безопасно выполнить SELECT и вернуть колонки + строки.

    Применяет: валидацию, read-only коннект, authorizer и лимит строк.

    Returns:
        {"sql": str, "columns": [..], "rows": [[..], ..], "row_count": int}
    """
    limit = limit or config.ANALYST_MAX_ROWS
    cleaned = validate_select(sql)

    conn = connect_ro()
    try:
        conn.set_authorizer(_read_only_authorizer)
        cur = conn.execute(cleaned)
        rows = cur.fetchmany(limit)
        columns = [d[0] for d in cur.description] if cur.description else []
        data = [list(r) for r in rows]
    finally:
        conn.close()

    return {
        "sql": cleaned,
        "columns": columns,
        "rows": data,
        "row_count": len(data),
    }
