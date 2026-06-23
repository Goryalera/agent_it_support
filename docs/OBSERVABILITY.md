# Наблюдаемость: Prometheus + Grafana — Слой 4

Агенты отдают метрики на `/metrics` (через `prometheus-fastapi-instrumentator`).
Prometheus их собирает, Grafana показывает дашборд. Поднимается профилем, чтобы не
висеть постоянно.

## Что собирается

- **HTTP-метрики** (на каждом агенте): латентность запросов
  (`http_request_duration_seconds`), число запросов, ошибки по статусам — в разрезе
  агента (`job`) и эндпоинта.
- **Кастомные метрики LLM** (`shared/metrics.py`): `askops_llm_requests_total`
  (вызовы LLM по провайдеру) и `askops_llm_tokens_total` (расход токенов:
  prompt/completion). Считаются в обёртке `shared/llm.py` вокруг каждого вызова.

Код деградирует мягко: без `prometheus-fastapi-instrumentator`/`prometheus_client`
агенты работают как раньше, только без `/metrics` (важно для лёгкого CI).

## Запуск

```bash
# Поднять стек вместе с мониторингом
docker compose --profile observability up --build

# (опционально вместе со Слоем 2)
docker compose --profile action --profile observability up --build
```

- Prometheus: <http://localhost:9090> (Targets → агенты должны быть `UP`).
- Grafana: <http://localhost:3000> (admin / admin) → дашборд **AskOps — агенты**
  (папка AskOps, провижинится автоматически).

Подай несколько запросов оркестратору (`/ask`), чтобы на дашборде появились данные:
RPS по агентам, p95-латентность, ошибки 5xx, вызовы LLM и расход токенов.

## Артефакты

- `deploy/observability/prometheus/prometheus.yml` — scrape-конфиг (цели — агенты).
- `deploy/observability/grafana/provisioning/` — datasource (Prometheus) и провайдер
  дашбордов (автонастройка).
- `deploy/observability/grafana/dashboards/askops.json` — сам дашборд.
