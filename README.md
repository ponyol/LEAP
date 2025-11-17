# LEAP - Log Extraction & Analysis Pipeline

**Version:** 0.1.0

LEAP is a complete log management pipeline that extracts log statements from source code, analyzes them with LLMs, and provides semantic search capabilities.

## Features

### 🔍 Log Extraction
- **Multi-language support**: Python, Go, Ruby, JavaScript/TypeScript
- **AST-based parsing**: Uses native AST parsers for 100% accurate extraction
- **Standardized output**: Generates `raw_logs.json` in a consistent format
- **Incremental analysis**: Support for parsing only changed files (CI/CD integration)
- **Extensible architecture**: Easy to add new language parsers

### 🤖 LLM Analysis
- **Multi-provider support**: Anthropic Claude, AWS Bedrock, Ollama, LM Studio
- **Intelligent analysis**: Explains log purpose, severity, and suggested actions
- **Multilingual**: Analysis in English or Russian
- **Resume capability**: Continue from partial results after interruption
- **Token tracking**: Monitor usage across all providers

### 📊 Semantic Search
- **Hybrid search**: Combines BM25 keyword search with semantic vector search
- **Multilingual indexing**: Automatic language detection (Russian/English)
- **Re-ranking**: Cross-encoder models for improved relevance
- **Multi-project support**: Search across multiple codebases
- **Web interface**: Interactive UI with filters and real-time search
- **REST API**: Programmatic access with OpenAPI documentation

## Installation

### From source (development)

```bash
# Install base package
pip install -e .

# Install with all features
pip install -e ".[all]"

# Install specific components
pip install -e ".[analyzer]"  # LLM analysis only
pip install -e ".[indexer]"   # Indexing only
pip install -e ".[search]"    # Search server only
```

### With development dependencies

```bash
pip install -e ".[dev]"
```

### JavaScript/TypeScript Parser Dependencies

If you plan to parse JavaScript or TypeScript files, you need to install Node.js dependencies:

```bash
cd leap/parsers/js_parser
npm install
cd ../../..
```

**Requirements:**
- Node.js >= 18.0.0
- npm or yarn

## Quick Start

LEAP consists of three main commands that form a complete pipeline:

### 1. Extract Logs from Source Code

```bash
# Extract from entire repository
leap extract /path/to/your/repo

# Extract from specific language
leap extract /path/to/repo --language python

# Extract from specific files (incremental)
leap extract /path/to/repo --files src/main.py --files src/utils.py
```

**Output:** `raw_logs.json` (log statements from your codebase)

### 2. Analyze Logs with LLM

```bash
# Analyze with Anthropic Claude (requires ANTHROPIC_API_KEY)
leap analyze raw_logs.json

# Use local Ollama
leap analyze raw_logs.json --provider ollama --model llama3:8b

# Russian language analysis
leap analyze raw_logs.json --language ru
```

**Output:** `analyzed_logs.json` (logs with LLM-generated explanations)

### 3. Index & Search Logs

```bash
# Index analyzed logs
leap index analyzed_logs.json --codebase my-project

# Start search server
leap serve

# Open http://localhost:8000 in your browser
```

**Result:** Semantic search interface for your logs!

## Output Format

LEAP generates a `raw_logs.json` file with the following structure:

```json
[
  {
    "language": "python",
    "file_path": "src/service.py",
    "line_number": 42,
    "log_level": "error",
    "log_template": "f\"User {uid} not found\"",
    "code_context": "    if not user:\n        logger.error(f\"User {uid} not found\")\n        return None"
  }
]
```

## Supported Languages

### Currently Implemented
- ✅ **Python**: Full support for `logging`, `logger`, and custom logger instances
- ✅ **Go**: Support for `log.*` (Printf, Fatalf, etc.), `zerolog`, and structured logging libraries
- ✅ **Ruby**: Support for `Logger`, `@logger`, `Rails.logger`
- ✅ **JavaScript/TypeScript**: Support for `console.*`, `winston`, `pino`, and other structured loggers (requires Node.js dependencies, see Installation)

## Architecture

LEAP is designed as a pipeline with three independent components:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. Extractor   │────▶│  2. Analyzer    │────▶│  3. Indexer     │
│                 │     │                 │     │   & Search      │
│  Source Code    │     │  LLM Analysis   │     │                 │
│  ──────────▶    │     │  ──────────▶    │     │  Vector DB      │
│  raw_logs.json  │     │  analyzed_      │     │  ──────────▶    │
│                 │     │  logs.json      │     │  Semantic       │
│                 │     │                 │     │  Search         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Component 1: Log Extractor
- Scans source code using AST parsers
- Extracts log statements with context
- Outputs `raw_logs.json`

### Component 2: Log Analyzer
- Sends logs to LLM for analysis
- Generates explanations, severity, and actions
- Outputs `analyzed_logs.json`
- **[Documentation](docs/ANALYZER_USAGE.md)**

### Component 3: Indexer & Search
- Indexes logs into vector database
- Provides semantic search via API/UI
- Hybrid search (BM25 + Vector) with re-ranking
- **[Documentation](docs/INDEXER_SEARCH_USAGE.md)**

## Development

### Running tests

```bash
pytest
```

### Type checking

```bash
mypy leap
```

### Linting

```bash
ruff check leap
```

## CI/CD Integration

LEAP supports incremental analysis for efficient CI/CD integration:

```bash
# In your CI pipeline
git diff --name-only main...HEAD > changed_files.txt
cat changed_files.txt | xargs leap extract --files
```

## Docker Deployment

### Quick Start with Docker Compose

```bash
# Start Qdrant + Search Server
docker-compose up -d

# Index your logs
docker-compose exec leap-search leap index /app/data/analyzed_logs.json \
  --codebase my-project

# Access UI at http://localhost:8000
```

### Services

- **Qdrant**: Vector database (ports 6333, 6334)
- **LEAP Search**: Search server (port 8000)

See [docs/INDEXER_SEARCH_USAGE.md](docs/INDEXER_SEARCH_USAGE.md) for detailed Docker instructions.

## Web Interface

The search server provides an interactive web interface with:

- **Natural language search**: Query in plain English or Russian
- **Real-time results**: Updates as you type
- **Advanced filters**: By codebase, language, severity
- **Similarity scores**: See how relevant each result is
- **Suggested actions**: LLM-generated recommendations

**Access:** http://localhost:8000 (after running `leap serve`)

## API Documentation

When the search server is running, OpenAPI documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

**Example API Call:**

```bash
curl -X POST "http://localhost:8000/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "database connection timeout",
    "codebase": "backend-python",
    "top_k": 5
  }'
```

## Project Structure

```
LEAP/
├── leap/                        # Main package
│   ├── cli.py                  # CLI entry point
│   ├── core/                   # Core functionality
│   │   ├── discovery.py        # File discovery
│   │   └── aggregator.py       # Result aggregation
│   ├── parsers/                # Language parsers
│   │   ├── base.py            # Base parser interface
│   │   ├── python_parser.py   # Python AST parser
│   │   ├── go_parser.py       # Go AST parser
│   │   ├── ruby_parser.py     # Ruby AST parser
│   │   └── js_parser/         # JS/TS parser (Node.js)
│   ├── analyzer/               # LLM analysis
│   │   ├── analyzer.py        # Main analyzer
│   │   └── providers/         # LLM provider implementations
│   ├── indexer/               # Log indexing
│   │   ├── embeddings/        # Embedding providers
│   │   ├── vector_stores/     # Vector DB implementations
│   │   └── watcher.py         # File watching
│   ├── search_server/         # Search server
│   │   ├── api/              # REST API endpoints
│   │   ├── retrieval/        # Hybrid search + re-ranking
│   │   └── ui/               # Web interface
│   ├── schemas/              # Data models
│   └── utils/                # Utilities
├── tests/                     # Unit tests
├── docs/                      # Documentation
├── examples/                  # Example files
└── pyproject.toml            # Project configuration
```

## Contributing

Contributions are welcome! Please see the [TechnicalSpecification.md](TechnicalSpecification.md) for detailed architecture and implementation guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Authors

- Jemma & Oleg

## Documentation

- **[Technical Specification](TechnicalSpecification.md)** - Detailed architecture
- **[Project Guidelines](CLAUDE.md)** - Coding standards
- **[Analyzer Usage](docs/ANALYZER_USAGE.md)** - LLM analysis guide
- **[Indexer & Search Usage](docs/INDEXER_SEARCH_USAGE.md)** - Semantic search guide
- **[Implementation Plans](docs/)** - Component design documents
