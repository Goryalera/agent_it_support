"""Подготовка аналитик-агента к старту внутри контейнера.

Если базы тикетов ещё нет (или задан REGEN=true) — генерирует синтетическую
выгрузку. БД лежит в именованном volume, поэтому повторная генерация при
перезапусках не нужна.

Запуск: python -m agents.analyst.startup
"""

from __future__ import annotations

import os
import sys

from agents.analyst import generate_tickets, tickets_db


def ensure_db() -> None:
    """Сгенерировать базу тикетов, если файла ещё нет."""
    path = tickets_db.db_path()
    regen = os.environ.get("REGEN", "").strip().lower() in {"1", "true", "yes", "on"}
    if path.exists() and not regen:
        print(f"База тикетов уже существует ({path}) — пропускаю генерацию.")
        return
    print(f"Генерирую базу тикетов в {path} …")
    generate_tickets.run()


def main() -> None:
    ensure_db()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 — стартовый шаг, печатаем и падаем
        print(f"Ошибка подготовки аналитик-агента: {exc}", file=sys.stderr)
        sys.exit(1)
