# Streamlit-страница для демо (необязательный сервис).
# Контекст сборки — корень репозитория (см. docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY ui/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY ui ./ui

EXPOSE 8501

CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
