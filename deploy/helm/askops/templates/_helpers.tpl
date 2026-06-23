{{/*
Общие хелперы чарта AskOps.
*/}}

{{/* Базовое имя релиза (усечённое до 63 символов — ограничение k8s-имён). */}}
{{- define "askops.fullname" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Общие метки на всех ресурсах. */}}
{{- define "askops.labels" -}}
app.kubernetes.io/part-of: askops
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/*
Полный путь образа для сервиса.
Принимает dict {svc, root}. Если у сервиса задан imageOverride — берём его как есть,
иначе собираем {registry}/{owner}/{svc.image}:{tag}.
*/}}
{{- define "askops.image" -}}
{{- $svc := .svc -}}
{{- $img := .root.Values.image -}}
{{- if $svc.imageOverride -}}
{{- $svc.imageOverride -}}
{{- else -}}
{{- printf "%s/%s/%s:%s" $img.registry $img.owner $svc.image $img.tag -}}
{{- end -}}
{{- end -}}
