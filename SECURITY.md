# Security Policy

## Supported Versions

We provide security fixes for the latest minor release on PyPI.

| Version | Supported |
|---------|-----------|
| 0.3.x   | ✅        |
| < 0.3   | ❌        |

## Reporting a Vulnerability

If you discover a security issue in **fastforge-cli** or in the code we
generate, please **do not** open a public GitHub issue. Instead:

1. Email **security@vibhuvi.io** with a description of the vulnerability,
   reproduction steps, and the affected version.
2. We will acknowledge receipt within **3 business days** and provide an
   initial assessment within **7 business days**.
3. We will coordinate a disclosure timeline with you. Typical embargo is
   **30 days** for high-severity issues, extendable if a fix requires more
   time.
4. You will be credited in the release notes unless you request otherwise.

## Scope

In scope:
- The `fastforge-cli` package itself (the CLI and generators).
- The template code that fastforge generates into user projects.

Out of scope:
- Vulnerabilities in transitive dependencies (please report those upstream;
  we will pull the fix once published).
- Issues that require an attacker to already control the developer's
  machine running `fastforge`.

## Disclosure Hall of Fame

_(empty — be the first!)_
