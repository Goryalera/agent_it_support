# Деплой через GitOps (k3d + Helm + ArgoCD) — Слой 3

Этот слой демонстрирует навык Kubernetes/Helm/ArgoCD в режиме «поднял → задеплоил
→ снял скриншоты → удалил». Кластер не крутится постоянно; артефакты (Helm-чарт,
манифест ArgoCD Application, этот документ, скриншоты) остаются в репозитории и
доказывают навык даже после удаления кластера.

```
git push ──► CI (GitHub Actions) ──► образы в GHCR
                                          │
   values.yaml (тег образа) ──► git ──► ArgoCD ──sync──► k3d-кластер (Helm-чарт)
```

## Что в репозитории

- `deploy/helm/askops/` — Helm-чарт: Deployment + Service на каждый сервис
  (`templates/deployment.yaml`, `service.yaml` — generic-шаблоны, разворачиваемые
  по `values.yaml`), значения с тегами образов и числом реплик.
- `deploy/helm/askops/values-real.yaml` — оверрайд для реального LLM (через секрет).
- `deploy/argocd/application.yaml` — ArgoCD Application, смотрящий на папку чарта в git.
- CI (`.github/workflows/ci.yml`) — на пуш в `main` собирает образы и пушит в
  **GHCR** (`ghcr.io/<owner>/askops-*`).

> Перед стартом замени в `values.yaml` (`image.owner`) и в `application.yaml`
> (`repoURL`, параметр `image.owner`) плейсхолдер `owner` на свой GitHub-логин
> (в нижнем регистре).

## 0. Предпосылки

Установлены `docker`, `k3d`, `kubectl`, `helm`. Образы запушены в GHCR (любой
пуш в `main` это делает) и пакеты сделаны публичными — иначе нужен imagePullSecret.

## 1. Локальный кластер k3d

```bash
k3d cluster create askops --agents 1
kubectl cluster-info
```

k3d поднимает k3s внутри Docker за полминуты.

## 2. Установка чарта напрямую (быстрая проверка без ArgoCD)

```bash
helm upgrade --install askops deploy/helm/askops \
  --namespace askops --create-namespace \
  --set image.owner=<твой-github-owner>

kubectl -n askops get pods           # дождаться Running/Ready
kubectl -n askops port-forward svc/orchestrator 8000:8000
curl -s http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question": "как настроить VPN"}'
```

В кластере по умолчанию `LLM_MODE=mock` — секреты не нужны, поды поднимаются
сразу. Для реального LLM см. `values-real.yaml`.

> Ресурсы: пик ~3–4 ГБ только на время демо. Если на 8 ГБ тяжело — поставь
> `services.opensearch.enabled=false` (деплой только агентов; RAG в этом режиме
> отвечает «не знаю», но цель слоя — показать k8s, а не весь стек).

## 3. GitOps через ArgoCD

```bash
# Установить ArgoCD в кластер
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Создать Application, смотрящий на папку чарта в твоём git-репозитории
kubectl apply -n argocd -f deploy/argocd/application.yaml

# Открыть UI ArgoCD
kubectl -n argocd port-forward svc/argocd-server 8080:443
# логин admin, пароль:
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

ArgoCD синхронизирует кластер с тем, что лежит в git. **Демонстрация GitOps:**
поменяй тег образа в `deploy/helm/askops/values.yaml` (`image.tag`), закоммить и
запушь — ArgoCD сам подтянет изменение и пересоздаст поды (`automated.selfHeal`,
`prune`).

## 4. Скриншоты для резюме

Сложить в `docs/screenshots/`:
- UI ArgoCD с зелёным (Healthy/Synced) приложением `askops`;
- вывод `kubectl -n askops get pods` со всеми Running;
- (опц.) ответ `curl` от оркестратора из кластера.

## 5. Уборка

```bash
k3d cluster delete askops
```

Артефакты (чарт, манифест Application, скриншоты) остаются в репозитории — их и
показываешь. Навык доказан даже после удаления кластера.
