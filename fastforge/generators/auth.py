"""Add JWT authentication scaffolding to a FastForge project.

This is an OPTIONAL plugin. JWT is one of several valid auth strategies;
many production deployments terminate auth at an upstream API gateway and
do not need this scaffold. Add it only when the service itself must verify
tokens or issue them.

What gets created:
* ``app/auth/__init__.py``
* ``app/auth/jwt.py``        — encode / decode, ``get_current_user`` dependency.
* ``app/auth/routes.py``     — ``POST /auth/login``, ``GET /auth/me``.
* ``app/auth/users.py``      — in-memory user store (REPLACE for production).

What gets modified:
* ``pyproject.toml``         — adds ``pyjwt[crypto]`` and ``passlib[bcrypt]``.
* ``.env.staging``           — adds ``JWT_SECRET``, ``JWT_ALGORITHM``, ``JWT_EXPIRE_MIN``.
* ``app/config.py``          — adds matching settings fields.
* ``app/main.py``            — includes ``auth_router``.
* ``.fastforge.json``        — sets ``auth = "jwt"``.

Idempotent: running twice is a no-op.

SECURITY NOTES (read before going to production):
* The generated user store is in-memory and unsalted-by-default — replace it
  with a real persistence + bcrypt hashing flow before exposing publicly.
* ``JWT_SECRET`` is a placeholder. Generate a real one
  (``openssl rand -hex 32``) and store it in your secrets backend, never in
  the repo.
* Refresh tokens are intentionally NOT implemented in the scaffold — add
  them when your token lifetime exceeds a few minutes.
"""

from __future__ import annotations

import os
import re

from fastforge.project_config import load_config, save_config

JWT_PY = '''\
"""JWT token issuance and verification.

Replace ``SECRET`` lookup with your secrets backend in production.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """Issue a short-lived JWT for ``subject`` (typically a user id)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_min)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises 401 on any failure."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: extract and validate the current user from the bearer token."""
    claims = decode_token(token)
    return {"username": claims["sub"], "claims": claims}
'''

USERS_PY = '''\
"""In-memory user store — REPLACE for production.

This is a scaffold. Wire your real persistence + bcrypt verification here.
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo seed user. Replace with a real lookup.
_USERS: dict[str, dict] = {
    "demo": {
        "username": "demo",
        # password = "demo" — change immediately or remove.
        "hashed_password": pwd_context.hash("demo"),
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_user(username: str) -> dict | None:
    return _USERS.get(username)
'''

ROUTES_PY = '''\
"""Authentication routes — `/auth/login`, `/auth/me`."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth.jwt import create_access_token, get_current_user
from app.auth.users import get_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    user = get_user(form_data.username)
    if user is None or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(subject=user["username"]))


@router.get("/me")
async def read_me(current_user: dict = Depends(get_current_user)) -> dict:
    """Echo back the authenticated user — useful for token-validation smoke tests."""
    return current_user
'''

DEPS = [
    '"pyjwt[crypto]>=2.9.0"',
    '"passlib[bcrypt]>=1.7.4"',
    '"python-multipart>=0.0.20"',  # required by OAuth2PasswordRequestForm
]

ENV_BLOCK = """
# JWT auth — replace JWT_SECRET with `openssl rand -hex 32`
JWT_SECRET=change-me-in-production-use-a-real-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MIN=15
"""

CONFIG_BLOCK = """\
    # JWT auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_min: int = 15

"""


def add_auth_jwt(project_dir: str) -> dict:
    """Add JWT authentication scaffolding. Returns summary of changes."""
    config = load_config(project_dir)

    if config.get("auth") == "jwt":
        return {"status": "already_configured", "created": [], "modified": []}
    if config.get("auth") not in (None, "none"):
        raise ValueError(f"Project already uses auth: {config['auth']}")

    created: list[str] = []
    modified: list[str] = []

    # 1. app/auth/ package
    auth_dir = os.path.join(project_dir, "app", "auth")
    os.makedirs(auth_dir, exist_ok=True)

    files = {
        "__init__.py": '"""Authentication package."""\n',
        "jwt.py": JWT_PY,
        "users.py": USERS_PY,
        "routes.py": ROUTES_PY,
    }
    for name, content in files.items():
        path = os.path.join(auth_dir, name)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(content)
            created.append(f"app/auth/{name}")

    # 2. config.py — append jwt settings before the closing brace of Settings
    config_path = os.path.join(project_dir, "app", "config.py")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            content = f.read()
        if "jwt_secret" not in content:
            for anchor in ["    model_config", "    @property"]:
                if anchor in content:
                    content = content.replace(anchor, CONFIG_BLOCK + anchor, 1)
                    break
            else:
                content = content.rstrip() + "\n" + CONFIG_BLOCK
            with open(config_path, "w") as f:
                f.write(content)
            modified.append("app/config.py")

    # 3. .env.staging
    env_path = os.path.join(project_dir, ".env.staging")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            env_content = f.read()
        if "JWT_SECRET" not in env_content:
            with open(env_path, "a") as f:
                f.write(ENV_BLOCK)
            modified.append(".env.staging")

    # 4. main.py — wire auth_router
    main_path = os.path.join(project_dir, "app", "main.py")
    if os.path.isfile(main_path):
        with open(main_path) as f:
            main_content = f.read()
        import_line = "from app.auth.routes import router as auth_router"
        include_line = "    app.include_router(auth_router)"
        changed = False
        if import_line not in main_content:
            # Insert after last "from app.api.routes" import
            lines = main_content.splitlines()
            idx = max(
                (i for i, line in enumerate(lines) if line.startswith("from app.api.routes")),
                default=-1,
            )
            if idx >= 0:
                lines.insert(idx + 1, import_line)
                main_content = "\n".join(lines) + "\n"
                changed = True
        if include_line not in main_content:
            # Insert after last include_router(... )
            pattern = re.compile(r"^( {4})app\.include_router\(.*\)$", re.MULTILINE)
            matches = list(pattern.finditer(main_content))
            if matches:
                end = matches[-1].end()
                main_content = main_content[:end] + "\n" + include_line + main_content[end:]
                changed = True
        if changed:
            with open(main_path, "w") as f:
                f.write(main_content)
            modified.append("app/main.py")

    # 5. pyproject.toml — add deps
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        new_deps = [d for d in DEPS if d.strip('"').split("[")[0] not in pyproject_content.lower()]
        if new_deps:
            match = re.search(
                r"(dependencies\s*=\s*\[)(.*?)(^\])",
                pyproject_content,
                re.DOTALL | re.MULTILINE,
            )
            if match:
                existing = match.group(2).rstrip()
                if existing and not existing.rstrip().endswith(","):
                    existing = existing.rstrip() + ","
                new_section = existing + "\n" + "\n".join(f"    {d}," for d in new_deps) + "\n"
                pyproject_content = (
                    pyproject_content[: match.start(2)]
                    + new_section
                    + pyproject_content[match.start(3) :]
                )
                with open(pyproject_path, "w") as f:
                    f.write(pyproject_content)
                modified.append("pyproject.toml")

    # 6. .fastforge.json
    config["auth"] = "jwt"
    save_config(config, project_dir)
    modified.append(".fastforge.json")

    return {"status": "added", "created": created, "modified": modified}
