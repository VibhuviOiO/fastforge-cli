"""Security tooling for FastForge projects.

Commands:
  setup   — Generate .gitleaks.toml + .trivy.yaml configs
  scan    — Run Trivy container image scan
  sbom    — Generate CycloneDX SBOM
  license — Check license compliance (block GPL/AGPL)
  audit   — Run pip-audit for known vulnerabilities
"""

import os
import shutil
import subprocess
import sys

from fastforge.project_config import load_config, save_config

# ═══════════════════════════════════════════════════════════════════════════════
# Config templates (moved from devsecops.py)
# ═══════════════════════════════════════════════════════════════════════════════

GITLEAKS_TOML = """\
# Gitleaks configuration
title = "Gitleaks Config"

[extend]
useDefault = true

# Custom rules for project-specific patterns
[[rules]]
id = "vault-token"
description = "HashiCorp Vault Token"
regex = '''hvs\\\\.[a-zA-Z0-9]{24,}'''
tags = ["vault", "secret"]

# Allow list for false positives
[allowlist]
description = "Allow list for known false positives"
paths = [
  '''.secrets.baseline''',
  '''\\\\.env\\\\.staging''',
  '''\\\\.env\\\\.production''',
  '''infra/.*''',
]
regexTarget = "line"
regexes = [
  '''dev-only-token''',
  '''REPLACE_WITH_''',
  '''change-me''',
]
"""

TRIVY_YAML = """\
severity:
  - CRITICAL
  - HIGH
  - MEDIUM

security-checks:
  - vuln
  - config
  - secret

ignore-unfixed: true

# Skip dev dependencies
skip-dirs:
  - tests
  - .venv
  - node_modules

# Output
format: table
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Generator functions
# ═══════════════════════════════════════════════════════════════════════════════


def secure_setup(project_dir: str) -> dict:
    """Generate security config files (.gitleaks.toml, .trivy.yaml)."""
    config = load_config(project_dir)

    if config.get("secure") == "enabled":
        return {"status": "already_configured", "created": [], "modified": []}

    created: list[str] = []

    gitleaks_path = os.path.join(project_dir, ".gitleaks.toml")
    if not os.path.exists(gitleaks_path):
        with open(gitleaks_path, "w") as f:
            f.write(GITLEAKS_TOML)
        created.append(".gitleaks.toml")

    trivy_path = os.path.join(project_dir, ".trivy.yaml")
    if not os.path.exists(trivy_path):
        with open(trivy_path, "w") as f:
            f.write(TRIVY_YAML)
        created.append(".trivy.yaml")

    config["secure"] = "enabled"
    save_config(config, project_dir)

    return {"status": "added", "created": created, "modified": [".fastforge.json"]}


def secure_scan(project_dir: str) -> int:
    """Run Trivy container image scan on the project's Docker image."""
    config = load_config(project_dir)
    slug = config.get("project_slug", "app")

    if not shutil.which("trivy"):
        print("✘ trivy not found. Install: https://aquasecurity.github.io/trivy/")
        return 1

    image = f"{slug}:latest"

    # Build image first if possible
    dockerfile = os.path.join(project_dir, "Dockerfile")
    if os.path.isfile(dockerfile):
        print(f"Building image {image}...")
        result = subprocess.run(
            ["docker", "build", "-t", image, "."],
            cwd=project_dir,
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"✘ Docker build failed:\n{result.stderr.decode()}")
            return 1

    print(f"\nScanning {image} for vulnerabilities...\n")
    result = subprocess.run(
        ["trivy", "image", "--severity", "CRITICAL,HIGH", image],
        cwd=project_dir,
    )
    return result.returncode


def secure_sbom(project_dir: str) -> int:
    """Generate CycloneDX SBOM from project dependencies."""
    if not shutil.which("cyclonedx-py"):
        # Try installing
        print("Installing cyclonedx-bom...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "cyclonedx-bom"],
            capture_output=True,
        )

    if not shutil.which("cyclonedx-py"):
        print("✘ cyclonedx-py not found. Install: pip install cyclonedx-bom")
        return 1

    output = os.path.join(project_dir, "sbom.json")
    print("Generating CycloneDX SBOM...\n")
    result = subprocess.run(
        ["cyclonedx-py", "environment", "--output", output, "--format", "json"],
        cwd=project_dir,
    )

    if result.returncode == 0:
        print(f"\n✔ SBOM written to sbom.json")
    return result.returncode


def secure_license(project_dir: str) -> int:
    """Check license compliance — block restrictive licenses."""
    if not shutil.which("pip-licenses"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pip-licenses"],
            capture_output=True,
        )

    if not shutil.which("pip-licenses"):
        print("✘ pip-licenses not found. Install: pip install pip-licenses")
        return 1

    print("Checking license compliance...\n")

    # First show all licenses
    subprocess.run(
        ["pip-licenses", "--format=table", "--with-authors"],
        cwd=project_dir,
    )

    # Then check for restricted licenses
    print("\nChecking for restrictive licenses (GPL, AGPL, LGPL)...\n")
    result = subprocess.run(
        [
            "pip-licenses",
            "--fail-on=GNU General Public License v3 (GPLv3);GNU Affero General Public License v3 (AGPLv3);GNU Lesser General Public License v3 (LGPLv3)",
            "--format=table",
        ],
        cwd=project_dir,
    )

    if result.returncode == 0:
        print("✔ No restrictive licenses found.")
    else:
        print("✘ Restrictive licenses detected! Review dependencies.")

    return result.returncode


def secure_audit(project_dir: str) -> int:
    """Run pip-audit to check for known vulnerabilities in dependencies."""
    if not shutil.which("pip-audit"):
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pip-audit"],
            capture_output=True,
        )

    if not shutil.which("pip-audit"):
        print("✘ pip-audit not found. Install: pip install pip-audit")
        return 1

    print("Running dependency vulnerability audit...\n")
    result = subprocess.run(
        ["pip-audit", "--format", "columns"],
        cwd=project_dir,
    )

    if result.returncode == 0:
        print("\n✔ No known vulnerabilities found.")
    return result.returncode


def secure_owasp(project_dir: str, target_url: str | None = None) -> int:
    """Run OWASP ZAP baseline scan against the running API.

    Requires Docker to be available (uses the official ZAP Docker image).
    """
    config = load_config(project_dir)
    port = config.get("port", 8000)

    if target_url is None:
        target_url = f"http://host.docker.internal:{port}"

    if not shutil.which("docker"):
        print("✘ Docker not found. OWASP ZAP scan requires Docker.")
        return 1

    print(f"Running OWASP ZAP baseline scan against {target_url}...\n")
    print("This may take a few minutes on first run (pulling ZAP image).\n")

    report_dir = os.path.join(project_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)

    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "--add-host=host.docker.internal:host-gateway",
            "-v", f"{report_dir}:/zap/wrk:rw",
            "ghcr.io/zaproxy/zaproxy:stable",
            "zap-baseline.py",
            "-t", target_url,
            "-r", "owasp-report.html",
            "-J", "owasp-report.json",
            "-I",  # Don't fail on warnings, only on failures
        ],
        cwd=project_dir,
    )

    if result.returncode <= 1:
        print(f"\n✔ OWASP ZAP report written to reports/owasp-report.html")
    else:
        print(f"\n✘ OWASP ZAP found issues. See reports/owasp-report.html")

    return result.returncode
