"""Generate deployment manifests for a FastForge project.

Targets: compose, swarm, k8s, helm, marathon
Creates: deploy/<target>/ directory with manifests + README
Modifies: .fastforge.json
"""

import os

from fastforge.project_config import load_config, save_config

# ═══════════════════════════════════════════════════════════════════════════════
# Docker Compose (production)
# ═══════════════════════════════════════════════════════════════════════════════

COMPOSE_YML = """\
# Production Docker Compose
# Usage: docker compose -f deploy/compose/docker-compose.yml up -d

services:
  app:
    image: ${{REGISTRY:-ghcr.io}}/${{IMAGE_NAME:-{project_slug}}}:${{IMAGE_TAG:-latest}}
    build:
      context: ../..
      dockerfile: Dockerfile
    container_name: {project_slug}-app
    restart: unless-stopped
    ports:
      - "${{APP_PORT:-{port}}}:{port}"
    environment:
      APP_NAME: {project_slug}
      APP_ENV: production
      APP_PORT: "{port}"
      LOG_FORMAT: json
      LOG_LEVEL: INFO
      LOG_FILE_ENABLED: "true"
      LOG_FILE_PATH: /var/log/app/app.log
    env_file:
      - ../../.env.production
    volumes:
      - app-logs:/var/log/app
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
        reservations:
          cpus: "0.25"
          memory: 128M

volumes:
  app-logs:
    driver: local
"""

COMPOSE_README = """\
# Docker Compose Production Deployment

## Quick Start

```bash
# Build and start
docker compose -f deploy/compose/docker-compose.yml up -d

# View logs
docker compose -f deploy/compose/docker-compose.yml logs -f app

# Stop
docker compose -f deploy/compose/docker-compose.yml down
```

## Configuration

Edit `../../.env.production` for environment-specific settings.

## Scaling

```bash
docker compose -f deploy/compose/docker-compose.yml up -d --scale app=3
```
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Docker Swarm
# ═══════════════════════════════════════════════════════════════════════════════

SWARM_STACK_YML = """\
# Docker Swarm Stack Definition
# Deploy: docker stack deploy -c deploy/swarm/docker-stack.yml {project_slug}

version: "3.9"

services:
  app:
    image: ${{REGISTRY:-ghcr.io}}/{project_slug}:${{IMAGE_TAG:-latest}}
    environment:
      APP_NAME: {project_slug}
      APP_ENV: production
      APP_PORT: "{port}"
      APP_WORKERS: "2"
      LOG_FORMAT: json
      LOG_LEVEL: INFO
      LOG_FILE_ENABLED: "true"
      LOG_FILE_PATH: /var/log/app/app.log
    ports:
      - "{port}:{port}"
    volumes:
      - app-logs:/var/log/app
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 30s
        failure_action: rollback
        order: start-first
      rollback_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
        reservations:
          cpus: "0.25"
          memory: 128M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 10s
    networks:
      - app-network

volumes:
  app-logs:
    driver: local

networks:
  app-network:
    driver: overlay
    attachable: true
"""

SWARM_README = """\
# Docker Swarm Deployment

## Prerequisites

- Docker Swarm initialized (`docker swarm init`)
- Image pushed to a registry accessible from all nodes

## Deploy

```bash
# Initialize swarm (if not already)
docker swarm init --advertise-addr <MANAGER_IP>

# Build and push image
docker build -t your-registry/{project_slug}:latest .
docker push your-registry/{project_slug}:latest

# Deploy stack
docker stack deploy -c deploy/swarm/docker-stack.yml {project_slug}

# Verify
docker service ls
docker service ps {project_slug}_app
docker service logs -f {project_slug}_app
```

## Scale

```bash
docker service scale {project_slug}_app=5
```

## Rolling Update

```bash
docker service update \\
  --image your-registry/{project_slug}:v2.0.0 \\
  --update-parallelism 1 \\
  --update-delay 30s \\
  {project_slug}_app
```

## Rollback

```bash
docker service update --rollback {project_slug}_app
```
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Kubernetes
# ═══════════════════════════════════════════════════════════════════════════════

K8S_NAMESPACE = """\
apiVersion: v1
kind: Namespace
metadata:
  name: {namespace}
  labels:
    app: {project_slug}
"""

K8S_CONFIGMAP = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: {project_slug}-config
  namespace: {namespace}
  labels:
    app: {project_slug}
data:
  APP_NAME: {project_slug}
  APP_ENV: production
  APP_PORT: "{port}"
  APP_WORKERS: "2"
  LOG_FORMAT: json
  LOG_LEVEL: INFO
  LOG_FILE_ENABLED: "true"
  LOG_FILE_PATH: /var/log/app/app.log
"""

K8S_SECRET = """\
# In production, use External Secrets Operator or Vault Agent Injector
# instead of storing secrets directly in Kubernetes.
apiVersion: v1
kind: Secret
metadata:
  name: {project_slug}-secrets
  namespace: {namespace}
  labels:
    app: {project_slug}
type: Opaque
stringData:
  SECRET_KEY: "REPLACE_WITH_SECRET_KEY"
"""

K8S_DEPLOYMENT = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {project_slug}
  namespace: {namespace}
  labels:
    app: {project_slug}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {project_slug}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      labels:
        app: {project_slug}
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "{port}"
        prometheus.io/path: "/metrics"
    spec:
      securityContext:
        fsGroup: 1000
      terminationGracePeriodSeconds: 30
      containers:
        - name: app
          image: your-registry/{project_slug}:latest
          imagePullPolicy: Always
          ports:
            - name: http
              containerPort: {port}
              protocol: TCP
          envFrom:
            - configMapRef:
                name: {project_slug}-config
          volumeMounts:
            - name: app-logs
              mountPath: /var/log/app
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          startupProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 10
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
      volumes:
        - name: app-logs
          emptyDir:
            sizeLimit: 200Mi
"""

K8S_SERVICE = """\
apiVersion: v1
kind: Service
metadata:
  name: {project_slug}
  namespace: {namespace}
  labels:
    app: {project_slug}
spec:
  type: ClusterIP
  ports:
    - name: http
      port: {port}
      targetPort: http
      protocol: TCP
  selector:
    app: {project_slug}
"""

K8S_INGRESS = """\
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {project_slug}
  namespace: {namespace}
  labels:
    app: {project_slug}
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
spec:
  ingressClassName: nginx
  rules:
    - host: {project_slug}.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {project_slug}
                port:
                  name: http
"""

K8S_HPA = """\
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {project_slug}
  namespace: {namespace}
  labels:
    app: {project_slug}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {project_slug}
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
"""

K8S_README = """\
# Kubernetes Deployment

## Manifests

| File | Purpose |
|------|---------|
| `namespace.yaml` | Namespace isolation |
| `configmap.yaml` | Application configuration |
| `secret.yaml` | Secrets (use External Secrets in prod) |
| `deployment.yaml` | Application deployment |
| `service.yaml` | ClusterIP service |
| `ingress.yaml` | Ingress rule |
| `hpa.yaml` | Horizontal Pod Autoscaler |

## Deploy

```bash
# Build and push image
docker build -t your-registry/{project_slug}:latest .
docker push your-registry/{project_slug}:latest

# Apply all manifests
kubectl apply -f deploy/k8s/

# Verify
kubectl get pods -n {namespace} -w
kubectl logs -n {namespace} -l app={project_slug} -f

# Port-forward for testing
kubectl port-forward -n {namespace} svc/{project_slug} {port}:{port}
curl http://localhost:{port}/health
```

## Scale

```bash
# Manual
kubectl scale deployment -n {namespace} {project_slug} --replicas=5

# HPA handles auto-scaling (see hpa.yaml)
kubectl get hpa -n {namespace}
```

## Update Image

```bash
kubectl set image deployment/{project_slug} \\
  app=your-registry/{project_slug}:v2.0.0 \\
  -n {namespace}
```

## Rollback

```bash
kubectl rollout undo deployment/{project_slug} -n {namespace}
```
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Helm
# ═══════════════════════════════════════════════════════════════════════════════

HELM_CHART_YAML = """\
apiVersion: v2
name: {project_slug}
description: Helm chart for {project_slug}
type: application
version: 0.1.0
appVersion: "1.0.0"
"""

HELM_VALUES_YAML = """\
replicaCount: 2

image:
  repository: your-registry/{project_slug}
  pullPolicy: Always
  tag: "latest"

service:
  type: ClusterIP
  port: {port}

ingress:
  enabled: false
  className: nginx
  hosts:
    - host: {project_slug}.example.com
      paths:
        - path: /
          pathType: Prefix

resources:
  limits:
    cpu: 500m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

env:
  APP_NAME: {project_slug}
  APP_ENV: production
  APP_PORT: "{port}"
  LOG_FORMAT: json
  LOG_LEVEL: INFO

livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 15

readinessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
"""

HELM_DEPLOYMENT_TPL = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{project_slug}.fullname" . }}}}
  labels:
    {{{{- include "{project_slug}.labels" . | nindent 4 }}}}
spec:
  {{{{- if not .Values.autoscaling.enabled }}}}
  replicas: {{{{ .Values.replicaCount }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{project_slug}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      labels:
        {{{{- include "{project_slug}.selectorLabels" . | nindent 8 }}}}
    spec:
      containers:
        - name: {{{{ .Chart.Name }}}}
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          ports:
            - name: http
              containerPort: {port}
              protocol: TCP
          env:
            {{{{- range $key, $value := .Values.env }}}}
            - name: {{{{ $key }}}}
              value: {{{{ $value | quote }}}}
            {{{{- end }}}}
          livenessProbe:
            {{{{- toYaml .Values.livenessProbe | nindent 12 }}}}
          readinessProbe:
            {{{{- toYaml .Values.readinessProbe | nindent 12 }}}}
          resources:
            {{{{- toYaml .Values.resources | nindent 12 }}}}
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
"""

HELM_SERVICE_TPL = """\
apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{project_slug}.fullname" . }}}}
  labels:
    {{{{- include "{project_slug}.labels" . | nindent 4 }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
    - port: {{{{ .Values.service.port }}}}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{{{- include "{project_slug}.selectorLabels" . | nindent 4 }}}}
"""

HELM_HPA_TPL = """\
{{{{- if .Values.autoscaling.enabled }}}}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{{{ include "{project_slug}.fullname" . }}}}
  labels:
    {{{{- include "{project_slug}.labels" . | nindent 4 }}}}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{{{ include "{project_slug}.fullname" . }}}}
  minReplicas: {{{{ .Values.autoscaling.minReplicas }}}}
  maxReplicas: {{{{ .Values.autoscaling.maxReplicas }}}}
  metrics:
    {{{{- if .Values.autoscaling.targetCPUUtilizationPercentage }}}}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.autoscaling.targetCPUUtilizationPercentage }}}}
    {{{{- end }}}}
    {{{{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}}}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{{{ .Values.autoscaling.targetMemoryUtilizationPercentage }}}}
    {{{{- end }}}}
{{{{- end }}}}
"""

HELM_HELPERS_TPL = """\
{{{{/*
Expand the name of the chart.
*/}}}}
{{{{- define "{project_slug}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{/*
Create a default fully qualified app name.
*/}}}}
{{{{- define "{project_slug}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{/*
Common labels
*/}}}}
{{{{- define "{project_slug}.labels" -}}}}
helm.sh/chart: {{{{ include "{project_slug}.name" . }}}}-{{{{ .Chart.Version | replace "+" "_" }}}}
{{{{ include "{project_slug}.selectorLabels" . }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{/*
Selector labels
*/}}}}
{{{{- define "{project_slug}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{project_slug}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}
"""

HELM_INGRESS_TPL = """\
{{{{- if .Values.ingress.enabled -}}}}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{{{ include "{project_slug}.fullname" . }}}}
  labels:
    {{{{- include "{project_slug}.labels" . | nindent 4 }}}}
spec:
  ingressClassName: {{{{ .Values.ingress.className }}}}
  rules:
    {{{{- range .Values.ingress.hosts }}}}
    - host: {{{{ .host | quote }}}}
      http:
        paths:
          {{{{- range .paths }}}}
          - path: {{{{ .path }}}}
            pathType: {{{{ .pathType }}}}
            backend:
              service:
                name: {{{{ include "{project_slug}.fullname" $ }}}}
                port:
                  name: http
          {{{{- end }}}}
    {{{{- end }}}}
{{{{- end }}}}
"""

HELM_README = """\
# Helm Chart — {project_slug}

## Install

```bash
helm install {project_slug} deploy/helm/{project_slug} \\
  --namespace {namespace} --create-namespace

# With custom values
helm install {project_slug} deploy/helm/{project_slug} \\
  --namespace {namespace} --create-namespace \\
  -f deploy/helm/custom-values.yaml
```

## Upgrade

```bash
helm upgrade {project_slug} deploy/helm/{project_slug} \\
  --namespace {namespace} \\
  --set image.tag=v2.0.0
```

## Rollback

```bash
helm rollback {project_slug} -n {namespace}
```

## Uninstall

```bash
helm uninstall {project_slug} -n {namespace}
```

## Values

See `values.yaml` for all configurable parameters.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Marathon
# ═══════════════════════════════════════════════════════════════════════════════

MARATHON_APP_JSON = """\
{
  "id": "/{project_slug}",
  "instances": 2,
  "cpus": 0.5,
  "mem": 256,
  "container": {
    "type": "DOCKER",
    "docker": {
      "image": "your-registry/{project_slug}:latest",
      "network": "BRIDGE",
      "portMappings": [
        {
          "containerPort": {port},
          "hostPort": 0,
          "protocol": "tcp",
          "name": "http",
          "labels": {"VIP_0": "/{project_slug}:{port}"}
        }
      ],
      "forcePullImage": true
    },
    "volumes": [
      {
        "containerPath": "/var/log/app",
        "hostPath": "/opt/logs/{project_slug}",
        "mode": "RW"
      }
    ]
  },
  "env": {
    "APP_NAME": "{project_slug}",
    "APP_ENV": "production",
    "APP_PORT": "{port}",
    "APP_WORKERS": "2",
    "LOG_FORMAT": "json",
    "LOG_LEVEL": "INFO",
    "LOG_FILE_ENABLED": "true",
    "LOG_FILE_PATH": "/var/log/app/app.log"
  },
  "healthChecks": [
    {
      "protocol": "HTTP",
      "path": "/health",
      "portIndex": 0,
      "gracePeriodSeconds": 30,
      "intervalSeconds": 15,
      "timeoutSeconds": 5,
      "maxConsecutiveFailures": 3
    }
  ],
  "upgradeStrategy": {
    "minimumHealthCapacity": 0.5,
    "maximumOverCapacity": 0.25
  },
  "labels": {
    "HAPROXY_GROUP": "external",
    "HAPROXY_0_VHOST": "{project_slug}.example.com",
    "environment": "production"
  },
  "constraints": [["hostname", "UNIQUE"]]
}
"""

MARATHON_README = """\
# Marathon Deployment

## Prerequisites

- Marathon cluster running (DC/OS or standalone)
- Docker containerizer enabled on Mesos agents
- Image pushed to an accessible registry

## Deploy

```bash
# Deploy via Marathon REST API
curl -X POST http://marathon.example.com:8080/v2/apps \\
  -H "Content-Type: application/json" \\
  -d @deploy/marathon/marathon-app.json

# Or via DC/OS CLI
dcos marathon app add deploy/marathon/marathon-app.json
```

## Scale

```bash
curl -X PUT http://marathon.example.com:8080/v2/apps/{project_slug} \\
  -H "Content-Type: application/json" \\
  -d '{{"instances": 5}}'
```

## Verify

```bash
curl http://marathon.example.com:8080/v2/apps/{project_slug} | jq .
```
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Generator functions
# ═══════════════════════════════════════════════════════════════════════════════


def _write(path: str, content: str, created: list[str], rel_prefix: str) -> None:
    """Write a file if it doesn't already exist."""
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(content)
        created.append(f"{rel_prefix}/{os.path.basename(path)}")


def deploy_compose(project_dir: str) -> dict:
    """Generate production docker-compose.yml."""
    config = load_config(project_dir)
    if "compose" in config.get("deploy", []):
        return {"status": "already_configured", "created": [], "modified": []}

    slug = config.get("project_slug", "app")
    port = config.get("port", "8000")
    created: list[str] = []

    out = os.path.join(project_dir, "deploy", "compose")
    os.makedirs(out, exist_ok=True)

    _write(os.path.join(out, "docker-compose.yml"),
           COMPOSE_YML.format(project_slug=slug, port=port),
           created, "deploy/compose")
    _write(os.path.join(out, "README.md"),
           COMPOSE_README,
           created, "deploy/compose")

    config.setdefault("deploy", []).append("compose")
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}


def deploy_swarm(project_dir: str) -> dict:
    """Generate Docker Swarm stack definition."""
    config = load_config(project_dir)
    if "swarm" in config.get("deploy", []):
        return {"status": "already_configured", "created": [], "modified": []}

    slug = config.get("project_slug", "app")
    port = config.get("port", "8000")
    created: list[str] = []

    out = os.path.join(project_dir, "deploy", "swarm")
    os.makedirs(out, exist_ok=True)

    _write(os.path.join(out, "docker-stack.yml"),
           SWARM_STACK_YML.format(project_slug=slug, port=port),
           created, "deploy/swarm")
    _write(os.path.join(out, "README.md"),
           SWARM_README.format(project_slug=slug),
           created, "deploy/swarm")

    config.setdefault("deploy", []).append("swarm")
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}


def deploy_k8s(project_dir: str) -> dict:
    """Generate Kubernetes manifests."""
    config = load_config(project_dir)
    if "k8s" in config.get("deploy", []):
        return {"status": "already_configured", "created": [], "modified": []}

    slug = config.get("project_slug", "app")
    port = config.get("port", "8000")
    namespace = config.get("project_slug", "app").replace("_", "-")
    fmt = {"project_slug": slug, "port": port, "namespace": namespace}
    created: list[str] = []

    out = os.path.join(project_dir, "deploy", "k8s")
    os.makedirs(out, exist_ok=True)

    manifests = [
        ("namespace.yaml", K8S_NAMESPACE),
        ("configmap.yaml", K8S_CONFIGMAP),
        ("secret.yaml", K8S_SECRET),
        ("deployment.yaml", K8S_DEPLOYMENT),
        ("service.yaml", K8S_SERVICE),
        ("ingress.yaml", K8S_INGRESS),
        ("hpa.yaml", K8S_HPA),
    ]

    for filename, template in manifests:
        _write(os.path.join(out, filename),
               template.format(**fmt),
               created, "deploy/k8s")

    _write(os.path.join(out, "README.md"),
           K8S_README.format(**fmt),
           created, "deploy/k8s")

    config.setdefault("deploy", []).append("k8s")
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}


def deploy_helm(project_dir: str) -> dict:
    """Generate Helm chart."""
    config = load_config(project_dir)
    if "helm" in config.get("deploy", []):
        return {"status": "already_configured", "created": [], "modified": []}

    slug = config.get("project_slug", "app")
    port = config.get("port", "8000")
    namespace = slug.replace("_", "-")
    fmt = {"project_slug": slug, "port": port, "namespace": namespace}
    created: list[str] = []

    chart_dir = os.path.join(project_dir, "deploy", "helm", slug)
    templates_dir = os.path.join(chart_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)

    _write(os.path.join(chart_dir, "Chart.yaml"),
           HELM_CHART_YAML.format(**fmt),
           created, f"deploy/helm/{slug}")
    _write(os.path.join(chart_dir, "values.yaml"),
           HELM_VALUES_YAML.format(**fmt),
           created, f"deploy/helm/{slug}")

    helm_templates = [
        ("deployment.yaml", HELM_DEPLOYMENT_TPL),
        ("service.yaml", HELM_SERVICE_TPL),
        ("hpa.yaml", HELM_HPA_TPL),
        ("ingress.yaml", HELM_INGRESS_TPL),
        ("_helpers.tpl", HELM_HELPERS_TPL),
    ]

    for filename, template in helm_templates:
        _write(os.path.join(templates_dir, filename),
               template.format(**fmt),
               created, f"deploy/helm/{slug}/templates")

    _write(os.path.join(project_dir, "deploy", "helm", "README.md"),
           HELM_README.format(**fmt),
           created, "deploy/helm")

    config.setdefault("deploy", []).append("helm")
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}


def deploy_marathon(project_dir: str) -> dict:
    """Generate Marathon app definition."""
    config = load_config(project_dir)
    if "marathon" in config.get("deploy", []):
        return {"status": "already_configured", "created": [], "modified": []}

    slug = config.get("project_slug", "app")
    port = int(config.get("port", "8000"))
    created: list[str] = []

    out = os.path.join(project_dir, "deploy", "marathon")
    os.makedirs(out, exist_ok=True)

    _write(os.path.join(out, "marathon-app.json"),
           MARATHON_APP_JSON.replace("{project_slug}", slug).replace("{port}", str(port)),
           created, "deploy/marathon")

    _write(os.path.join(out, "README.md"),
           MARATHON_README.format(project_slug=slug),
           created, "deploy/marathon")

    config.setdefault("deploy", []).append("marathon")
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}
