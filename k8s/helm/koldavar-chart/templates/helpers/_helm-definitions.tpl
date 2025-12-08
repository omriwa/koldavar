{{/*
Return the chart name
*/}}
{{- define "koldavar.name" -}}
{{ .Chart.Name }}
{{- end }}

{{/*
Return the full chart version string
*/}}
{{- define "koldavar.chart" -}}
{{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Standard Helm labels
*/}}
{{- define "koldavar.labels" -}}
app.kubernetes.io/name: {{ include "koldavar.name" . }}
helm.sh/chart: {{ include "koldavar.chart" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Helm release ownership annotations
*/}}
{{- define "koldavar.annotations" -}}
meta.helm.sh/release-name: {{ .Release.Name }}
meta.helm.sh/release-namespace: {{ .Release.Namespace }}
{{- end }}
