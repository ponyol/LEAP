"""FastAPI application for LEAP Search Server.

This module provides the main FastAPI application for the search server.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from leap.indexer.embeddings import EmbeddingProvider, get_embedding_provider
from leap.indexer.vector_stores import VectorStore, get_vector_store
from leap.search_server.api.models import (
    CodebaseInfo,
    CodebasesResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from leap.search_server.config import SearchServerConfig
from leap.search_server.retrieval import HybridSearcher, Reranker


class SearchServerState:
    """Global state for the search server.

    Attributes:
        config: Server configuration
        embeddings: Embedding provider
        vector_store: Vector store
        hybrid_searcher: Hybrid searcher (BM25 + Vector)
        reranker: Re-ranker model
        models_loaded: Whether models are loaded
    """

    def __init__(self, config: SearchServerConfig) -> None:
        """Initialize search server state.

        Args:
            config: Server configuration
        """
        self.config = config
        self.embeddings: EmbeddingProvider | None = None
        self.vector_store: VectorStore | None = None
        self.hybrid_searcher: HybridSearcher | None = None
        self.reranker: Reranker | None = None
        self.models_loaded = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager.

    Loads models and initializes resources on startup,
    cleans up on shutdown.

    Args:
        app: FastAPI application
    """
    # Startup: Load models
    state: SearchServerState = app.state.search_state

    print("Loading embedding model...")
    from leap.indexer.config import EmbeddingModelType, IndexerConfig

    indexer_config = IndexerConfig(
        vector_store=state.config.vector_store,
        embedding_model=EmbeddingModelType.SENTENCE_TRANSFORMERS,
        embedding_model_name=state.config.embedding_model_name,
        chromadb_path=state.config.chromadb_path,
        qdrant_url=state.config.qdrant_url,
        qdrant_api_key=state.config.qdrant_api_key,
        show_progress=False,
    )

    state.embeddings = get_embedding_provider(indexer_config)
    state.vector_store = get_vector_store(indexer_config)

    # Load hybrid searcher and reranker if enabled
    if state.config.enable_hybrid_search:
        print("Loading hybrid searcher...")
        state.hybrid_searcher = HybridSearcher()
        print("✓ Hybrid searcher initialized")

    if state.config.enable_reranking:
        print(f"Loading reranker model: {state.config.reranker_model_name}...")
        state.reranker = Reranker(state.config.reranker_model_name)
        print("✓ Reranker model loaded")

    state.models_loaded = True

    print(f"✓ Embedding model loaded: {state.config.embedding_model_name}")
    print(f"✓ Vector store connected: {state.config.vector_store.value}")

    yield

    # Shutdown: Cleanup (if needed)
    print("Shutting down...")


def create_app(config: SearchServerConfig) -> FastAPI:
    """Create FastAPI application.

    Args:
        config: Server configuration

    Returns:
        FastAPI application
    """
    app = FastAPI(
        title="LEAP Search Server",
        description="Semantic search API for analyzed logs",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Initialize state
    app.state.search_state = SearchServerState(config)

    # Setup templates
    template_dir = Path(__file__).parent / "ui" / "templates"
    templates = Jinja2Templates(directory=str(template_dir))

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    @app.post("/api/search", response_model=SearchResponse)
    async def search(request: SearchRequest) -> SearchResponse:
        """Search for similar logs.

        Args:
            request: Search request

        Returns:
            Search response with results
        """
        state: SearchServerState = app.state.search_state

        if not state.models_loaded:
            raise HTTPException(status_code=503, detail="Models not loaded")

        start_time = time.time()

        try:
            # Determine which collections to search
            collections = _get_collections_to_search(
                state=state,
                codebase=request.codebase,
                language=request.language,
            )

            if not collections:
                return SearchResponse(
                    results=[],
                    total_found=0,
                    search_time_ms=0.0,
                )

            # Generate query embedding
            if state.embeddings is None:
                raise HTTPException(status_code=503, detail="Embeddings not loaded")
            query_embedding = state.embeddings.embed_query(request.query)

            # Search in each collection
            if state.vector_store is None:
                raise HTTPException(status_code=503, detail="Vector store not loaded")

            from leap.indexer.vector_stores import SearchResult

            all_results: list[SearchResult] = []
            for collection_name in collections:
                try:
                    # Get more results for hybrid search and reranking
                    initial_top_k = request.top_k * 4 if state.config.enable_hybrid_search or state.config.enable_reranking else request.top_k
                    results = state.vector_store.search(
                        collection_name=collection_name,
                        query_embedding=query_embedding,
                        top_k=initial_top_k,
                        filters=_convert_filters(request.filters),
                    )
                    all_results.extend(results)
                except Exception as e:
                    # Collection might not exist, skip it
                    print(f"Warning: Error searching collection {collection_name}: {e}")
                    continue

            # Apply hybrid search if enabled
            if state.config.enable_hybrid_search and state.hybrid_searcher:
                all_results = state.hybrid_searcher.search(
                    query=request.query,
                    vector_results=all_results,
                    top_k=request.top_k * 2,  # Keep more for reranking
                )
            else:
                # Sort by score and take top results
                all_results.sort(key=lambda x: x.score, reverse=True)
                all_results = all_results[: request.top_k * 2]

            # Apply reranking if enabled
            if state.config.enable_reranking and state.reranker:
                # Extract documents for reranking
                documents = [r.document.text for r in all_results]
                reranked_indices = state.reranker.rerank(
                    query=request.query,
                    documents=documents,
                    top_k=request.top_k,
                )
                # Reorder results based on reranker scores
                top_results = []
                for idx, score in reranked_indices:
                    result = all_results[idx]
                    result.score = score  # Update score with reranker score
                    top_results.append(result)
            else:
                # Just take top_k
                top_results = all_results[: request.top_k]

            # Convert to API models
            result_items = [
                SearchResultItem(
                    id=r.document.id,
                    log_template=r.document.metadata.get("log_template", ""),
                    analysis=r.document.metadata.get("analysis", ""),
                    severity=r.document.metadata.get("severity", "INFO"),
                    source_file=r.document.metadata.get("source_file", ""),
                    codebase_name=_extract_codebase_from_collection(
                        r.document.metadata.get("collection_name", "")
                    ),
                    language=r.document.metadata.get("language", "en"),
                    score=r.score,
                    suggested_action=r.document.metadata.get("suggested_action", ""),
                    metadata=r.document.metadata,
                )
                for r in top_results
            ]

            # Calculate search time
            search_time_ms = (time.time() - start_time) * 1000

            return SearchResponse(
                results=result_items,
                total_found=len(all_results),
                search_time_ms=search_time_ms,
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/codebases", response_model=CodebasesResponse)
    async def get_codebases() -> CodebasesResponse:
        """Get list of available codebases.

        Returns:
            List of codebases with statistics
        """
        state: SearchServerState = app.state.search_state

        if not state.models_loaded:
            raise HTTPException(status_code=503, detail="Models not loaded")

        if state.vector_store is None:
            raise HTTPException(status_code=503, detail="Vector store not loaded")

        try:
            collections = state.vector_store.list_collections()

            # Group collections by codebase
            codebases: dict[str, dict[str, Any]] = {}

            for collection_name in collections:
                # Parse collection name: logs_{lang}_{codebase}
                if not collection_name.startswith("logs_"):
                    continue

                parts = collection_name.split("_", 2)
                if len(parts) < 3:
                    continue

                lang = parts[1]
                codebase = parts[2]

                if codebase not in codebases:
                    codebases[codebase] = {
                        "name": codebase,
                        "total_logs": 0,
                        "ru_logs": 0,
                        "en_logs": 0,
                        "last_indexed": None,
                    }

                # Get collection stats
                stats = state.vector_store.get_collection_stats(collection_name)
                count = stats.get("document_count", 0)

                codebases[codebase]["total_logs"] += count
                if lang == "ru":
                    codebases[codebase]["ru_logs"] = count
                elif lang == "en":
                    codebases[codebase]["en_logs"] = count

            # Convert to API models
            codebase_infos = [
                CodebaseInfo(**cb_data) for cb_data in codebases.values()
            ]

            return CodebasesResponse(codebases=codebase_infos)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint.

        Returns:
            Health status
        """
        state: SearchServerState = app.state.search_state

        return HealthResponse(
            status="ok" if state.models_loaded else "error",
            vector_store=state.config.vector_store.value,
            models_loaded=state.models_loaded,
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Serve the web UI.

        Args:
            request: FastAPI request

        Returns:
            HTML page
        """
        return templates.TemplateResponse("index.html", {"request": request})

    return app


def _get_collections_to_search(
    state: SearchServerState,
    codebase: str | None,
    language: str,
) -> list[str]:
    """Get list of collections to search based on filters.

    Args:
        state: Search server state
        codebase: Optional codebase filter
        language: Language filter (auto, ru, en)

    Returns:
        List of collection names to search
    """
    if state.vector_store is None:
        return []
    all_collections = state.vector_store.list_collections()

    # Filter by pattern: logs_{lang}_{codebase}
    collections = []

    for collection_name in all_collections:
        if not collection_name.startswith("logs_"):
            continue

        parts = collection_name.split("_", 2)
        if len(parts) < 3:
            continue

        lang = parts[1]
        cb = parts[2]

        # Filter by codebase
        if codebase and cb != codebase:
            continue

        # Filter by language
        if language != "auto" and lang != language:
            continue

        collections.append(collection_name)

    return collections


def _convert_filters(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert API filters to vector store filters.

    Args:
        filters: API filters

    Returns:
        Vector store filters
    """
    if not filters:
        return None

    # For now, pass through as-is
    # ChromaDB and Qdrant have similar filter syntax
    return filters


def _extract_codebase_from_collection(collection_name: str) -> str:
    """Extract codebase name from collection name.

    Args:
        collection_name: Collection name (logs_{lang}_{codebase})

    Returns:
        Codebase name
    """
    if not collection_name.startswith("logs_"):
        return "unknown"

    parts = collection_name.split("_", 2)
    if len(parts) < 3:
        return "unknown"

    return parts[2]
