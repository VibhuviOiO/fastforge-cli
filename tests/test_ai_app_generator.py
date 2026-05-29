"""Tests for fastforge.generators.ai_app — AI infrastructure generator."""

from __future__ import annotations

import json

import pytest

from fastforge.generators.ai_app import AIAppGenerator


@pytest.fixture
def ai_generator():
    return AIAppGenerator()


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project structure."""
    (tmp_path / "app" / "api" / "routes").mkdir(parents=True)
    (tmp_path / ".fastforge.json").write_text(
        json.dumps(
            {
                "project_slug": "test-app",
                "kind": "standalone",
            }
        )
    )
    return tmp_path


class TestAIAppGeneratorProtocol:
    """Test that AIAppGenerator satisfies the Generator protocol."""

    def test_has_required_properties(self, ai_generator):
        assert ai_generator.name == "ai-app"
        assert ai_generator.version == "1.0.0"
        assert ai_generator.capability_key == "ai_app_kind"
        assert ai_generator.delegatable is True

    def test_description_is_not_empty(self, ai_generator):
        assert len(ai_generator.description) > 0


class TestEmitInline:
    """Test emit_inline generates the correct file structure."""

    def test_creates_ai_directory_structure(self, ai_generator, project_dir):
        result = ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        assert result["status"] == "ok"
        assert len(result["created"]) > 0

        ai_dir = project_dir / "app" / "ai"
        assert ai_dir.exists()
        assert (ai_dir / "config.py").exists()
        assert (ai_dir / "lifespan.py").exists()
        assert (ai_dir / "dependencies.py").exists()

    def test_creates_gateway_files(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        gateway_dir = project_dir / "app" / "ai" / "gateway"
        assert (gateway_dir / "__init__.py").exists()
        assert (gateway_dir / "registry.py").exists()
        assert (gateway_dir / "litellm_client.py").exists()
        assert (gateway_dir / "bifrost_client.py").exists()

    def test_creates_embedding_files(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        emb_dir = project_dir / "app" / "ai" / "embeddings"
        assert (emb_dir / "__init__.py").exists()
        assert (emb_dir / "registry.py").exists()
        assert (emb_dir / "openai_provider.py").exists()
        assert (emb_dir / "gemini_provider.py").exists()
        assert (emb_dir / "cohere_provider.py").exists()
        assert (emb_dir / "huggingface_provider.py").exists()
        assert (emb_dir / "bedrock_provider.py").exists()
        assert (emb_dir / "local_provider.py").exists()

    def test_creates_vector_store_files(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        vs_dir = project_dir / "app" / "ai" / "vector_store"
        assert (vs_dir / "__init__.py").exists()
        assert (vs_dir / "registry.py").exists()
        assert (vs_dir / "vertex_ai_provider.py").exists()
        assert (vs_dir / "chromadb_provider.py").exists()
        assert (vs_dir / "opensearch_provider.py").exists()
        assert (vs_dir / "pgvector_provider.py").exists()
        assert (vs_dir / "qdrant_provider.py").exists()

    def test_creates_app_kind_files(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        kinds_dir = project_dir / "app" / "ai" / "app_kinds"
        assert (kinds_dir / "__init__.py").exists()
        assert (kinds_dir / "semantic_search.py").exists()
        assert (kinds_dir / "rag.py").exists()
        assert (kinds_dir / "agent.py").exists()

    def test_creates_example_route_semantic_search(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        route_file = project_dir / "app" / "api" / "routes" / "ai.py"
        assert route_file.exists()
        content = route_file.read_text()
        assert "SearchOrchestrator" in content
        assert "/ai/search" in content

    def test_creates_example_route_rag(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "rag",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        route_file = project_dir / "app" / "api" / "routes" / "ai.py"
        content = route_file.read_text()
        assert "RAGOrchestrator" in content
        assert "/ai/rag" in content

    def test_creates_example_route_agent(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "agent",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        route_file = project_dir / "app" / "api" / "routes" / "ai.py"
        content = route_file.read_text()
        assert "AgentOrchestrator" in content
        assert "/ai/agent" in content

    def test_updates_fastforge_json(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "rag",
                "gateway_provider": "bifrost",
                "embedding_provider": "gemini",
                "vector_store_provider": "vertex_ai",
            },
        )

        config = json.loads((project_dir / ".fastforge.json").read_text())
        assert config["ai_app_kind"] == "rag"
        assert config["llm_gateway"] == "bifrost"
        assert config["embeddings_provider"] == "gemini"
        assert config["vector_store"] == "vertex_ai"

    def test_creates_env_example(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        env_file = project_dir / ".env.example"
        assert env_file.exists()
        content = env_file.read_text()
        assert "AI_GATEWAY_PROVIDER=litellm" in content
        assert "AI_EMBEDDING_PROVIDER=openai" in content
        assert "AI_VECTOR_STORE_PROVIDER=chromadb" in content
        assert "AI_CHROMADB_HOST" in content


class TestIdempotency:
    """Test that running the generator twice produces no additional changes."""

    def test_second_run_is_noop(self, ai_generator, project_dir):
        args = {
            "ai_app_kind": "semantic_search",
            "gateway_provider": "litellm",
            "embedding_provider": "openai",
            "vector_store_provider": "chromadb",
        }

        # First run
        result1 = ai_generator.emit_inline(project_dir, args)
        assert result1["status"] == "ok"

        # Second run — should be idempotent
        result2 = ai_generator.emit_inline(project_dir, args)
        assert result2["status"] == "already_configured"
        assert result2["created"] == []
        assert result2["modified"] == []


class TestValidate:
    """Test the validate method."""

    def test_validate_healthy(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        warnings = ai_generator.validate(project_dir)
        assert warnings == []

    def test_validate_missing_ai_dir(self, ai_generator, project_dir):
        warnings = ai_generator.validate(project_dir)
        assert any("app/ai/ directory is missing" in w for w in warnings)


class TestUpgrade:
    """Test the upgrade method."""

    def test_upgrade_from_0_is_noop(self, ai_generator, project_dir):
        result = ai_generator.upgrade(project_dir, "0.0.0")
        assert result["status"] == "no_change"


class TestEnvVarsByProvider:
    """Test that correct env vars are generated for each provider combo."""

    def test_vertex_ai_env_vars(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "vertex_ai",
            },
        )

        content = (project_dir / ".env.example").read_text()
        assert "AI_VERTEX_AI_PROJECT=" in content
        assert "AI_VERTEX_AI_LOCATION=" in content
        assert "AI_VERTEX_AI_INDEX_ENDPOINT=" in content

    def test_pgvector_env_vars(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "pgvector",
            },
        )

        content = (project_dir / ".env.example").read_text()
        assert "AI_PGVECTOR_DSN=" in content

    def test_gemini_embedding_env_vars(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "gemini",
                "vector_store_provider": "chromadb",
            },
        )

        content = (project_dir / ".env.example").read_text()
        assert "AI_GEMINI_API_KEY=" in content

    def test_bedrock_embedding_env_vars(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "bedrock",
                "vector_store_provider": "chromadb",
            },
        )

        content = (project_dir / ".env.example").read_text()
        assert "AI_BEDROCK_REGION=" in content


# ─────────────────────────────────────────────────────────────────────────────
# Regression tests for production-grade fixes (B1–B5, D1–D6, P*)
# ─────────────────────────────────────────────────────────────────────────────


class TestDependencyInjection:
    """B4: robust pyproject.toml dependency injection."""

    def _seed_pyproject(self, project_dir, body: str) -> None:
        (project_dir / "pyproject.toml").write_text(body)

    def test_injects_into_simple_dependencies_array(self, ai_generator, project_dir):
        self._seed_pyproject(
            project_dir, ('[project]\nname = "x"\ndependencies = [\n    "fastapi==0.115.0",\n]\n')
        )
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )
        content = (project_dir / "pyproject.toml").read_text()
        assert "# ai-infrastructure-deps" in content
        assert "httpx==0.27.0" in content
        assert "chromadb==0.5.0" in content
        # Original entry preserved
        assert "fastapi==0.115.0" in content

    def test_skips_already_present_deps(self, ai_generator, project_dir):
        self._seed_pyproject(
            project_dir, ('[project]\nname = "x"\ndependencies = [\n    "httpx==0.27.0",\n]\n')
        )
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )
        content = (project_dir / "pyproject.toml").read_text()
        # httpx should appear only once even after injection
        assert content.count("httpx==0.27.0") == 1

    def test_fallback_sidecar_when_no_dependencies_block(self, ai_generator, project_dir):
        self._seed_pyproject(project_dir, '[project]\nname = "x"\n')
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )
        sidecar = project_dir / "AI_DEPENDENCIES.txt"
        assert sidecar.exists()
        assert "httpx==0.27.0" in sidecar.read_text()


class TestGeneratedCodeCompiles:
    """P4: generated AI infrastructure must be syntactically valid Python."""

    def test_compileall_passes(self, ai_generator, project_dir):
        import compileall

        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )
        ok = compileall.compile_dir(
            str(project_dir / "app" / "ai"),
            quiet=1,
            force=True,
        )
        assert ok, "generated app/ai/ failed py_compile"


class TestVectorStoreDimension:
    """B1: vector stores must honor settings.embedding_dimensions."""

    def test_pgvector_template_no_longer_hardcodes_1536(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "pgvector",
            },
        )
        src = (project_dir / "app" / "ai" / "vector_store" / "pgvector_provider.py").read_text()
        assert "vector(1536)" not in src
        assert "self._dimensions" in src

    def test_opensearch_template_no_longer_hardcodes_1536(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "opensearch",
            },
        )
        src = (project_dir / "app" / "ai" / "vector_store" / "opensearch_provider.py").read_text()
        assert '"dimension": 1536' not in src
        assert "self._dimensions" in src

    def test_qdrant_template_no_longer_hardcodes_1536(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "qdrant",
            },
        )
        src = (project_dir / "app" / "ai" / "vector_store" / "qdrant_provider.py").read_text()
        assert "size=1536" not in src
        assert "self._dimensions" in src


class TestAgentToolCalls:
    """B2: agent must use CompletionRequest.tools, not metadata."""

    def test_agent_template_uses_tools_field(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "agent",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )
        agent_src = (project_dir / "app" / "ai" / "app_kinds" / "agent.py").read_text()
        assert "tools=tool_schemas" in agent_src
        assert 'metadata={"tools"' not in agent_src

    def test_litellm_template_extracts_tool_calls(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "agent",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )
        src = (project_dir / "app" / "ai" / "gateway" / "litellm_client.py").read_text()
        assert "tool_calls" in src
        assert 'payload["tools"]' in src


class TestVertexAIFailLoud:
    """B3: Vertex AI stubs must raise, not silently succeed."""

    def test_vertex_ai_template_raises_on_upsert(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "vertex_ai",
            },
        )
        src = (project_dir / "app" / "ai" / "vector_store" / "vertex_ai_provider.py").read_text()
        assert "raise NotImplementedError" in src


class TestPgVectorIdentifierValidation:
    """D1: pgvector collection name must be whitelist-validated."""

    def test_pgvector_template_has_identifier_check(self, ai_generator, project_dir):
        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "pgvector",
            },
        )
        src = (project_dir / "app" / "ai" / "vector_store" / "pgvector_provider.py").read_text()
        assert "_IDENT_RE" in src
        assert "Invalid pgvector collection name" in src


class TestMainAndReadmeAutoWiring:
    """Regression tests for app/main.py + README auto-wiring."""

    def test_wires_ai_router_and_lifespan_into_main(self, ai_generator, project_dir):
        (project_dir / "app").mkdir(exist_ok=True)
        (project_dir / "app" / "main.py").write_text(
            """from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()
"""
        )

        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "openai",
                "vector_store_provider": "chromadb",
            },
        )

        main_src = (project_dir / "app" / "main.py").read_text()
        assert "from app.api.routes.ai import router as ai_router" in main_src
        assert "from app.ai.lifespan import ai_lifespan" in main_src
        assert "def merged_lifespan" in main_src
        assert "lifespan=merged_lifespan" in main_src
        assert "app.include_router(ai_router)" in main_src

    def test_adds_ml_runbook_to_readme(self, ai_generator, project_dir):
        (project_dir / "README.md").write_text(
            "# sample\n\n## Environment\n\nConfiguration is managed via environment variables.\n"
            "\n## Extend Your Project\n"
        )

        ai_generator.emit_inline(
            project_dir,
            {
                "ai_app_kind": "semantic_search",
                "gateway_provider": "litellm",
                "embedding_provider": "gemini",
                "vector_store_provider": "vertex_ai",
            },
        )

        readme = (project_dir / "README.md").read_text()
        assert "## AI Runbook (Generated)" in readme
        assert "AI_GEMINI_API_KEY=<required>" in readme
        assert "AI_VERTEX_AI_PROJECT=<required>" in readme
        assert "Cloud Run concurrency at `250`" in readme
