"""Streamlit-страница для демо AskOps.

Простое поле ввода: вопрос → ответ от оркестратора (через REST /ask).

Запуск:
    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import os

import requests
import streamlit as st

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")
# Нотификатор опционален (Слой 2, профиль "action"). Если задан — покажем ленту
# уведомлений о созданных тикетах; если недоступен — просто скрываем блок.
NOTIFIER_URL = os.environ.get("NOTIFIER_URL", "")

st.set_page_config(page_title="AskOps — помощник ИТ-поддержки", page_icon="💬")

st.title("💬 AskOps")
st.caption("Помощник первой линии ИТ-поддержки. Спросите по-человечески.")

with st.sidebar:
    st.subheader("Примеры вопросов")
    st.markdown(
        "**Знание (RAG):**\n"
        "- Не подключается VPN с домашнего ноутбука\n"
        "- Как получить доступ к Jira?\n"
        "- Какой VPN-клиент ставить на Mac?\n"
        "\n**Статистика (аналитик):**\n"
        "- Сколько инцидентов по доступам за последний месяц?\n"
        "- Среднее время решения по приоритетам\n"
        "\n**Действие (action, профиль «action»):**\n"
        "- Создай заявку на доступ к боевой БД"
    )
    st.caption(f"Оркестратор: {ORCHESTRATOR_URL}")

    if NOTIFIER_URL:
        with st.expander("🔔 Уведомления о тикетах", expanded=False):
            try:
                r = requests.get(f"{NOTIFIER_URL}/notifications", timeout=5)
                r.raise_for_status()
                notes = r.json().get("notifications", [])
                if notes:
                    for line in reversed(notes[-10:]):
                        st.text(line)
                else:
                    st.caption("Пока нет уведомлений.")
            except Exception:  # noqa: BLE001 — нотификатор не поднят: просто молчим
                st.caption("Нотификатор недоступен (поднимите профиль «action»).")

question = st.text_input("Ваш вопрос", placeholder="Например: не подключается VPN")

if st.button("Спросить", type="primary") and question.strip():
    with st.spinner("Ищу ответ в базе знаний…"):
        try:
            resp = requests.post(
                f"{ORCHESTRATOR_URL}/ask",
                json={"question": question},
                timeout=120,
            )
            resp.raise_for_status()
            answer = resp.json().get("answer", "(пустой ответ)")
            st.markdown("### Ответ")
            st.write(answer)
        except Exception as exc:  # noqa: BLE001 — показываем ошибку пользователю
            st.error(f"Не удалось получить ответ: {exc}")
