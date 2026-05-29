"""FastForge AI App generator — scaffolds AI infrastructure (gateway, embeddings, vector store, app skeleton).

Usage:
    fastforge add ai-app semantic_search
    fastforge add ai-app rag
    fastforge add ai-app agent

This generator emits the full AI infrastructure layer:
- AI config (Pydantic Settings from AI_* env vars)
- AI gateway client (LiteLLM / BiFrost)
- Embedding provider (OpenAI / Gemini / Cohere / HuggingFace / Bedrock / local)
- Vector store (Vertex AI / ChromaDB / OpenSearch / pgvector / Qdrant)
- App-kind orchestrator skeleton (semantic_search / rag / agent)
- FastAPI lifespan integration
- Dependencies for injection
- Example route
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from fastforge.generator_protocol import BaseGenerator
from fastforge.project_config import load_config, save_config

# ── Pinned dependency versions ───────────────────────────────────────────────
# Single source of truth for the dep injector. Bump versions here.
_BASE_DEPS: tuple[str, ...] = (
    "httpx==0.27.0",
    "pydantic-settings==2.4.0",
    "opentelemetry-api==1.25.0",
    "opentelemetry-sdk==1.25.0",
)
_VECTOR_STORE_DEPS: dict[str, str] = {
    "chromadb": "chromadb==0.5.0",
    "opensearch": "opensearch-py==2.6.0",
    "pgvector": "pgvector==0.3.2",
    "qdrant": "qdrant-client==1.9.0",
    "vertex_ai": "google-cloud-aiplatform==1.56.0",
}
_EMBEDDING_DEPS: dict[str, str] = {
    "huggingface": "sentence-transformers==3.0.0",
    "local": "sentence-transformers==3.0.0",
    "bedrock": "boto3==1.34.0",
}
_AI_DEPS_MARKER = "# ai-infrastructure-deps"


class AIAppGenerator(BaseGenerator):
    """Generator for AI application infrastructure."""

    name = "ai-app"
    version = "1.0.0"
    description = "AI infrastructure: gateway, embeddings, vector store, and app orchestrator"
    capability_key = "ai_app_kind"
    delegatable = True

    # Template source directory (relative to this package)
    _TEMPLATE_DIR = Path(__file__).parent.parent / "ai_templates"

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        """Generate AI infrastructure directly into the project.

        Args in args dict:
            ai_app_kind: semantic_search | rag | agent
            gateway_provider: litellm | bifrost
            embedding_provider: openai | gemini | cohere | huggingface | bedrock | local
            vector_store_provider: vertex_ai | chromadb | opensearch | pgvector | qdrant
        """
        ai_app_kind = args.get("ai_app_kind", "semantic_search")
        gateway = args.get("gateway_provider", "litellm")
        embedding = args.get("embedding_provider", "openai")
        vector_store = args.get("vector_store_provider", "chromadb")

        app_dir = project_dir / "app"
        ai_dir = app_dir / "ai"

        created: list[str] = []
        modified: list[str] = []

        # Check if already configured
        config_path = project_dir / ".fastforge.json"
        if config_path.exists():
            config = load_config(str(project_dir))
            if config.get("ai_app_kind") and config["ai_app_kind"] != "none":
                # Already configured — idempotent, no-op
                return {"status": "already_configured", "created": [], "modified": []}
        else:
            config = {}

        # Create directory structure
        dirs_to_create = [
            ai_dir,
            ai_dir / "gateway",
            ai_dir / "embeddings",
            ai_dir / "vector_store",
            ai_dir / "app_kinds",
        ]
        for d in dirs_to_create:
            d.mkdir(parents=True, exist_ok=True)

        # Copy all template files
        created.extend(self._copy_templates(project_dir, ai_dir))

        # Create the example route
        routes_dir = app_dir / "api" / "routes"
        routes_dir.mkdir(parents=True, exist_ok=True)
        route_file = routes_dir / "ai.py"
        if not route_file.exists():
            route_file.write_text(self._generate_route(ai_app_kind))
            created.append(str(route_file.relative_to(project_dir)))

        # Wire AI route + lifespan into app/main.py when present
        if self._wire_app_main(project_dir):
            modified.append("app/main.py")

        # Add an AI operations runbook for ML-focused deployments
        if self._augment_readme(project_dir, embedding, vector_store):
            modified.append("README.md")

        # Update .fastforge.json
        config["ai_app_kind"] = ai_app_kind
        config["llm_gateway"] = gateway
        config["embeddings_provider"] = embedding
        config["vector_store"] = vector_store
        save_config(config, str(project_dir))
        modified.append(".fastforge.json")

        # Create/update .env.example
        env_file = project_dir / ".env.example"
        env_additions = self._get_env_vars(gateway, embedding, vector_store)
        if env_file.exists():
            existing = env_file.read_text()
            if "AI_GATEWAY_PROVIDER" not in existing:
                with open(env_file, "a") as f:
                    f.write("\n# ── AI Infrastructure ─────────────────────────\n")
                    f.write(env_additions)
                modified.append(".env.example")
        else:
            env_file.write_text(
                "# ── AI Infrastructure ─────────────────────────\n" + env_additions
            )
            created.append(".env.example")

        # Update pyproject.toml with AI dependencies
        pyproject_path = project_dir / "pyproject.toml"
        if pyproject_path.exists():
            self._update_dependencies(pyproject_path, gateway, embedding, vector_store)
            modified.append("pyproject.toml")

        return {"status": "ok", "created": created, "modified": modified}

    def emit_delegated(self, project_dir: Path, lib: str, args: dict[str, Any]) -> dict[str, Any]:
        """For app kind — thin wire-up that imports AI infra from the platform lib."""
        # For now, falls back to inline. Will be refined when Batch B lands.
        return self.emit_inline(project_dir, args)

    def emit_into_lib(self, lib_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        """Generate AI infrastructure into a shared library."""
        # For now, same as inline but targets lib_dir
        return self.emit_inline(lib_dir, args)

    def upgrade(self, project_dir: Path, from_version: str) -> dict[str, Any]:
        """Upgrade AI infrastructure from a previous version."""
        # v1.0.0 is the first version; no deltas to apply
        return {"status": "no_change", "changes": []}

    def validate(self, project_dir: Path) -> list[str]:
        """Validate AI infrastructure is consistent."""
        warnings: list[str] = []
        ai_dir = project_dir / "app" / "ai"

        if not ai_dir.exists():
            warnings.append("app/ai/ directory is missing")
            return warnings

        expected_files = [
            "config.py",
            "lifespan.py",
            "dependencies.py",
            "gateway/__init__.py",
            "gateway/registry.py",
            "embeddings/__init__.py",
            "embeddings/registry.py",
            "vector_store/__init__.py",
            "vector_store/registry.py",
        ]

        for f in expected_files:
            if not (ai_dir / f).exists():
                warnings.append(f"app/ai/{f} is missing")

        return warnings

    def _copy_templates(self, project_dir: Path, ai_dir: Path) -> list[str]:
        """Copy template files into the project's app/ai/ directory."""
        created = []
        template_dir = self._TEMPLATE_DIR

        for root, dirs, files in os.walk(template_dir):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            rel_root = Path(root).relative_to(template_dir)
            target_root = ai_dir / rel_root

            for filename in files:
                if filename.endswith((".pyc", ".pyo")):
                    continue

                source = Path(root) / filename
                target = target_root / filename

                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    created.append(str(target.relative_to(project_dir)))

        return created

    def _generate_route(self, ai_app_kind: str) -> str:
        """Generate an example FastAPI route for the chosen AI app kind."""
        if ai_app_kind == "semantic_search":
            return '''"""AI search routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ai.app_kinds.semantic_search import SearchOrchestrator, SearchQuery
from app.ai.dependencies import get_embedding_provider, get_gateway, get_vector_store
from app.ai.embeddings import EmbeddingProvider
from app.ai.gateway import GatewayClient
from app.ai.vector_store import VectorStoreProvider

router = APIRouter(prefix="/ai/search", tags=["ai-search"])


class SearchRequest(BaseModel):
    """Search request body."""

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=10, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    namespace: str | None = None
    rewrite_query: bool = False
    include_fields: list[str] = Field(default_factory=list)


class SearchResultItemResponse(BaseModel):
    """A single search result."""

    id: str
    score: float
    content: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class SearchResponseModel(BaseModel):
    """Search response."""

    results: list[SearchResultItemResponse]
    query: str
    total_count: int
    rewritten_query: str | None = None


@router.post("/", response_model=SearchResponseModel)
async def search(
    request: SearchRequest,
    gateway: GatewayClient = Depends(get_gateway),
    embedding: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
) -> SearchResponseModel:
    """Perform a semantic search."""
    orchestrator = SearchOrchestrator(
        gateway=gateway,
        embedding_provider=embedding,
        vector_store=vector_store,
    )

    query = SearchQuery(
        text=request.query,
        top_k=request.top_k,
        filters=request.filters,
        namespace=request.namespace,
        rewrite_query=request.rewrite_query,
        include_fields=request.include_fields,
    )

    result = await orchestrator.search(query)

    return SearchResponseModel(
        results=[
            SearchResultItemResponse(
                id=r.id, score=r.score, content=r.content, fields=r.fields
            )
            for r in result.results
        ],
        query=result.query,
        total_count=result.total_count,
        rewritten_query=result.rewritten_query,
    )
'''
        elif ai_app_kind == "rag":
            return '''"""AI RAG routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ai.app_kinds.rag import RAGOrchestrator, RAGQuery
from app.ai.dependencies import get_embedding_provider, get_gateway, get_vector_store
from app.ai.embeddings import EmbeddingProvider
from app.ai.gateway import GatewayClient
from app.ai.vector_store import VectorStoreProvider

router = APIRouter(prefix="/ai/rag", tags=["ai-rag"])


class RAGRequest(BaseModel):
    """RAG query request."""

    question: str = Field(..., min_length=1, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict)
    namespace: str | None = None
    model: str = "gpt-4o"
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    include_sources: bool = True


class RAGSourceResponse(BaseModel):
    """A source used in the RAG answer."""

    id: str
    content: str
    score: float


class RAGResponseModel(BaseModel):
    """RAG response."""

    answer: str
    sources: list[RAGSourceResponse]
    model: str
    query: str


@router.post("/", response_model=RAGResponseModel)
async def query_rag(
    request: RAGRequest,
    gateway: GatewayClient = Depends(get_gateway),
    embedding: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStoreProvider = Depends(get_vector_store),
) -> RAGResponseModel:
    """Ask a question using RAG."""
    orchestrator = RAGOrchestrator(
        gateway=gateway,
        embedding_provider=embedding,
        vector_store=vector_store,
    )

    rag_query = RAGQuery(
        question=request.question,
        top_k=request.top_k,
        filters=request.filters,
        namespace=request.namespace,
        model=request.model,
        temperature=request.temperature,
        include_sources=request.include_sources,
    )

    result = await orchestrator.query(rag_query)

    return RAGResponseModel(
        answer=result.answer,
        sources=[
            RAGSourceResponse(id=s.id, content=s.content, score=s.score)
            for s in result.sources
        ],
        model=result.model,
        query=result.query,
    )
'''
        else:  # agent
            return '''"""AI Agent routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.ai.app_kinds.agent import AgentOrchestrator, AgentQuery, AgentMessage
from app.ai.dependencies import get_gateway
from app.ai.gateway import GatewayClient

router = APIRouter(prefix="/ai/agent", tags=["ai-agent"])


class MessageInput(BaseModel):
    """A message in the conversation history."""

    role: str
    content: str


class AgentRequest(BaseModel):
    """Agent request."""

    message: str = Field(..., min_length=1, max_length=10000)
    conversation_history: list[MessageInput] = Field(default_factory=list)
    model: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_iterations: int = Field(default=10, ge=1, le=50)


class AgentResponseModel(BaseModel):
    """Agent response."""

    answer: str
    tool_calls_made: list[dict[str, Any]]
    iterations: int
    model: str


@router.post("/", response_model=AgentResponseModel)
async def run_agent(
    request: AgentRequest,
    gateway: GatewayClient = Depends(get_gateway),
) -> AgentResponseModel:
    """Run the AI agent."""
    orchestrator = AgentOrchestrator(gateway=gateway, max_iterations=request.max_iterations)

    # Register your tools here:
    # orchestrator.add_tool(Tool(name="search", description="...", parameters={...}, handler=...))

    query = AgentQuery(
        message=request.message,
        conversation_history=[
            AgentMessage(role=m.role, content=m.content)
            for m in request.conversation_history
        ],
        model=request.model,
        temperature=request.temperature,
        max_iterations=request.max_iterations,
    )

    result = await orchestrator.run(query)

    return AgentResponseModel(
        answer=result.answer,
        tool_calls_made=result.tool_calls_made,
        iterations=result.iterations,
        model=result.model,
    )
'''

    def _get_env_vars(self, gateway: str, embedding: str, vector_store: str) -> str:
        """Generate .env.example entries for the selected providers."""
        lines = [
            f"AI_GATEWAY_PROVIDER={gateway}",
            "AI_GATEWAY_BASE_URL=http://localhost:4000",
            "AI_GATEWAY_API_KEY=",
            f"AI_EMBEDDING_PROVIDER={embedding}",
            "AI_EMBEDDING_MODEL=text-embedding-3-small",
            "AI_EMBEDDING_DIMENSIONS=1536",
            f"AI_VECTOR_STORE_PROVIDER={vector_store}",
            "AI_VECTOR_STORE_COLLECTION=default",
            "",
        ]

        # Provider-specific vars
        if embedding == "openai":
            lines.append("AI_OPENAI_API_KEY=")
        elif embedding == "gemini":
            lines.extend(["AI_GEMINI_API_KEY=", "AI_GEMINI_MODEL=models/embedding-001"])
        elif embedding == "cohere":
            lines.append("AI_COHERE_API_KEY=")
        elif embedding == "bedrock":
            lines.extend(
                ["AI_BEDROCK_REGION=us-east-1", "AI_BEDROCK_MODEL_ID=amazon.titan-embed-text-v1"]
            )

        if vector_store == "vertex_ai":
            lines.extend(
                [
                    "",
                    "AI_VERTEX_AI_PROJECT=",
                    "AI_VERTEX_AI_LOCATION=us-central1",
                    "AI_VERTEX_AI_INDEX_ENDPOINT=",
                    "AI_VERTEX_AI_DEPLOYED_INDEX_ID=",
                ]
            )
        elif vector_store == "chromadb":
            lines.extend(["", "AI_CHROMADB_HOST=localhost", "AI_CHROMADB_PORT=8000"])
        elif vector_store == "opensearch":
            lines.extend(
                [
                    "",
                    "AI_OPENSEARCH_HOST=localhost",
                    "AI_OPENSEARCH_PORT=9200",
                    "AI_OPENSEARCH_INDEX=vectors",
                    "AI_OPENSEARCH_USERNAME=",
                    "AI_OPENSEARCH_PASSWORD=",
                ]
            )
        elif vector_store == "pgvector":
            lines.extend(
                ["", "AI_PGVECTOR_DSN=postgresql+asyncpg://user:pass@localhost:5432/vectors"]
            )
        elif vector_store == "qdrant":
            lines.extend(
                ["", "AI_QDRANT_HOST=localhost", "AI_QDRANT_PORT=6333", "AI_QDRANT_API_KEY="]
            )

        return "\n".join(lines) + "\n"

    def _wire_app_main(self, project_dir: Path) -> bool:
        """Patch app/main.py to include AI route and AI lifespan.

        Returns True when the file was modified.
        """
        main_path = project_dir / "app" / "main.py"
        if not main_path.exists():
            return False

        original = main_path.read_text()
        content = original

        if "from app.api.routes.ai import router as ai_router" not in content:
            if "from app.api.routes.health import router as health_router" in content:
                content = content.replace(
                    "from app.api.routes.health import router as health_router",
                    "from app.api.routes.health import router as health_router\n"
                    "from app.api.routes.ai import router as ai_router",
                    1,
                )

        if "from app.ai.lifespan import ai_lifespan" not in content:
            if "from app.config import settings" in content:
                content = content.replace(
                    "from app.config import settings",
                    "from app.ai.lifespan import ai_lifespan\nfrom app.config import settings",
                    1,
                )

        if "def merged_lifespan(" not in content:
            merged = (
                "\n\n@asynccontextmanager\n"
                "async def merged_lifespan(app: FastAPI):\n"
                '    """Compose base app lifespan with AI provider lifespan."""\n'
                "    async with lifespan(app):\n"
                "        try:\n"
                "            async with ai_lifespan(app):\n"
                "                yield\n"
                "        except Exception as e:  # noqa: BLE001\n"
                '            logger.warning("ai_lifespan_disabled", error=str(e))\n'
                "            yield\n"
            )
            if "\n\ndef create_app() -> FastAPI:\n" in content:
                content = content.replace(
                    "\n\ndef create_app() -> FastAPI:\n",
                    merged + "\n\ndef create_app() -> FastAPI:\n",
                    1,
                )

        if "lifespan=merged_lifespan" not in content:
            if "lifespan=lifespan," in content:
                content = content.replace("lifespan=lifespan,", "lifespan=merged_lifespan,", 1)
            elif "lifespan=lifespan)" in content:
                content = content.replace("lifespan=lifespan)", "lifespan=merged_lifespan)", 1)

        if "app.include_router(ai_router)" not in content:
            content = content.replace(
                "\n    return app\n",
                "\n    app.include_router(ai_router)\n\n    return app\n",
                1,
            )

        if content == original:
            return False
        main_path.write_text(content)
        return True

    def _augment_readme(self, project_dir: Path, embedding: str, vector_store: str) -> bool:
        """Append an AI deployment runbook to the generated README.

        Returns True when the README was modified.
        """
        readme_path = project_dir / "README.md"
        if not readme_path.exists():
            return False

        content = readme_path.read_text()
        marker = "## AI Runbook (Generated)"
        if marker in content:
            return False

        env_lines = [
            "AI_GATEWAY_PROVIDER=litellm",
            f"AI_EMBEDDING_PROVIDER={embedding}",
            f"AI_VECTOR_STORE_PROVIDER={vector_store}",
        ]
        if embedding == "openai":
            env_lines.append("AI_OPENAI_API_KEY=<required>")
        elif embedding == "gemini":
            env_lines.extend(
                [
                    "AI_GEMINI_API_KEY=<required>",
                    "AI_GEMINI_MODEL=models/embedding-001",
                ]
            )
        elif embedding == "cohere":
            env_lines.append("AI_COHERE_API_KEY=<required>")
        elif embedding == "bedrock":
            env_lines.extend(
                [
                    "AI_BEDROCK_REGION=us-east-1",
                    "AI_BEDROCK_MODEL_ID=amazon.titan-embed-text-v1",
                ]
            )

        if vector_store == "vertex_ai":
            env_lines.extend(
                [
                    "AI_VERTEX_AI_PROJECT=<required>",
                    "AI_VERTEX_AI_LOCATION=us-central1",
                    "AI_VERTEX_AI_INDEX_ENDPOINT=<required>",
                    "AI_VERTEX_AI_DEPLOYED_INDEX_ID=<required>",
                ]
            )

        env_block = "\n".join(env_lines)
        runbook = f"""

## AI Runbook (Generated)

This project includes generated AI infrastructure under `app/ai/` and routes under `app/api/routes/ai.py`.

### 1. Minimum AI Environment

Set these in `.env.staging` (or your runtime secret store):

```env
{env_block}
```

### 2. Local Smoke Validation

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ --tb=short
python -m compileall app
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then verify:
- `GET /health` returns 200
- `POST /ai/search/` returns non-404 (route is wired)

### 3. Cloud Run Guidance for ML Search

- Prefer async provider clients and keep a single initialized instance per provider via lifespan.
- Start Cloud Run concurrency at `250` for async I/O-heavy search orchestration; tune with p95 latency + error rate.
- For Vertex AI Vector Search latency, use private networking:
  - Serverless VPC Access connector
  - Private egress route for Google APIs / internal path
  - Keep region alignment between Cloud Run and Vertex resources

### 4. Production Readiness Checklist

- Enable OpenTelemetry exporter and trace context propagation.
- Keep provider selection config-driven (`AI_*` vars), not hardcoded.
- Validate client-key routing and query normalization in service-layer tests.
"""

        anchor = "\n## Extend Your Project\n"
        if anchor in content:
            content = content.replace(anchor, runbook + anchor, 1)
        else:
            content += runbook

        readme_path.write_text(content)
        return True

    def _update_dependencies(
        self, pyproject_path: Path, gateway: str, embedding: str, vector_store: str
    ) -> None:
        """Add AI dependencies to pyproject.toml.

        Uses a bracket-matching parser to find the dependencies array and
        injects missing entries before the closing ]. Falls back to a sidecar
        AI_DEPENDENCIES.txt file if the structure cannot be parsed, so the
        user always sees what to add.
        """
        content = pyproject_path.read_text()

        deps = list(_BASE_DEPS)
        if vector_store in _VECTOR_STORE_DEPS:
            deps.append(_VECTOR_STORE_DEPS[vector_store])
        if embedding in _EMBEDDING_DEPS:
            deps.append(_EMBEDDING_DEPS[embedding])

        # Deduplicate while preserving order
        seen: set[str] = set()
        deps = [d for d in deps if not (d in seen or seen.add(d))]

        missing = [d for d in deps if d.split("==")[0] not in content]
        if not missing:
            return
        if _AI_DEPS_MARKER in content:
            return  # already injected on a previous run

        new_content = self._inject_deps(content, missing)
        if new_content is None:
            self._write_dep_fallback(pyproject_path, missing)
            return
        pyproject_path.write_text(new_content)

    @staticmethod
    def _inject_deps(content: str, missing: list[str]) -> str | None:
        """Locate `dependencies = [` and inject entries before the matching ].

        Returns the new content, or None if the array could not be parsed.
        """
        import re

        match = re.search(r"^\s*dependencies\s*=\s*\[", content, re.MULTILINE)
        if not match:
            return None
        bracket_start = match.end() - 1  # position of '['

        # Walk from bracket_start, counting nesting, skipping strings
        depth = 0
        i = bracket_start
        n = len(content)
        while i < n:
            c = content[i]
            if c == '"' or c == "'":
                quote = c
                i += 1
                while i < n and content[i] != quote:
                    if content[i] == "\\" and i + 1 < n:
                        i += 2
                    else:
                        i += 1
                i += 1
                continue
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth != 0:
            return None

        close_idx = i
        addition = f"    {_AI_DEPS_MARKER}\n" + "\n".join(f'    "{d}",' for d in missing) + "\n"
        return content[:close_idx] + addition + content[close_idx:]

    @staticmethod
    def _write_dep_fallback(pyproject_path: Path, missing: list[str]) -> None:
        """Write a sidecar file listing deps that must be added manually."""
        sidecar = pyproject_path.parent / "AI_DEPENDENCIES.txt"
        sidecar.write_text(
            "FastForge AI: could not auto-add the following dependencies to "
            "pyproject.toml.\nPlease add them manually under [project] dependencies:\n\n"
            + "\n".join(missing)
            + "\n"
        )
