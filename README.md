# LEAP - Log Extraction & Analysis Pipeline

**Version:** 0.1.0

LEAP is a CLI tool and library for extracting log statements from source code across multiple programming languages.

## Features

- **Multi-language support**: Python, Go, Ruby, JavaScript/TypeScript
- **AST-based parsing**: Uses native AST parsers for 100% accurate extraction
- **Standardized output**: Generates `raw_logs.json` in a consistent format
- **Incremental analysis**: Support for parsing only changed files (CI/CD integration)
- **Extensible architecture**: Easy to add new language parsers

## Installation

### From source (development)

```bash
pip install -e .
```

### With development dependencies

```bash
pip install -e ".[dev]"
```

## Quick Start

### Extract logs from a repository

```bash
leap extract /path/to/your/repo
```

### Extract logs from specific language

```bash
leap extract /path/to/repo --language python
```

### Extract logs from specific files (incremental)

```bash
leap extract /path/to/repo --files src/main.py --files src/utils.py
```

### Merge with existing results

```bash
leap extract /path/to/repo --merge --output existing_logs.json
```

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
- ⚠️ **JavaScript/TypeScript**: Basic support for `console.*`, `winston`, `pino` (under development)

## Architecture

LEAP is designed as a pipeline with three independent components:

1. **leap-cli (Extractor)**: Scans source code and extracts log statements → `raw_logs.json`
2. **leap-analyzer (Analyzer)**: Feeds logs to LLM for analysis → `analyzed_logs.json` *(planned)*
3. **leap-indexer (Indexer)**: Loads analyzed logs into vector DB for RAG *(planned)*

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

## Project Structure

```
LEAP/
├── leap/                    # Main package
│   ├── cli.py              # CLI entry point
│   ├── core/               # Core functionality
│   │   ├── discovery.py    # File discovery
│   │   └── aggregator.py   # Result aggregation
│   ├── parsers/            # Language parsers
│   │   ├── base.py         # Base parser interface
│   │   └── python_parser.py
│   ├── schemas/            # Data models
│   │   └── log_entry.py    # Pydantic models
│   └── utils/              # Utilities
│       └── logger.py       # Structured logging
├── tests/                  # Unit tests
├── examples/               # Example files
└── pyproject.toml          # Project configuration
```

## Contributing

Contributions are welcome! Please see the [TechnicalSpecification.md](TechnicalSpecification.md) for detailed architecture and implementation guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Authors

- Jemma & Oleg

## Documentation

- [Technical Specification](TechnicalSpecification.md)
- [Project Guidelines](CLAUDE.md)
