# LEAP Indexer & Search Server - Usage Guide

**Version:** 0.1.0
**Last Updated:** 2025-11-17

This guide provides comprehensive instructions for using the LEAP Indexer and Search Server to index analyzed logs and perform semantic search.

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Indexing Logs](#indexing-logs)
5. [Search Server](#search-server)
6. [Web Interface](#web-interface)
7. [Docker Deployment](#docker-deployment)
8. [Advanced Usage](#advanced-usage)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The LEAP Indexer & Search Server consists of two main components:

- **Indexer** (`leap index`): Indexes analyzed logs into a vector database with multilingual support
- **Search Server** (`leap serve`): Provides semantic search via REST API and web interface

### Key Features

- 🌍 **Multilingual**: Automatic language detection (Russian/English)
- 🔍 **Hybrid Search**: Combines BM25 keyword search with semantic vector search
- 🎯 **Re-ranking**: Uses cross-encoder models for improved result relevance
- 📁 **Multi-project**: Search across multiple codebases
- 🐳 **Docker Ready**: Easy deployment with Docker Compose
- 👁️ **Watch Mode**: Auto-reindex when files change

---

## Installation

### Required Dependencies

Install LEAP with indexer and search dependencies:

```bash
# Install all dependencies
pip install -e ".[all]"

# Or install only indexer dependencies
pip install -e ".[indexer]"

# Or install only search dependencies
pip install -e ".[indexer,search]"
```

### System Requirements

- Python 3.11+
- 2GB+ RAM (for embedding models)
- 500MB+ disk space (for models and data)

### Optional: Docker

For production deployment with Qdrant:

```bash
docker-compose up -d qdrant
```

---

## Quick Start

### 1. Index Your Logs

```bash
# Basic indexing (assumes you have analyzed_logs.json)
leap index analyzed_logs.json --codebase my-project
```

**Output:**
```
LEAP - Log Indexing
Input: analyzed_logs.json
Codebase: my-project
Vector Store: chromadb
Embedding Model: paraphrase-multilingual-MiniLM-L12-v2

Loading embedding model...
✓ Detected 856 Russian logs, 412 English logs
✓ Creating collection: logs_ru_my-project
✓ Indexing Russian logs... ████████████████ 856/856 (100%)
✓ Creating collection: logs_en_my-project
✓ Indexing English logs... ████████████████ 412/412 (100%)

Indexing Complete!

Statistics:
  Total logs: 1268
  Russian logs: 856
  English logs: 412
  Duration: 142.3s

Collections created:
  - logs_ru_my-project
  - logs_en_my-project
```

### 2. Start Search Server

```bash
leap serve
```

**Output:**
```
LEAP - Search Server
Vector Store: chromadb
Embedding Model: paraphrase-multilingual-MiniLM-L12-v2

Loading embedding model...
✓ Embedding model loaded: paraphrase-multilingual-MiniLM-L12-v2
Loading hybrid searcher...
✓ Hybrid searcher initialized
Loading reranker model: jinaai/jina-reranker-v2-base-multilingual...
✓ Reranker model loaded
✓ Vector store connected: chromadb

🚀 Server will run at http://0.0.0.0:8000
   - Web UI: http://0.0.0.0:8000
   - API Docs: http://0.0.0.0:8000/docs

Press Ctrl+C to stop
```

### 3. Open Web Interface

Navigate to http://localhost:8000 in your browser.

---

## Indexing Logs

### Basic Indexing

```bash
leap index analyzed_logs.json --codebase my-project
```

### Indexing Options

```bash
# Use Qdrant instead of ChromaDB
leap index analyzed_logs.json \
  --codebase my-project \
  --vector-store qdrant \
  --qdrant-url http://localhost:6333

# Custom embedding model
leap index analyzed_logs.json \
  --codebase my-project \
  --embedding-model multilingual-e5-large

# Custom ChromaDB path
leap index analyzed_logs.json \
  --codebase my-project \
  --chromadb-path /path/to/db

# Adjust batch size for performance
leap index analyzed_logs.json \
  --codebase my-project \
  --batch-size 64
```

### Watch Mode

Automatically reindex when the file changes:

```bash
leap index analyzed_logs.json \
  --codebase my-project \
  --watch
```

**Output:**
```
LEAP - Watch Mode
Watching: analyzed_logs.json
Codebase: my-project

Performing initial indexing...
✓ Initial Indexing Complete!
  Total logs: 1268
  Russian logs: 856
  English logs: 412
  Duration: 142.3s

Watching for changes... (Press Ctrl+C to stop)

# When file changes:
File changed: analyzed_logs.json
Reindexing...
✓ Reindexing Complete!
  Total logs: 1270
  Russian logs: 857
  English logs: 413
  Duration: 38.2s
```

### Indexing Multiple Codebases

```bash
# Index multiple projects
leap index backend_logs.json --codebase backend-python
leap index frontend_logs.json --codebase frontend-react
leap index ml_logs.json --codebase ml-pipeline

# All will be searchable from the same server
```

---

## Search Server

### Starting the Server

```bash
# Default settings (ChromaDB, port 8000)
leap serve

# Custom port
leap serve --port 9000

# Use Qdrant
leap serve --vector-store qdrant --qdrant-url http://localhost:6333

# Custom host (for Docker/remote access)
leap serve --host 0.0.0.0 --port 8000

# Development mode (auto-reload)
leap serve --reload
```

### API Endpoints

#### 1. Search Logs

**Endpoint:** `POST /api/search`

```bash
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection timeout",
    "top_k": 5,
    "language": "auto"
  }'
```

**Response:**
```json
{
  "results": [
    {
      "id": "abc123...",
      "log_template": "Failed to connect to database",
      "analysis": "This error occurs when the application cannot establish a connection to the database...",
      "severity": "ERROR",
      "source_file": "src/db.py:156",
      "codebase_name": "backend-python",
      "language": "ru",
      "score": 0.94,
      "suggested_action": "Check database credentials and network connectivity",
      "metadata": {...}
    }
  ],
  "total_found": 47,
  "search_time_ms": 234
}
```

**Search with Filters:**
```bash
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "authentication failed",
    "codebase": "backend-python",
    "language": "ru",
    "top_k": 10,
    "filters": {
      "severity": ["ERROR", "CRITICAL"]
    }
  }'
```

#### 2. List Codebases

**Endpoint:** `GET /api/codebases`

```bash
curl "http://localhost:8000/api/codebases"
```

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
    },
    {
      "name": "frontend-react",
      "total_logs": 542,
      "ru_logs": 0,
      "en_logs": 542,
      "last_indexed": "2025-11-17T11:15:00Z"
    }
  ]
}
```

#### 3. Health Check

**Endpoint:** `GET /api/health`

```bash
curl "http://localhost:8000/api/health"
```

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

### Features

1. **Search Input**
   - Natural language queries
   - Real-time search (updates as you type)

2. **Filters**
   - **Codebase**: Filter by specific project
   - **Language**: Auto, Russian, or English
   - **Top K**: Number of results (1-50)
   - **Severity**: DEBUG, INFO, WARNING, ERROR, CRITICAL

3. **Results Display**
   - Severity badges with color coding
   - Source file location (clickable)
   - Similarity score (0-100%)
   - Log template (original code)
   - LLM analysis
   - Suggested action (if available)

### Usage Tips

- **Start broad**: Begin with general queries like "error" or "timeout"
- **Refine with filters**: Use severity and codebase filters to narrow results
- **Natural language**: Write queries as questions: "how to fix database connection?"
- **Multilingual**: Works in both Russian and English automatically

---

## Docker Deployment

### Using Docker Compose

The easiest way to deploy with Qdrant:

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f leap-search

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Services

- **Qdrant**: Vector database (ports 6333, 6334)
- **LEAP Search**: Search server (port 8000)

### Indexing with Docker

```bash
# Index logs (requires analyzed_logs.json in ./data/)
docker-compose exec leap-search leap index /app/data/analyzed_logs.json \
  --codebase backend-python \
  --vector-store qdrant \
  --qdrant-url http://qdrant:6333
```

### Production Deployment

1. **Build custom image** with your data:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install -e ".[all]"

# Pre-index your logs
COPY analyzed_logs.json /app/
RUN leap index analyzed_logs.json --codebase my-project

CMD ["leap", "serve", "--host", "0.0.0.0"]
```

2. **Environment variables**:

```yaml
# docker-compose.yml
services:
  leap-search:
    environment:
      - VECTOR_STORE=qdrant
      - QDRANT_URL=http://qdrant:6333
      - EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

---

## Advanced Usage

### Custom Embedding Models

LEAP supports any Sentence Transformers model:

```bash
# Use a larger model for better accuracy
leap index analyzed_logs.json \
  --codebase my-project \
  --embedding-model sentence-transformers/all-mpnet-base-v2

# Use multilingual model optimized for Russian
leap index analyzed_logs.json \
  --codebase my-project \
  --embedding-model cointegrated/rubert-tiny2
```

### Programmatic Usage

#### Indexing

```python
from pathlib import Path
from leap.indexer import IndexerConfig, LogIndexer, VectorStoreType

# Create configuration
config = IndexerConfig(
    vector_store=VectorStoreType.CHROMADB,
    embedding_model_name="paraphrase-multilingual-MiniLM-L12-v2",
    chromadb_path=Path(".leap_data/chromadb"),
    batch_size=32,
    show_progress=True,
)

# Create indexer
indexer = LogIndexer(config)

# Index logs
stats = indexer.index_file(
    input_path=Path("analyzed_logs.json"),
    codebase_name="my-project",
)

print(f"Indexed {stats.total_logs} logs in {stats.duration_seconds:.1f}s")
```

#### Search Server

```python
from leap.search_server import SearchServerConfig, create_app
import uvicorn

# Create configuration
config = SearchServerConfig(
    host="0.0.0.0",
    port=8000,
    vector_store=VectorStoreType.CHROMADB,
    enable_hybrid_search=True,
    enable_reranking=True,
)

# Create app
app = create_app(config)

# Run server
uvicorn.run(app, host=config.host, port=config.port)
```

### Performance Tuning

#### Indexing Performance

```bash
# Increase batch size for faster indexing (more memory)
leap index analyzed_logs.json --codebase my-project --batch-size 128

# Use GPU if available (requires GPU-enabled PyTorch)
CUDA_VISIBLE_DEVICES=0 leap index analyzed_logs.json --codebase my-project
```

#### Search Performance

- **Disable re-ranking** for faster searches (less accurate):
  ```python
  config = SearchServerConfig(enable_reranking=False)
  ```

- **Use Qdrant** for better performance with large datasets
- **Adjust `top_k`** to retrieve fewer results

---

## Configuration

### Vector Stores

#### ChromaDB (Default)

- **Best for**: Local development, small datasets (<100k documents)
- **Storage**: `.leap_data/chromadb/` (configurable)
- **No external services required**

```bash
leap index analyzed_logs.json \
  --codebase my-project \
  --chromadb-path /custom/path
```

#### Qdrant (Production)

- **Best for**: Production, large datasets (>100k documents)
- **Requires**: Qdrant server (Docker recommended)
- **Better compression and performance**

```bash
# Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Index with Qdrant
leap index analyzed_logs.json \
  --codebase my-project \
  --vector-store qdrant \
  --qdrant-url http://localhost:6333
```

### Embedding Models

Recommended models:

| Model | Dimensions | Languages | Best For |
|-------|-----------|-----------|----------|
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 50+ | Default, balanced |
| `multilingual-e5-large` | 1024 | 100+ | Better accuracy |
| `all-MiniLM-L6-v2` | 384 | English | English-only, faster |
| `cointegrated/rubert-tiny2` | 312 | Russian | Russian-optimized |

### Search Settings

```python
config = SearchServerConfig(
    enable_hybrid_search=True,    # BM25 + Vector (recommended)
    enable_reranking=True,        # Use cross-encoder (slower, more accurate)
    default_top_k=5,              # Default number of results
)
```

---

## Troubleshooting

### Common Issues

#### 1. "Models not loaded" Error

**Problem:** Server returns 503 error with "Models not loaded"

**Solution:**
- Ensure you have enough RAM (2GB+ required)
- Wait for models to load on startup (can take 30-60 seconds)
- Check server logs for errors

#### 2. Slow Indexing

**Problem:** Indexing takes too long

**Solutions:**
```bash
# Increase batch size
leap index analyzed_logs.json --codebase my-project --batch-size 64

# Use GPU (if available)
CUDA_VISIBLE_DEVICES=0 leap index analyzed_logs.json --codebase my-project

# Disable progress bar
leap index analyzed_logs.json --codebase my-project --no-progress
```

#### 3. Qdrant Connection Failed

**Problem:** Cannot connect to Qdrant

**Solutions:**
```bash
# Check if Qdrant is running
curl http://localhost:6333/healthz

# Start Qdrant with Docker
docker run -p 6333:6333 qdrant/qdrant

# Use correct URL in Docker Compose
--qdrant-url http://qdrant:6333  # Inside Docker network
--qdrant-url http://localhost:6333  # From host
```

#### 4. No Results Found

**Problem:** Search returns no results

**Solutions:**
1. Check that logs are indexed:
   ```bash
   curl http://localhost:8000/api/codebases
   ```
2. Try broader queries
3. Remove filters temporarily
4. Check language filter (auto/ru/en)

#### 5. Out of Memory

**Problem:** Process killed due to OOM

**Solutions:**
- Reduce batch size: `--batch-size 16`
- Use smaller embedding model
- Increase system swap space
- Use Docker with memory limits

### Debug Mode

Enable verbose logging:

```bash
# For indexing
leap index analyzed_logs.json --codebase my-project --verbose

# For search server
leap serve --reload  # Shows debug output in development mode
```

---

## Performance Benchmarks

### Indexing Speed (CPU)

| Dataset Size | Time (ChromaDB) | Time (Qdrant) |
|-------------|-----------------|---------------|
| 1,000 logs | ~1 min | ~1 min |
| 10,000 logs | ~10 min | ~9 min |
| 100,000 logs | ~100 min | ~85 min |

### Search Speed

| Operation | Time (avg) |
|-----------|-----------|
| Vector search only | 50-100ms |
| Hybrid search (BM25 + Vector) | 100-200ms |
| With re-ranking | 300-500ms |

*Benchmarks on AMD Ryzen 7, 16GB RAM*

---

## Best Practices

### Indexing

1. **Use watch mode** during development for automatic updates
2. **Organize by codebase** for better search filtering
3. **Index regularly** to keep data fresh
4. **Use Qdrant** for production deployments

### Searching

1. **Start with natural language** queries
2. **Use filters** to narrow results
3. **Adjust top_k** based on needs (5-10 is usually enough)
4. **Enable hybrid search** for best results

### Production

1. **Use Docker Compose** for consistent deployments
2. **Monitor memory usage** (models require ~2GB RAM)
3. **Set up health checks** for availability monitoring
4. **Back up ChromaDB** or Qdrant data regularly

---

## Next Steps

- Explore the [API Documentation](http://localhost:8000/docs) (when server is running)
- Read the [Implementation Plan](INDEXER_AND_SEARCH_PLAN.md) for technical details
- Check [CLAUDE.md](../CLAUDE.md) for coding guidelines
- See [examples/](../examples/) for sample workflows

---

**Questions or Issues?**
Check the main [README.md](../README.md) or open an issue on GitHub.
