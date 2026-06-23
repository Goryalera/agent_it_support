"""Генератор синтетической выгрузки тикетов хелпдеска (Faker → SQLite).

Создаёт правдоподобную историю обращений за ~год: с перекосами распределений,
которые делают аналитику осмысленной (доступов больше, чем поломок железа; пик
обращений в понедельник; редкие долгие инциденты).

Данные синтетические и осознанно так заявлены — реального доступа к корпоративным
системам у пет-проекта нет. Зерно фиксировано, поэтому выгрузка воспроизводима.

Запуск:
    python -m agents.analyst.generate_tickets
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

from agents.analyst import tickets_db
from shared import config

SEED = 42

# Перекос по категориям: доступов и учёток много, железа мало.
_CATEGORY_WEIGHTS = {
    "доступы": 0.34,
    "учётки": 0.24,
    "ПО": 0.18,
    "сеть": 0.16,
    "железо": 0.08,
}

# Команда-исполнитель по категории — берём из общего словаря (tickets_db).
_TEAM_BY_CATEGORY = tickets_db.TEAM_BY_CATEGORY

_PRIORITY_WEIGHTS = {
    "низкий": 0.30,
    "средний": 0.45,
    "высокий": 0.20,
    "критический": 0.05,
}

_CHANNEL_WEIGHTS = {
    "портал": 0.40,
    "почта": 0.28,
    "телефон": 0.16,
    "чат": 0.12,
    "лично": 0.04,
}

# Вес дня недели: понедельник пиковый, выходные тихие (0=пн … 6=вс).
_WEEKDAY_WEIGHTS = [0.22, 0.18, 0.16, 0.15, 0.14, 0.08, 0.07]

# Базовое время решения (минуты) по приоритету — медиана.
_BASE_RESOLUTION = {
    "низкий": 240,
    "средний": 120,
    "высокий": 60,
    "критический": 30,
}

# Шаблоны текста обращения по категории.
_TEXT_TEMPLATES = {
    "доступы": [
        "Нужен доступ к {sys}. Оформите, пожалуйста.",
        "Не могу зайти в {sys}, пишет «нет прав».",
        "Прошу выдать права на {sys} для работы.",
    ],
    "учётки": [
        "Забыл пароль от корпоративной почты, помогите восстановить.",
        "Заблокировалась учётная запись после отпуска.",
        "Нужно завести учётку новому сотруднику.",
    ],
    "ПО": [
        "Не устанавливается {sys}, выдаёт ошибку.",
        "Прошу установить {sys} на рабочий ноутбук.",
        "{sys} вылетает при запуске, нужна помощь.",
    ],
    "сеть": [
        "Не подключается VPN с домашнего ноутбука.",
        "Пропал интернет на рабочем месте.",
        "Не вижу корпоративный Wi-Fi на телефоне.",
    ],
    "железо": [
        "Не печатает сетевой принтер на этаже.",
        "Ноутбук не включается, нужен ремонт.",
        "Сломалась док-станция, не видит монитор.",
    ],
}

_SYSTEMS = ["Jira", "Confluence", "1С", "CRM", "общей папке", "GitLab", "VPN"]


def _weighted_choice(faker, weights: dict) -> str:
    """Выбрать ключ словаря пропорционально весам (через Faker для детерминизма)."""
    items = list(weights.items())
    r = faker.pyfloat(min_value=0, max_value=1, right_digits=6)
    acc = 0.0
    for key, w in items:
        acc += w
        if r <= acc:
            return key
    return items[-1][0]


def _pick_created_at(faker, start: datetime, end: datetime) -> datetime:
    """Дата создания в [start, end] с перекосом на понедельник и рабочие часы."""
    total_days = (end - start).days
    # Несколько попыток подобрать день с нужным днём недели (rejection sampling).
    day = start + timedelta(days=faker.random_int(min=0, max=total_days))
    for _ in range(6):
        day_offset = faker.random_int(min=0, max=total_days)
        day = start + timedelta(days=day_offset)
        weight = _WEEKDAY_WEIGHTS[day.weekday()]
        if faker.pyfloat(min_value=0, max_value=1, right_digits=6) <= weight / 0.22:
            break
    hour = faker.random_int(min=8, max=19)
    minute = faker.random_int(min=0, max=59)
    second = faker.random_int(min=0, max=59)
    return day.replace(hour=hour, minute=minute, second=second, microsecond=0)


def _resolution_minutes(faker, priority: str) -> int:
    """Время решения: базовое по приоритету × разброс, с редкими длинными хвостами."""
    base = _BASE_RESOLUTION[priority]
    factor = faker.pyfloat(min_value=0.3, max_value=2.5, right_digits=2)
    minutes = int(base * factor)
    # Редкий долгий инцидент (≈4%): растягиваем в разы.
    if faker.pyfloat(min_value=0, max_value=1, right_digits=4) < 0.04:
        minutes *= faker.random_int(min=5, max=20)
    return max(5, minutes)


def build_rows(count: int) -> list[dict]:
    """Сгенерировать список тикетов (как словари)."""
    from faker import Faker

    faker = Faker("ru_RU")
    Faker.seed(SEED)

    end = datetime(2026, 6, 1, 0, 0, 0)
    start = end - timedelta(days=365)

    rows: list[dict] = []
    for i in range(1, count + 1):
        category = _weighted_choice(faker, _CATEGORY_WEIGHTS)
        priority = _weighted_choice(faker, _PRIORITY_WEIGHTS)
        channel = _weighted_choice(faker, _CHANNEL_WEIGHTS)
        team = _TEAM_BY_CATEGORY[category]
        created = _pick_created_at(faker, start, end)

        # Большинство тикетов закрыто; часть ещё в работе (тем чаще, чем свежее).
        days_old = (end - created).days
        is_closed = days_old > 3 or faker.pyfloat(
            min_value=0, max_value=1, right_digits=4
        ) < 0.85
        if is_closed:
            res_minutes = _resolution_minutes(faker, priority)
            closed = created + timedelta(minutes=res_minutes)
            roll = faker.pyfloat(min_value=0, max_value=1, right_digits=2)
            status = "закрыт" if roll < 0.8 else "решён"
        else:
            res_minutes = None
            closed = None
            status = faker.random_element(["создан", "в работе", "ожидает"])

        template = faker.random_element(_TEXT_TEMPLATES[category])
        text = template.format(sys=faker.random_element(_SYSTEMS))

        rows.append(
            {
                "ticket_number": f"INC-{i:06d}",
                "created_at": created.strftime("%Y-%m-%d %H:%M:%S"),
                "closed_at": closed.strftime("%Y-%m-%d %H:%M:%S") if closed else None,
                "category": category,
                "priority": priority,
                "status": status,
                "team": team,
                "channel": channel,
                "resolution_minutes": res_minutes,
                "text": text,
            }
        )
    return rows


_CREATE_TABLE = f"""
CREATE TABLE {tickets_db.TABLE_NAME} (
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

_INSERT = f"""
INSERT INTO {tickets_db.TABLE_NAME}
    (ticket_number, created_at, closed_at, category, priority, status, team,
     channel, resolution_minutes, text)
VALUES
    (:ticket_number, :created_at, :closed_at, :category, :priority, :status,
     :team, :channel, :resolution_minutes, :text)
"""


def write_db(rows: list[dict]) -> int:
    """Создать таблицу заново и залить строки. Возвращает число строк."""
    conn = tickets_db.connect_rw()
    try:
        conn.execute(f"DROP TABLE IF EXISTS {tickets_db.TABLE_NAME}")
        conn.execute(_CREATE_TABLE)
        conn.execute(
            f"CREATE INDEX idx_tickets_created ON {tickets_db.TABLE_NAME}(created_at)"
        )
        conn.execute(
            f"CREATE INDEX idx_tickets_category ON {tickets_db.TABLE_NAME}(category)"
        )
        conn.executemany(_INSERT, rows)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def run(count: int | None = None) -> int:
    """Полная генерация: построить строки и записать в SQLite."""
    count = count or config.TICKETS_COUNT
    print(f"Генерирую {count} тикетов (Faker, seed={SEED}) …")
    rows = build_rows(count)
    written = write_db(rows)
    print(f"Готово. Записано тикетов в {tickets_db.db_path()}: {written}")
    return written


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 — запускают вручную, печатаем причину
        print(f"Ошибка генерации тикетов: {exc}", file=sys.stderr)
        sys.exit(1)
