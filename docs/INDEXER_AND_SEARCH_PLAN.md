# LEAP Indexer & Search Server - Implementation Plan

**Created**: 2025-11-17
**Status**: In Development
**Components**: Indexer (CLI) + Search Server (FastAPI)

---

## Executive Summary

This document outlines the implementation plan for Components 3.1 (Log Indexer) and 3.2 (Search Server) of the LEAP project. The goal is to create a semantic search system for analyzed logs with:

- **Multilingual support** (Russian + English)
- **Hybrid search** (BM25 + Vector + Re-Ranking)
- **Codebase-aware indexing** (multiple projects support)
- **Web UI + REST API**
- **Auto-reindexing** (watch mode)

---

## Architecture Overview

### System Components

```
leap/
├── indexer/                     # Component 3.1: CLI for indexing
│   ├── __init__.py             # Public API
│   ├── config.py               # IndexerConfig (Pydantic)
│   ├── indexer.py              # Main orchestration
│   ├── embeddings/
│   │   ├── __init__.py         # Embeddings factory
│   │   ├── base.py             # Abstract EmbeddingProvider
│   │   └── sentence_transformers.py  # Local embeddings
│   ├── vector_stores/
│   │   ├── __init__.py         # VectorStore factory
│   │   ├── base.py             # Abstract VectorStore
│   │   ├── chromadb.py         # ChromaDB implementation
│   │   └── qdrant.py           # Qdrant implementation
│   └── language_detector.py    # Language detection (ru/en)
│
├── search_server/              # Component 3.2: Search Server
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── config.py               # ServerConfig
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── hybrid_search.py    # EnsembleRetriever (BM25 + Vector)
│   │   └── reranker.py         # jina-reranker-v2-base-multilingual
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API endpoints
│   │   └── models.py           # Pydantic models
│   └── ui/
│       ├── static/             # CSS, JS
│       └── templates/          # Jinja2 templates
│
└── cli.py                      # + new commands: index, serve, search
```

---

## Data Model

### Collection Strategy

**Two collections per codebase** (language separation):

```
ChromaDB/Qdrant:
├── logs_en_{codebase}    # English logs
└── logs_ru_{codebase}    # Russian logs

Example:
├── logs_en_backend-python
├── logs_ru_backend-python
├── logs_en_frontend-react
└── logs_ru_frontend-react
```

### Document Schema

```json
{
  "id": "sha256(source_file + log_template)",
  "text": "[log_template] + [analysis]",
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "codebase_name": "backend-python",
    "language": "ru",
    "log_template": "Failed to connect to database",
    "analysis": "This error occurs when...",
    "severity": "ERROR",
    "suggested_action": "Check database credentials...",
    "source_file": "src/db.py",
    "line_number": 156,
    "indexed_at": "2025-11-17T10:30:00Z"
  }
}
```

---

## Technology Stack

### Vector Stores
- **ChromaDB** (default): Embedded, no external services
- **Qdrant**: Production-ready, Docker-based

### Embedding Models
- **Primary**: `paraphrase-multilingual-MiniLM-L12-v2`
  - Dimensions: 384
  - Languages: 50+ (including Russian, English)
  - Size: ~120 MB
  - Speed: ~500 embeddings/sec on CPU

### Re-Ranker
- **Model**: `jinaai/jina-reranker-v2-base-multilingual`
  - Format: F16 (float16)
  - Size: ~500 MB
  - Speed: ~20-30 pairs/sec on CPU
  - Languages: Multilingual

### Search Pipeline

```
1. User Query → "database connection timeout"
                 ↓
2. Hybrid Search (LangChain EnsembleRetriever)
   ├── BM25 Retriever → Top 20 results (keyword matching)
   └── Vector Retriever → Top 20 results (semantic search)
   ↓ (weighted: 0.5 BM25 + 0.5 Vector)
   ↓
3. Combined Top 20 results
   ↓
4. Re-Ranker (jina-reranker-v2-base-multilingual-F16)
   ↓ (scores each result 0-1)
   ↓
5. Final Top K results (ranked by relevance)
```

### Language Detection
- **Library**: `langdetect`
- **Strategy**:
  1. Analyze `log_template + analysis`
  2. If confidence > 0.7 for Russian → "ru"
  3. If confidence > 0.7 for English → "en"
  4. Fallback → "en"

---

## CLI Interface

### 1. Indexing

```bash
# Basic indexing (auto language detection)
leap index analyzed_logs.json \
  --codebase backend-python \
  --vector-store chromadb

# With watch mode (auto-reindex on file changes)
leap index analyzed_logs.json \
  --codebase backend-python \
  --watch

# With Qdrant
leap index analyzed_logs.json \
  --codebase frontend-react \
  --vector-store qdrant \
  --qdrant-url http://localhost:6333

# Output:
# ✓ Detected 856 Russian logs, 412 English logs
# ✓ Creating collections: logs_ru_backend-python, logs_en_backend-python
# ✓ Indexing Russian logs... [████████████████] 856/856 (100%)
# ✓ Indexing English logs... [████████████████] 412/412 (100%)
# ✓ Done! Indexed 1268 logs in 2m 34s
```

### 2. Start Search Server

```bash
# Start server with ChromaDB
leap serve --vector-store chromadb --port 8000

# Start with Qdrant
leap serve --vector-store qdrant --qdrant-url http://localhost:6333

# Output:
# ✓ Loading models...
#   - Embeddings: paraphrase-multilingual-MiniLM-L12-v2 ✓
#   - Re-Ranker: jina-reranker-v2-base-multilingual ✓
# ✓ Connecting to ChromaDB...
# ✓ Found 3 codebases: backend-python, frontend-react, ml-pipeline
#
# 🚀 Server running at http://localhost:8000
#    - Web UI: http://localhost:8000
#    - API Docs: http://localhost:8000/docs
#
# Press Ctrl+C to stop
```

### 3. CLI Search (optional)

```bash
# Quick search from CLI
leap search "database timeout" \
  --codebase backend-python \
  --top-k 5

# Output:
# Found 5 results in 0.23s:
#
# 1. [ERROR] src/db.py:156 (Score: 0.94)
#    Template: Failed to connect to database
#    Analysis: This error occurs when...
#    Action: Check database credentials...
# ...
```

---

## API Endpoints

### POST /api/search

**Request:**
```json
{
  "query": "database connection timeout",
  "codebase": "backend-python",
  "language": "auto",
  "top_k": 5,
  "filters": {
    "severity": ["ERROR", "CRITICAL"]
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "abc123",
      "log_template": "Failed to connect to database",
      "analysis": "This error occurs when...",
      "severity": "ERROR",
      "source_file": "src/db.py:156",
      "codebase_name": "backend-python",
      "language": "ru",
      "score": 0.94,
      "metadata": {...}
    }
  ],
  "total_found": 47,
  "search_time_ms": 234
}
```

### GET /api/codebases

**Response:**
```json
{
  "codebases": [
    {
      "name": "backend-python",
      "total_logs": 1268,
      "ru_logs": 856,
      "en_logs": 412,
      "last_indexed": "2025-11-17T10:30:00Z"
    }
  ]
}
```

### GET /api/health

**Response:**
```json
{
  "status": "ok",
  "vector_store": "chromadb",
  "models_loaded": true
}
```

---

## Web Interface

**Simple UI for testing:**

```
┌─────────────────────────────────────────────────────────┐
│  LEAP Log Search                                        │
├─────────────────────────────────────────────────────────┤
│  Query: [database connection timeout____________]  🔍  │
│                                                         │
│  Codebase: [All codebases ▼]                           │
│  Language: [Auto ▼]    Top K: [5_]                     │
│  Severity: □ DEBUG  □ INFO  ☑ ERROR  ☑ CRITICAL       │
│                                                         │
│  ─────────────────────────────────────────────────────  │
│  Results (5 found in 0.23s):                           │
│                                                         │
│  1. [ERROR] backend-python • src/db.py:156  Score: 0.94│
│     Template: Failed to connect to database            │
│     Analysis: This error occurs when the application...│
│     Action: Check database credentials and network...  │
│     [View Full]                                         │
│                                                         │
│  2. [ERROR] backend-python • src/api.py:89  Score: 0.87│
│     ...                                                 │
└─────────────────────────────────────────────────────────┘
```

**Technologies:**
- **Backend**: FastAPI + Jinja2 templates
- **Frontend**: HTMX (dynamic search without JS frameworks) + Alpine.js (interactivity)
- **Styling**: Tailwind CSS or custom CSS

---

## Docker Support

### docker-compose.yml

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  leap-search:
    build: .
    ports:
      - "8000:8000"
    environment:
      - VECTOR_STORE=qdrant
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - qdrant
    volumes:
      - ./data:/app/data

volumes:
  qdrant_data:
```

**Usage:**
```bash
# Start all services
docker-compose up -d

# Index logs
docker-compose exec leap-search leap index /app/data/analyzed_logs.json \
  --codebase backend-python

# Access UI at http://localhost:8000
```

---

## Implementation Phases

### Phase 1: Basic Indexing (3-4 days)

**Deliverables:**
- ✅ Module structure: `leap/indexer/`
- ✅ `config.py` with Pydantic models
- ✅ Embeddings provider (paraphrase-multilingual-MiniLM-L12-v2)
- ✅ ChromaDB integration
- ✅ Language detector
- ✅ CLI command: `leap index`

**Files to create:**
```
leap/indexer/
├── __init__.py
├── config.py
├── indexer.py
├── language_detector.py
├── embeddings/
│   ├── __init__.py
│   ├── base.py
│   └── sentence_transformers.py
└── vector_stores/
    ├── __init__.py
    ├── base.py
    └── chromadb.py
```

**Key features:**
- Load `analyzed_logs.json`
- Detect language (ru/en) for each log
- Generate embeddings
- Create collections: `logs_{lang}_{codebase}`
- Batch processing with progress bar

---

### Phase 2: Basic Search Server (3-4 days)

**Deliverables:**
- ✅ Module structure: `leap/search_server/`
- ✅ FastAPI app (`main.py`)
- ✅ Vector search (without BM25/reranking yet)
- ✅ API endpoints: `/api/search`, `/api/codebases`, `/api/health`
- ✅ CLI command: `leap serve`

**Files to create:**
```
leap/search_server/
├── __init__.py
├── main.py
├── config.py
└── api/
    ├── __init__.py
    ├── routes.py
    └── models.py
```

**Key features:**
- Connect to ChromaDB
- Basic vector search
- Filter by codebase, language, severity
- JSON API responses
- CORS support

---

### Phase 3: Hybrid Search + Re-Ranking (2-3 days)

**Deliverables:**
- ✅ BM25 retriever (LangChain)
- ✅ EnsembleRetriever (BM25 + Vector)
- ✅ Re-Ranker integration (jina-reranker-v2)
- ✅ Optimized pipeline

**Files to create:**
```
leap/search_server/retrieval/
├── __init__.py
├── hybrid_search.py
└── reranker.py
```

**Key features:**
- Keyword search (BM25)
- Semantic search (Vector)
- Weighted combination (0.5 + 0.5)
- Re-ranking top 20 → top K

---

### Phase 4: Web Interface (2-3 days)

**Deliverables:**
- ✅ HTML templates (Jinja2)
- ✅ HTMX for dynamic search
- ✅ Alpine.js for interactivity
- ✅ Styling (Tailwind CSS or custom)

**Files to create:**
```
leap/search_server/ui/
├── static/
│   ├── css/
│   │   └── main.css
│   └── js/
│       └── main.js
└── templates/
    ├── base.html
    ├── index.html
    └── search_results.html
```

**Key features:**
- Search form with filters
- Real-time search (on typing)
- Result cards with syntax highlighting
- Responsive design

---

### Phase 5: Qdrant + Tests (2-3 days)

**Deliverables:**
- ✅ Qdrant vector store implementation
- ✅ Unit tests for indexer
- ✅ Integration tests for search server
- ✅ Documentation and examples

**Files to create:**
```
leap/indexer/vector_stores/qdrant.py
tests/test_indexer.py
tests/test_search_server.py
```

**Key features:**
- Qdrant client integration
- Collection management
- Test fixtures
- CI/CD integration

---

### Phase 6: Additional Features (2-3 days)

**Deliverables:**
- ✅ Watch mode for auto-reindexing
- ✅ Docker Compose setup
- ✅ Update dependencies in `pyproject.toml`

**Files to create:**
```
docker-compose.yml
Dockerfile
.dockerignore
```

**Key features:**
- File watcher (watchdog library)
- Auto-reindex on `analyzed_logs.json` changes
- Docker images for services
- Production deployment guide

---

## Dependencies

### New Dependencies to Add

```toml
[tool.poetry.dependencies]
# Embeddings & Re-Ranking
sentence-transformers = "^3.3.1"
torch = "^2.6.0"  # Required by sentence-transformers

# Language Detection
langdetect = "^1.0.9"

# Vector Stores
chromadb = "^0.5.23"
qdrant-client = "^1.12.1"

# LangChain (Hybrid Search)
langchain = "^0.3.13"
langchain-community = "^0.3.13"
rank-bm25 = "^0.2.2"

# FastAPI (Search Server)
fastapi = "^0.115.6"
uvicorn = {version = "^0.34.0", extras = ["standard"]}
jinja2 = "^3.1.5"
python-multipart = "^0.0.20"

# File Watching
watchdog = "^6.0.0"
```

---

## Performance Estimates

### Indexing Performance (1268 logs example)

**ChromaDB + Local Embeddings:**
- Embedding generation: ~2-3 minutes (CPU)
- ChromaDB insertion: ~5-10 seconds
- **Total**: ~2.5-3.5 minutes

**Qdrant + Local Embeddings:**
- Embedding generation: ~2-3 minutes (CPU)
- Qdrant insertion: ~3-5 seconds
- **Total**: ~2.5-3.5 minutes

### Search Performance

**Vector Search Only:**
- Query embedding: ~50ms
- Vector search: ~20-50ms
- **Total**: ~70-100ms

**Hybrid Search + Re-Ranking:**
- Query embedding: ~50ms
- BM25 search: ~10-20ms
- Vector search: ~20-50ms
- Re-ranking (20 candidates): ~200-300ms
- **Total**: ~280-420ms

---

## Storage Requirements

**Per 1000 logs:**
- ChromaDB: ~1.5-3 MB
- Qdrant: ~1-2 MB (better compression)

**Models:**
- Embeddings model: ~120 MB
- Re-Ranker model: ~500 MB
- **Total**: ~620 MB (loaded in memory)

---

## Success Criteria

1. ✅ Successfully index logs from `analyzed_logs.json`
2. ✅ Automatic language detection (>95% accuracy)
3. ✅ Hybrid search returns relevant results (top-5 precision >80%)
4. ✅ Re-ranking improves relevance (NDCG improvement >10%)
5. ✅ Web UI loads in <1 second
6. ✅ Search completes in <500ms
7. ✅ All tests pass: `pytest && mypy leap && ruff check leap`
8. ✅ Docker Compose setup works out of the box

---

## Future Enhancements (Post-MVP)

1. **Advanced Filters:**
   - Date range filtering
   - File path patterns (regex)
   - Multi-severity selection

2. **Analytics:**
   - Most searched queries
   - Common error patterns
   - Trending issues

3. **Export Features:**
   - Export search results to JSON/CSV
   - Generate reports

4. **Multi-user Support:**
   - User accounts
   - Saved searches
   - Search history

5. **Integration:**
   - Slack/Discord notifications
   - GitHub issue linking
   - Prometheus metrics

---

## Timeline

**Total estimated time**: 12-17 days (2.5-3.5 weeks)

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Basic Indexing | 3-4 days | 🔄 In Progress |
| Phase 2: Basic Search Server | 3-4 days | ⏳ Pending |
| Phase 3: Hybrid Search + Re-Ranking | 2-3 days | ⏳ Pending |
| Phase 4: Web Interface | 2-3 days | ⏳ Pending |
| Phase 5: Qdrant + Tests | 2-3 days | ⏳ Pending |
| Phase 6: Additional Features | 2-3 days | ⏳ Pending |

---

## References

- **ChromaDB Docs**: https://docs.trychroma.com/
- **Qdrant Docs**: https://qdrant.tech/documentation/
- **LangChain Retrieval**: https://python.langchain.com/docs/modules/data_connection/retrievers/
- **Sentence Transformers**: https://www.sbert.net/
- **Jina Reranker**: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- **FastAPI**: https://fastapi.tiangolo.com/
- **HTMX**: https://htmx.org/

---

**Last Updated**: 2025-11-17
**Author**: Claude (Anthropic)
**Version**: 1.0
