"""Generate CI/CD pipelines for multiple providers.

Providers: github, gitlab, bitbucket, jenkins
Creates: CI config files in the project root
Modifies: .fastforge.json
"""

import os

from fastforge.project_config import load_config, save_config

# ═══════════════════════════════════════════════════════════════════════════════
# GitHub Actions
# ═══════════════════════════════════════════════════════════════════════════════

GITHUB_CI = """\
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "{python_version}"
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{{{ github.repository }}}}

jobs:
  # ─── Code Quality & Tests ──────────────────────────
  test:
    name: Test & Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}
          cache: pip

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint with ruff
        run: |
          ruff check app/ tests/
          ruff format --check app/ tests/

      - name: Run tests
        run: pytest --cov=app --cov-report=xml --cov-report=term-missing

      - name: Upload coverage
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage.xml

  # ─── Security: SAST ────────────────────────────────
  sast:
    name: SAST - Bandit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}

      - name: Install bandit
        run: pip install "bandit[toml]"

      - name: Run Bandit SAST scan
        run: bandit -c pyproject.toml -r app/ -f json -o bandit-report.json || true

      - name: Upload Bandit report
        uses: actions/upload-artifact@v4
        with:
          name: bandit-report
          path: bandit-report.json

  # ─── Security: Secret Scanning ─────────────────────
  secret-scan:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Gitleaks scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}

  # ─── Security: Dependency Audit ────────────────────
  dependency-audit:
    name: Dependency Audit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: pip-audit
        run: pip-audit --format json --output pip-audit-report.json || true

      - name: Upload audit report
        uses: actions/upload-artifact@v4
        with:
          name: pip-audit-report
          path: pip-audit-report.json

  # ─── Build Docker Image ────────────────────────────
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    needs: [test, sast, secret-scan, dependency-audit]
    if: github.event_name != 'pull_request'
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{{{ env.REGISTRY }}}}
          username: ${{{{ github.actor }}}}
          password: ${{{{ secrets.GITHUB_TOKEN }}}}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}
          tags: |
            type=sha
            type=ref,event=branch
            type=semver,pattern={{{{version}}}}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{{{ steps.meta.outputs.tags }}}}
          labels: ${{{{ steps.meta.outputs.labels }}}}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # ─── Container Image Scan (Trivy) ─────────────────
  trivy-scan:
    name: Trivy Container Scan
    runs-on: ubuntu-latest
    needs: [build]
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:sha-${{{{ github.sha }}}}
          format: sarif
          output: trivy-results.sarif
          severity: CRITICAL,HIGH
          exit-code: 0

      - name: Upload Trivy SARIF to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: trivy-results.sarif

  # ─── IaC Security Scan ────────────────────────────
  iac-scan:
    name: IaC Security Scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Trivy IaC scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: config
          scan-ref: .
          format: table
          severity: CRITICAL,HIGH,MEDIUM
          exit-code: 0

  # ─── Generate SBOM ────────────────────────────────
  sbom:
    name: Generate SBOM
    runs-on: ubuntu-latest
    needs: [build]
    steps:
      - uses: actions/checkout@v4

      - name: Generate SBOM with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{{{ env.REGISTRY }}}}/${{{{ env.IMAGE_NAME }}}}:sha-${{{{ github.sha }}}}
          format: cyclonedx
          output: sbom.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json
"""

# ═══════════════════════════════════════════════════════════════════════════════
# GitLab CI
# ═══════════════════════════════════════════════════════════════════════════════

GITLAB_CI = """\
stages:
  - test
  - security
  - build
  - scan

variables:
  PYTHON_VERSION: "{python_version}"
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"

cache:
  paths:
    - .cache/pip/

# ─── Test & Lint ──────────────────────────────────────
test:
  stage: test
  image: python:${{PYTHON_VERSION}}-slim
  script:
    - pip install -e ".[dev]"
    - ruff check app/ tests/
    - ruff format --check app/ tests/
    - pytest --cov=app --cov-report=xml --cov-report=term-missing --junitxml=report.xml
  artifacts:
    reports:
      junit: report.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

# ─── SAST ─────────────────────────────────────────────
sast:
  stage: security
  image: python:${{PYTHON_VERSION}}-slim
  script:
    - pip install "bandit[toml]"
    - bandit -c pyproject.toml -r app/ -f json -o bandit-report.json || true
  artifacts:
    paths:
      - bandit-report.json

# ─── Secret Scanning ─────────────────────────────────
secret-scan:
  stage: security
  image:
    name: zricethezav/gitleaks:latest
    entrypoint: [""]
  script:
    - gitleaks detect --source . --report-format json --report-path gitleaks-report.json || true
  artifacts:
    paths:
      - gitleaks-report.json

# ─── Dependency Audit ────────────────────────────────
dependency-audit:
  stage: security
  image: python:${{PYTHON_VERSION}}-slim
  script:
    - pip install -e ".[dev]" pip-audit
    - pip-audit --format json --output pip-audit-report.json || true
  artifacts:
    paths:
      - pip-audit-report.json

# ─── Build Docker Image ─────────────────────────────
build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA -t $CI_REGISTRY_IMAGE:latest .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
    - docker push $CI_REGISTRY_IMAGE:latest
  only:
    - main
    - develop

# ─── Trivy Container Scan ───────────────────────────
trivy-scan:
  stage: scan
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  script:
    - trivy image --severity CRITICAL,HIGH --exit-code 0 --format table $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  only:
    - main
    - develop
  needs:
    - build
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Bitbucket Pipelines
# ═══════════════════════════════════════════════════════════════════════════════

BITBUCKET_PIPELINES = """\
image: python:{python_version}-slim

definitions:
  caches:
    pip: ~/.cache/pip
  steps:
    - step: &test
        name: Test & Lint
        caches:
          - pip
        script:
          - pip install -e ".[dev]"
          - ruff check app/ tests/
          - ruff format --check app/ tests/
          - pytest --cov=app --cov-report=xml --junitxml=test-results.xml
        artifacts:
          - coverage.xml
          - test-results.xml

    - step: &security
        name: Security Scan
        caches:
          - pip
        script:
          - pip install "bandit[toml]" pip-audit
          - bandit -c pyproject.toml -r app/ || true
          - pip install -e ".[dev]"
          - pip-audit || true

    - step: &docker-build
        name: Build & Push Docker Image
        services:
          - docker
        caches:
          - docker
        script:
          - docker build -t $BITBUCKET_REPO_SLUG:$BITBUCKET_COMMIT .
          - pipe: atlassian/docker-push:1.0.0
            variables:
              IMAGE_NAME: $BITBUCKET_REPO_SLUG
              IMAGE_TAG: $BITBUCKET_COMMIT

pipelines:
  default:
    - step: *test
    - step: *security

  branches:
    main:
      - step: *test
      - step: *security
      - step: *docker-build

    develop:
      - step: *test
      - step: *security
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Jenkinsfile
# ═══════════════════════════════════════════════════════════════════════════════

JENKINSFILE = """\
pipeline {{
    agent any

    environment {{
        PYTHON_VERSION = '{python_version}'
        REGISTRY = credentials('docker-registry')
        IMAGE_NAME = '{project_slug}'
    }}

    stages {{
        stage('Setup') {{
            steps {{
                sh 'python -m venv .venv'
                sh '.venv/bin/pip install -e ".[dev]"'
            }}
        }}

        stage('Lint') {{
            steps {{
                sh '.venv/bin/ruff check app/ tests/'
                sh '.venv/bin/ruff format --check app/ tests/'
            }}
        }}

        stage('Test') {{
            steps {{
                sh '.venv/bin/pytest --cov=app --cov-report=xml --junitxml=test-results.xml'
            }}
            post {{
                always {{
                    junit 'test-results.xml'
                    cobertura coberturaReportFile: 'coverage.xml'
                }}
            }}
        }}

        stage('Security') {{
            parallel {{
                stage('SAST') {{
                    steps {{
                        sh '.venv/bin/pip install "bandit[toml]"'
                        sh '.venv/bin/bandit -c pyproject.toml -r app/ || true'
                    }}
                }}
                stage('Dependency Audit') {{
                    steps {{
                        sh '.venv/bin/pip install pip-audit'
                        sh '.venv/bin/pip-audit || true'
                    }}
                }}
            }}
        }}

        stage('Build Docker Image') {{
            when {{
                anyOf {{
                    branch 'main'
                    branch 'develop'
                }}
            }}
            steps {{
                sh "docker build -t ${{IMAGE_NAME}}:${{BUILD_NUMBER}} -t ${{IMAGE_NAME}}:latest ."
            }}
        }}

        stage('Trivy Scan') {{
            when {{
                anyOf {{
                    branch 'main'
                    branch 'develop'
                }}
            }}
            steps {{
                sh "trivy image --severity CRITICAL,HIGH --exit-code 0 ${{IMAGE_NAME}}:${{BUILD_NUMBER}}"
            }}
        }}
    }}

    post {{
        always {{
            cleanWs()
        }}
    }}
}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Generator functions
# ═══════════════════════════════════════════════════════════════════════════════

PROVIDERS = {
    "github": {
        "template": GITHUB_CI,
        "path": ".github/workflows/ci.yml",
        "needs_dir": True,
    },
    "gitlab": {
        "template": GITLAB_CI,
        "path": ".gitlab-ci.yml",
        "needs_dir": False,
    },
    "bitbucket": {
        "template": BITBUCKET_PIPELINES,
        "path": "bitbucket-pipelines.yml",
        "needs_dir": False,
    },
    "jenkins": {
        "template": JENKINSFILE,
        "path": "Jenkinsfile",
        "needs_dir": False,
    },
}


def add_ci(project_dir: str, provider: str) -> dict:
    """Generate CI/CD pipeline for the specified provider."""
    config = load_config(project_dir)

    ci_list = config.get("ci", [])
    if provider in ci_list:
        return {"status": "already_configured", "created": [], "modified": []}

    if provider not in PROVIDERS:
        return {"status": "error", "message": f"Unknown provider: {provider}"}

    info = PROVIDERS[provider]
    python_version = config.get("python_version", "3.13")
    slug = config.get("project_slug", "app")

    created: list[str] = []

    file_path = os.path.join(project_dir, info["path"])

    if info["needs_dir"]:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if not os.path.exists(file_path):
        content = info["template"].format(
            python_version=python_version,
            project_slug=slug,
        )
        with open(file_path, "w") as f:
            f.write(content)
        created.append(info["path"])

    ci_list.append(provider)
    config["ci"] = ci_list
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}


def ci_local(project_dir: str) -> int:
    """Run the CI/CD pipeline locally — lint, test, security scan, docker build.

    Returns exit code (0 = all passed).
    """
    import shutil
    import subprocess
    import sys

    config = load_config(project_dir)
    slug = config.get("project_slug", "app")

    steps: list[tuple[str, list[str]]] = [
        ("Lint (ruff check)", ["ruff", "check", "app/", "tests/"]),
        ("Format check (ruff)", ["ruff", "format", "--check", "app/", "tests/"]),
        ("Tests (pytest)", ["pytest", "tests/", "-x", "-q", "--tb=short"]),
    ]

    # Optional security steps
    if shutil.which("bandit"):
        steps.append(("SAST (bandit)", ["bandit", "-r", "app/", "-q"]))
    if shutil.which("pip-audit"):
        steps.append(("Dependency audit", ["pip-audit"]))
    if os.path.isfile(os.path.join(project_dir, "Dockerfile")) and shutil.which("docker"):
        steps.append(("Docker build", ["docker", "build", "-t", f"{slug}:local", "."]))
        if shutil.which("trivy"):
            steps.append(("Trivy image scan", ["trivy", "image", "--severity", "CRITICAL,HIGH", f"{slug}:local"]))

    passed = 0
    failed = 0

    for name, cmd in steps:
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}\n")

        result = subprocess.run(cmd, cwd=project_dir)

        if result.returncode == 0:
            print(f"\n  ✔ {name} — passed")
            passed += 1
        else:
            print(f"\n  ✘ {name} — FAILED")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return 1 if failed > 0 else 0
