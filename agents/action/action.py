"""Логика action-агента: создать заявку (тикет) и опубликовать событие.

Это «агент, который делает»: на запрос-действие он записывает новый тикет в ту же
базу (статус «создан») и публикует событие в Kafka-топик. Реальных корпоративных
систем нет — это осознанная симуляция интеграции, честно описанная в README.

Надёжность: запись в БД и публикация события разделены. Если очередь недоступна,
тикет всё равно создан, а в ответе честно отражается, ушло ли событие.
"""

from __future__ import annotations

from datetime import datetime

from agents.action import kafka_producer
from agents.analyst import tickets_db

# Ключевые слова для определения категории заявки (по убыванию приоритета совпадения).
_CATEGORY_KEYWORDS = [
    ("учётки", ["учётк", "учетк", "пароль", "аккаунт", "логин", "разблок"]),
    ("железо", ["ноутбук", "монитор", "принтер", "мышь", "клавиатур", "док-стан", "техник"]),
    ("ПО", ["устан", "софт", "программ", "приложени", "лицензи", "по "]),
    ("сеть", ["сеть", "интернет", "wi-fi", "wifi", "роутер"]),
    ("доступы", ["доступ", "права", "разрешени", "vpn", "jira", "confluence", "папк", "бд", "база данных"]),
]

# Ключевые слова повышенного приоритета.
_HIGH_PRIORITY_KEYWORDS = ["срочно", "критичн", "боев", "прод", "production", "не работает"]


def _detect_category(text: str) -> str:
    """Грубо определить категорию заявки по ключевым словам (fallback — доступы)."""
    low = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(kw in low for kw in keywords):
            return category
    return "доступы"


def _detect_priority(text: str) -> str:
    low = text.lower()
    if any(kw in low for kw in _HIGH_PRIORITY_KEYWORDS):
        return "высокий"
    return "средний"


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_ticket(request_text: str) -> dict:
    """Создать заявку по тексту запроса: записать тикет и опубликовать событие.

    Returns:
        {"answer", "ticket_number", "category", "priority", "published", "found"}
    """
    request_text = (request_text or "").strip()
    if not request_text:
        return {
            "answer": "Пустой запрос — нечего создавать.",
            "ticket_number": "",
            "category": "",
            "priority": "",
            "published": False,
            "found": False,
        }

    category = _detect_category(request_text)
    priority = _detect_priority(request_text)
    created_at = _now_str()

    # 1. Записать тикет в БД (статус «создан»).
    conn = tickets_db.connect_rw()
    try:
        tickets_db.ensure_table(conn)
        ticket_number = tickets_db.next_ticket_number(conn, prefix="REQ")
    finally:
        conn.close()

    ticket = {
        "ticket_number": ticket_number,
        "created_at": created_at,
        "closed_at": None,
        "category": category,
        "priority": priority,
        "status": "создан",
        "team": tickets_db.team_for_category(category),
        "channel": "агент",
        "resolution_minutes": None,
        "text": request_text,
    }
    tickets_db.insert_ticket(ticket)

    # 2. Опубликовать событие в очередь (не критично для создания тикета).
    event = {
        "event": "ticket_created",
        "ticket_number": ticket_number,
        "category": category,
        "priority": priority,
        "status": "создан",
        "created_at": created_at,
        "text": request_text,
    }
    published = kafka_producer.publish_event(event)

    queue_note = (
        "событие отправлено в очередь — нотификатор сообщит ответственным"
        if published
        else "событие в очередь отправить не удалось (очередь недоступна), "
        "но заявка уже зарегистрирована"
    )
    answer = (
        f"Заявка создана: {ticket_number} (категория «{category}», "
        f"приоритет «{priority}», исполнитель — {ticket['team']}). {queue_note.capitalize()}."
    )

    return {
        "answer": answer,
        "ticket_number": ticket_number,
        "category": category,
        "priority": priority,
        "published": published,
        "found": True,
    }
