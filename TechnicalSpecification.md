### Technical Specification: Log Extraction & Analysis Pipeline (LEAP)

**Version:** 1.0
**Date:** 16.11.2025
**Author:** Jemma (with contributions from Oleg)

### 1.0 Introduction

**1.1. The Problem**
Engineers (SREs, DevOps, Developers) spend significant time deciphering application logs. A log line like `Operation failed` provides no information about the *business reason* or *technical context* that triggered it. This slows down troubleshooting and increases the Mean Time to Resolution (MTTR).

**1.2. The Solution**
We are creating an automated pipeline, **LEAP**, which solves this problem in three stages:

1.  **Extraction:** 100% reliable parsing of the source code across four languages (Python, Go, Ruby, Node.js/TS) using **native AST parsers** to extract *every* log statement.
2.  **Analysis:** Feeding the extracted data (log string + code context) into an LLM to generate a human-readable analysis of the *reason* for the log.
3.  **Indexing:** Loading the resulting pairs `[Log Template] : [LLM Analysis]` into a vector database (RAG) for instant search.

This TS focuses on the development of **Component 1 (The Extraction CLI)**.

### 2.0 Core Objectives

  * Create a CLI tool (`leap-cli`) that recursively scans a source code directory.
  * Support four languages (Python, Go, Ruby, JavaScript/TypeScript) via a modular parser architecture.
  * Guarantee 100% extraction completeness (determinism).
  * Standardize the output of all parsers into a single **`raw_logs.json`** format.
  * Provide capability for incremental analysis (parsing only changed files).

### 3.0 System Architecture

The pipeline will consist of three independent components:

1.  **`leap-cli` (Extractor):** The main CLI tool (proposed: Python). Its job is to find files and invoke the appropriate "child" AST parser for each language.
2.  **`leap-analyzer` (Analyzer):** A service (or script) that consumes `raw_logs.json`, queries an LLM for each entry, and generates `analyzed_logs.json`.
3.  **`leap-indexer` (Indexer):** A service (or script) that consumes `analyzed_logs.json` and loads the data into a Vector DB (e.g., ChromaDB).

### 4.0 Component 1: `leap-cli` (Extractor)

This is the primary component to be developed.

**4.1. Technology**

  * **Main CLI:** Python (using `argparse` or `typer` for the CLI, `subprocess` for invoking parsers).
  * **Parser 1 (Python):** `ast` (built-in module).
  * **Parser 2 (Go):** `go/parser` and `go/ast` (built-in packages).
  * **Parser 3 (Ruby):** `Ripper` (built-in) or the `parser` gem (recommended for its higher-level API).
  * **Parser 4 (Node):** `acorn` (for JavaScript) and `typescript-compiler-api` (for TypeScript).

**4.2. Execution Flow**

1.  `leap-cli` is invoked with a path to the repository (and/or a list of changed files).
2.  The CLI recursively walks the directory.
3.  Based on the file extension (`.py`, `.go`, `.rb`, `.js`, `.ts`), it calls the corresponding "child" parser:
    ```bash
    python python_parser.py /path/to/service.py
    go_parser /path/to/main.go
    ruby ruby_parser.rb /path/to/user.rb
    ```
4.  Each "child" parser reads the file, builds its AST, and walks the tree.
5.  The parser identifies logger calls (see sec. 4.3).
6.  The parser formats *each* finding into the **Standardized Output Format** (see sec. 5.1) and prints it to `stdout` as a JSON array.
7.  The main `leap-cli` (Python) collects the `stdout` from all child processes and aggregates them into a single master file, `raw_logs.json`.

**4.3. Parser Requirements**
The parsers **must** handle complex cases, not just `log.info("...")`:

  * **Python:** `logger.error(f"...")`, `self.log.exception(...)`, `logging.getLogger(...).warning(...)`.
  * **Go:** `log.Printf(...)`, `log.Fatalf(...)`, and "fluent" APIs like `zerologger.Error().Err(err).Msg("...")`.
  * **Ruby:** `Rails.logger.info "..."`, `logger.warn "..."`.
  * **Node:** `console.error(...)`, `winston.info(...)`, `pino.error(...)`.

The parser *must* extract the log **template** (`log_template`) and the **context** (the entire code block, e.g., function or if-statement, for the LLM).

### 5.0 Data Schemas (The "Contract")

This is the **most critical** part of the TS. These common schemas are the key to success.

**5.1. Schema 1: `raw_logs.json` (Output of `leap-cli`)**
This is a JSON array, where each object is a single log found.

```json
[
  {
    "language": "python",
    "file_path": "src/service.py",
    "line_number": 42,
    "log_level": "error", // (best-effort, if discernible from 'logger.error')
    "log_template": "f\"User {uid} not found\"",
    "code_context": "    if not user:\n        logger.error(f\"User {uid} not found\")\n        return None" // (Context: entire function or if-block)
  },
  {
    "language": "go",
    "file_path": "cmd/main.go",
    "line_number": 226,
    "log_level": "error",
    "log_template": "\"error to run registerer\"",
    "code_context": "    err = registerer_core.NewServiceRunner(...).Run(...)\n    if err != nil {\n        zerologger.Error().Err(err).Msg(\"error to run registerer\")\n        return 1\n    }"
  }
  // ... etc. for Ruby and Node
]
```

**5.2. Schema 2: `analyzed_logs.json` (Output of `leap-analyzer`)**
This JSON will be the "fuel" for the RAG.

```json
[
  {
    "log_template": "f\"User {uid} not found\"",
    "analysis": "This log triggers when a function (e.g., 'get_user') fails to find a user by 'uid' and returns None.",
    "language": "python",
    "source_file": "src/service.py:42"
  },
  {
    "log_template": "\"error to run registerer\"",
    "analysis": "This Error-level log triggers if the main Go 'ServiceRunner' fails to start. This is a critical failure, causing the service to exit with code 1.",
    "language": "go",
    "source_file": "cmd/main.go:226"
  }
]
```

### 6.0 Workflow (CI/CD Integration)

The pipeline must be incremental to avoid re-parsing the entire codebase.

1.  **In CI (on Pull Request / Merge):**
2.  `git diff --name-only main...HEAD > changed_files.txt`
3.  `cat changed_files.txt | xargs leap-cli --files`
4.  (Optional) `leap-analyzer` runs on the `raw_logs.json`, and the LLM analysis can be posted as a *comment on the PR*.
5.  **After merge to `main`:**
6.  `leap-cli` and `leap-analyzer` run on the changed files.
7.  `leap-indexer` updates the Vector DB.

### 7.0 Potential Risks and Challenges

1.  **Parsing Complexity:** Writing AST parsers for "fluent" APIs (like `zerologger`) is non-trivial. It will require a deep analysis of the AST trees for those languages.
2.  **Logger Identification:** In the code, a logger might be named `my_custom_logger`, `lg`, or `app.logger`, not just `log`. The parsers must be "smart" enough to find these (perhaps via import analysis).
3.  **LLM Consistency:** The Analyzer (Stage 2) must have robust JSON validation to ensure "poisoned" (malformed) data from the LLM does not break the RAG index.
