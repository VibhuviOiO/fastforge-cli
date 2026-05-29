"""AI configuration — loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class AISettings(BaseSettings):
    """AI infrastructure configuration.

    All values are read from environment variables prefixed with AI_.
    """

    model_config = {"env_prefix": "AI_"}

    # Gateway
    gateway_provider: str = "litellm"  # litellm | bifrost
    gateway_base_url: str = "http://localhost:4000"
    gateway_api_key: str = ""

    # Embedding
    embedding_provider: str = "openai"  # openai | gemini | cohere | huggingface | bedrock | local
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Vector store
    vector_store_provider: str = "chromadb"  # vertex_ai | chromadb | opensearch | pgvector | qdrant
    vector_store_collection: str = "default"

    # App kind
    app_kind: str = "semantic_search"  # semantic_search | rag | agent

    # Vertex AI specific
    vertex_ai_project: str = ""
    vertex_ai_location: str = "us-central1"
    vertex_ai_index_endpoint: str = ""
    vertex_ai_deployed_index_id: str = ""

    # ChromaDB specific
    chromadb_host: str = "localhost"
    chromadb_port: int = 8000

    # OpenSearch specific
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_index: str = "vectors"
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_use_ssl: bool = False
    opensearch_verify_certs: bool = True

    # pgvector specific
    pgvector_dsn: str = "postgresql+asyncpg://user:pass@localhost:5432/vectors"

    # Qdrant specific
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""

    # OpenAI specific
    openai_api_key: str = ""

    # Gemini specific
    gemini_api_key: str = ""
    gemini_model: str = "models/embedding-001"

    # Cohere specific
    cohere_api_key: str = ""

    # HuggingFace specific
    huggingface_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Bedrock specific
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.titan-embed-text-v1"

    # RAG specific
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5

    # Agent specific
    agent_model: str = "gpt-4o"
    agent_max_iterations: int = 10
