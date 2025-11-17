"""
Main CLI entry point for LEAP (Log Extraction & Analysis Pipeline).

This module provides the command-line interface for the leap-cli tool.
"""

import asyncio
from datetime import UTC
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from leap.analyzer import AnalyzerConfig, LogAnalyzer
from leap.core import aggregate_results, discover_files, filter_changed_files
from leap.indexer import IndexerConfig, LogIndexer, VectorStoreType
from leap.parsers import BaseParser, GoParser, JSParser, PythonParser, RubyParser
from leap.schemas import RawLogEntry
from leap.search_server import SearchServerConfig, create_app
from leap.utils.logger import get_logger

app = typer.Typer(
    name="leap",
    help="Log Extraction & Analysis Pipeline - Extract log statements from source code",
    add_completion=False,
)

console = Console()
logger = get_logger(__name__)


@app.command()
def extract(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to the repository or source directory to scan",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for raw_logs.json",
        ),
    ] = Path("raw_logs.json"),
    files: Annotated[
        list[Path] | None,
        typer.Option(
            "--files",
            "-f",
            help="Process only specific files (for incremental analysis)",
        ),
    ] = None,
    languages: Annotated[
        list[str] | None,
        typer.Option(
            "--language",
            "-l",
            help="Filter by language (python, go, ruby, javascript, typescript)",
        ),
    ] = None,
    merge: Annotated[
        bool,
        typer.Option(
            "--merge",
            "-m",
            help="Merge results with existing output file",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output",
        ),
    ] = False,
) -> None:
    """
    Extract log statements from source code.

    Recursively scans the specified directory, identifies source files,
    and extracts all logging statements using language-specific AST parsers.

    Examples:

        # Extract from entire repository
        leap extract /path/to/repo

        # Extract only Python files
        leap extract /path/to/repo --language python

        # Extract from specific files (incremental)
        leap extract /path/to/repo --files src/main.py --files src/utils.py

        # Merge with existing results
        leap extract /path/to/repo --merge --output existing_logs.json
    """
    try:
        # Convert path to absolute
        root_path = path.resolve()

        console.print("[bold blue]LEAP - Log Extraction & Analysis Pipeline[/bold blue]")
        console.print(f"Scanning: {root_path}")

        # Step 1: Discover files
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Discovering source files...", total=None)

            # Filter by languages if specified
            language_filter: set[Literal["python", "go", "ruby", "javascript", "typescript"]] | None = None
            if languages:
                # Validate and convert language names
                valid_languages = {"python", "go", "ruby", "javascript", "typescript"}
                temp_filter = set()
                for lang in languages:
                    if lang.lower() not in valid_languages:
                        console.print(
                            f"[bold red]Error:[/bold red] Invalid language '{lang}'. "
                            f"Valid options: {', '.join(sorted(valid_languages))}"
                        )
                        raise typer.Exit(1)
                    temp_filter.add(lang.lower())
                # Cast is safe because we've validated all values
                language_filter = cast(set[Literal["python", "go", "ruby", "javascript", "typescript"]], temp_filter)

            discovered = discover_files(root_path, languages=language_filter)

            # Filter by specific files if provided
            if files:
                # Convert file paths to absolute
                file_paths = [f.resolve() for f in files]
                discovered = filter_changed_files(discovered, file_paths)

            progress.update(task, completed=True)

        # Check if any files were found
        total_files = sum(len(file_list) for file_list in discovered.values())
        if total_files == 0:
            console.print("[yellow]No source files found.[/yellow]")
            raise typer.Exit(0)

        console.print(f"Found {total_files} source file(s)")
        for lang, file_list in discovered.items():
            console.print(f"  - {lang}: {len(file_list)} file(s)")

        # Step 2: Parse files
        all_log_entries: list[RawLogEntry] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Parse Python files
            if "python" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['python'])} Python file(s)...", total=None
                )
                python_entries = _parse_files(discovered["python"], PythonParser(), "Python")
                all_log_entries.extend(python_entries)
                progress.update(task, completed=True)

            # Parse Go files
            if "go" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['go'])} Go file(s)...", total=None
                )
                try:
                    go_entries = _parse_files(discovered["go"], GoParser(), "Go")
                    all_log_entries.extend(go_entries)
                    progress.update(task, completed=True)
                except RuntimeError as e:
                    progress.update(task, completed=True)
                    console.print(f"[yellow]Warning: {e}[/yellow]")

            # Parse Ruby files
            if "ruby" in discovered:
                task = progress.add_task(
                    f"Parsing {len(discovered['ruby'])} Ruby file(s)...", total=None
                )
                try:
                    ruby_entries = _parse_files(discovered["ruby"], RubyParser(), "Ruby")
                    all_log_entries.extend(ruby_entries)
                    progress.update(task, completed=True)
                except RuntimeError as e:
                    progress.update(task, completed=True)
                    console.print(f"[yellow]Warning: {e}[/yellow]")

            # Parse JavaScript/TypeScript files
            if "javascript" in discovered or "typescript" in discovered:
                js_files = discovered.get("javascript", [])
                ts_files = discovered.get("typescript", [])
                all_js_files = js_files + ts_files

                task = progress.add_task(
                    f"Parsing {len(all_js_files)} JS/TS file(s)...", total=None
                )
                try:
                    js_entries = _parse_files(all_js_files, JSParser(), "JavaScript/TypeScript")
                    all_log_entries.extend(js_entries)
                    progress.update(task, completed=True)
                except RuntimeError as e:
                    progress.update(task, completed=True)
                    console.print(f"[yellow]Warning: {e}[/yellow]")

        console.print(f"Extracted {len(all_log_entries)} log statement(s)")

        # Step 3: Aggregate and write results
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Writing output...", total=None)

            # Merge with existing file if requested
            if merge and output.exists():
                from leap.core.aggregator import merge_results

                all_log_entries = merge_results(output, all_log_entries)

            aggregate_results(all_log_entries, output)
            progress.update(task, completed=True)

        console.print(f"[bold green]Success![/bold green] Output written to: {output}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        logger.error(f"CLI error: {e}", exc_info=True)
        raise typer.Exit(1) from None


def _parse_files(file_paths: list[Path], parser: BaseParser, language_name: str) -> list[RawLogEntry]:
    """
    Parse files and extract log entries using a given parser.

    Args:
        file_paths: List of file paths to parse
        parser: Parser instance to use
        language_name: Name of the language (for logging)

    Returns:
        List of all extracted log entries
    """
    all_entries: list[RawLogEntry] = []

    for file_path in file_paths:
        try:
            entries = parser.parse_file(file_path)
            all_entries.extend(entries)
        except SyntaxError as e:
            logger.warning(
                f"Skipping {language_name} file with syntax errors: {file_path}",
                extra={"context": {"file": str(file_path), "error": str(e)}},
            )
            continue
        except Exception as e:
            logger.error(
                f"Failed to parse {language_name} file: {file_path}",
                extra={"context": {"file": str(file_path), "error": str(e)}},
            )
            continue

    return all_entries


@app.command()
def analyze(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to raw_logs.json file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output file path for analyzed_logs.json",
        ),
    ] = Path("analyzed_logs.json"),
    provider: Annotated[
        Literal["anthropic", "bedrock", "ollama", "lmstudio"],
        typer.Option(
            "--provider",
            "-p",
            help="LLM provider to use for analysis",
        ),
    ] = "anthropic",
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model name/identifier for the selected provider",
        ),
    ] = "claude-3-5-sonnet-20241022",
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-c",
            help="Maximum number of concurrent LLM requests",
            min=1,
            max=50,
        ),
    ] = 10,
    language: Annotated[
        Literal["en", "ru"],
        typer.Option(
            "--language",
            "-l",
            help="Language for analysis output (en=English, ru=Russian)",
        ),
    ] = "en",
    analysis_prompt: Annotated[
        Path | None,
        typer.Option(
            "--analysis-prompt",
            help="Path to custom analysis prompt template",
            exists=True,
            file_okay=True,
            dir_okay=False,
        ),
    ] = None,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Disable caching for duplicate log entries",
        ),
    ] = False,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            help="Resume from partial results if available (useful after interruption)",
        ),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Request timeout in seconds",
            min=10,
            max=300,
        ),
    ] = 60,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output",
        ),
    ] = False,
) -> None:
    """
    Analyze logs with LLM to generate human-readable explanations.

    Takes raw_logs.json from the extract command and uses an LLM to analyze
    each log statement, generating:
    - Human-readable explanation
    - Severity classification (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Suggested action for operators

    Examples:

        # Basic usage with Anthropic Claude (requires ANTHROPIC_API_KEY)
        leap analyze raw_logs.json

        # Use Ollama locally
        leap analyze raw_logs.json --provider ollama --model llama3:8b

        # Use AWS Bedrock
        leap analyze raw_logs.json --provider bedrock --model anthropic.claude-3-5-sonnet-20241022-v2:0

        # Custom output path and concurrency
        leap analyze raw_logs.json -o my_analysis.json -c 20

        # Russian language analysis
        leap analyze raw_logs.json -l ru

        # Custom prompt template
        leap analyze raw_logs.json --analysis-prompt my_prompt.txt
    """
    try:
        console.print("[bold blue]LEAP - Log Analysis with LLM[/bold blue]")
        console.print(f"Input: {input_file}")
        console.print(f"Provider: {provider}")
        console.print(f"Model: {model}")
        console.print(f"Concurrency: {concurrency}")
        console.print(f"Language: {language}")
        console.print()

        # Create analyzer configuration
        config = AnalyzerConfig.from_env(
            provider=provider,
            model=model,
            concurrency=concurrency,
            language=language,
            analysis_prompt_path=str(analysis_prompt) if analysis_prompt else None,
            enable_cache=not no_cache,
            timeout=timeout,
        )

        # Validate provider configuration
        try:
            config.validate_provider_config()
        except ValueError as e:
            console.print(f"[bold red]Configuration Error:[/bold red] {e}")
            console.print()
            console.print("[yellow]Hint:[/yellow]")

            if provider == "anthropic":
                console.print("  Set ANTHROPIC_API_KEY environment variable")
                console.print("  export ANTHROPIC_API_KEY='sk-ant-...'")
            elif provider == "bedrock":
                console.print("  Configure AWS credentials:")
                console.print("  export AWS_REGION='us-east-1'")
                console.print("  export AWS_PROFILE='your-profile'")
            elif provider == "ollama":
                console.print("  Ensure Ollama is running:")
                console.print("  ollama serve")
            elif provider == "lmstudio":
                console.print("  Ensure LM Studio server is running")

            raise typer.Exit(1) from e

        # Create analyzer
        analyzer = LogAnalyzer(config)

        # Run analysis (async)
        async def run_analysis() -> dict[str, Any]:
            return await analyzer.analyze_file(
                str(input_file.resolve()),
                str(output.resolve()),
                resume=resume
            )

        metadata = asyncio.run(run_analysis())

        # Display results
        console.print()
        console.print("[bold green]Analysis Complete![/bold green]")
        console.print(f"Output written to: {output}")
        console.print()
        console.print("[bold]Statistics:[/bold]")
        console.print(f"  Total entries: {metadata['total_entries']}")
        console.print(f"  Successful: {metadata['successful']} ({metadata['successful']/metadata['total_entries']*100:.1f}%)")
        console.print(f"  Failed: {metadata['failed']} ({metadata['failed']/metadata['total_entries']*100:.1f}%)")

        if config.enable_cache:
            cache_stats = metadata['cache_stats']
            console.print()
            console.print("[bold]Cache Statistics:[/bold]")
            console.print(f"  Hit rate: {cache_stats['hit_rate']:.1f}%")
            console.print(f"  Hits: {cache_stats['hits']}")
            console.print(f"  Misses: {cache_stats['misses']}")
            console.print(f"  Unique entries: {cache_stats['size']}")

        # Display token usage if available
        token_usage = metadata.get('token_usage')
        if token_usage and token_usage['total_tokens'] > 0:
            console.print()
            console.print("[bold]Token Usage:[/bold]")
            console.print(f"  Input tokens: {token_usage['input_tokens']:,}")
            console.print(f"  Output tokens: {token_usage['output_tokens']:,}")
            console.print(f"  Total tokens: {token_usage['total_tokens']:,}")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        logger.error(f"Analysis error: {e}", exc_info=True)
        raise typer.Exit(1) from None


@app.command()
def index(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to analyzed_logs.json file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    codebase: Annotated[
        str,
        typer.Option(
            "--codebase",
            "-c",
            help="Name of the codebase (e.g., 'backend-python')",
        ),
    ],
    vector_store: Annotated[
        Literal["chromadb", "qdrant"],
        typer.Option(
            "--vector-store",
            "-vs",
            help="Vector store to use",
        ),
    ] = "chromadb",
    embedding_model: Annotated[
        str,
        typer.Option(
            "--embedding-model",
            "-em",
            help="Sentence Transformers model name",
        ),
    ] = "paraphrase-multilingual-MiniLM-L12-v2",
    chromadb_path: Annotated[
        Path,
        typer.Option(
            "--chromadb-path",
            help="Path to ChromaDB storage directory",
        ),
    ] = Path(".leap_data/chromadb"),
    qdrant_url: Annotated[
        str,
        typer.Option(
            "--qdrant-url",
            help="Qdrant server URL (for Qdrant vector store)",
        ),
    ] = "http://localhost:6333",
    qdrant_api_key: Annotated[
        str | None,
        typer.Option(
            "--qdrant-api-key",
            help="Qdrant API key (for Qdrant Cloud)",
        ),
    ] = None,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Batch size for embedding generation",
            min=1,
            max=128,
        ),
    ] = 32,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            "-w",
            help="Watch file for changes and auto-reindex",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output",
        ),
    ] = False,
) -> None:
    """
    Index analyzed logs into a vector database for semantic search.

    Takes analyzed_logs.json from the analyze command and indexes it into
    a vector database, separating logs by language (Russian/English).

    Examples:

        # Basic usage with ChromaDB (default)
        leap index analyzed_logs.json --codebase backend-python

        # Use Qdrant
        leap index analyzed_logs.json -c backend-python --vector-store qdrant

        # Custom embedding model
        leap index analyzed_logs.json -c backend-python --embedding-model multilingual-e5-large

        # Custom ChromaDB path
        leap index analyzed_logs.json -c backend-python --chromadb-path /path/to/db
    """
    try:
        console.print("[bold blue]LEAP - Log Indexing[/bold blue]")
        console.print(f"Input: {input_file}")
        console.print(f"Codebase: {codebase}")
        console.print(f"Vector Store: {vector_store}")
        console.print(f"Embedding Model: {embedding_model}")
        console.print()

        # Validate vector store specific settings
        if vector_store == "qdrant":
            console.print(f"Qdrant URL: {qdrant_url}")

        # Create indexer configuration
        config = IndexerConfig(
            vector_store=VectorStoreType(vector_store),
            embedding_model_name=embedding_model,
            chromadb_path=chromadb_path,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
            batch_size=batch_size,
            show_progress=True,
        )

        # Watch mode
        if watch:
            from leap.indexer.watcher import watch_file

            watch_file(
                file_path=input_file.resolve(),
                codebase_name=codebase,
                config=config,
            )
            return

        # Create indexer
        console.print("Loading embedding model...")
        indexer = LogIndexer(config)

        # Index logs
        console.print()
        stats = indexer.index_file(
            input_path=input_file.resolve(),
            codebase_name=codebase,
        )

        # Display results
        console.print()
        console.print("[bold green]Indexing Complete![/bold green]")
        console.print()
        console.print("[bold]Statistics:[/bold]")
        console.print(f"  Total logs: {stats.total_logs}")
        console.print(f"  Russian logs: {stats.ru_logs}")
        console.print(f"  English logs: {stats.en_logs}")
        console.print(f"  Duration: {stats.duration_seconds:.1f}s")
        console.print()
        console.print("[bold]Collections created:[/bold]")
        for collection in stats.collections_created:
            console.print(f"  - {collection}")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        logger.error(f"Indexing error: {e}", exc_info=True)
        raise typer.Exit(1) from None


@app.command()
def serve(
    vector_store: Annotated[
        Literal["chromadb", "qdrant"],
        typer.Option(
            "--vector-store",
            "-vs",
            help="Vector store to use",
        ),
    ] = "chromadb",
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="Server host",
        ),
    ] = "0.0.0.0",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Server port",
        ),
    ] = 8000,
    embedding_model: Annotated[
        str,
        typer.Option(
            "--embedding-model",
            "-em",
            help="Sentence Transformers model name",
        ),
    ] = "paraphrase-multilingual-MiniLM-L12-v2",
    chromadb_path: Annotated[
        Path,
        typer.Option(
            "--chromadb-path",
            help="Path to ChromaDB storage directory",
        ),
    ] = Path(".leap_data/chromadb"),
    qdrant_url: Annotated[
        str,
        typer.Option(
            "--qdrant-url",
            help="Qdrant server URL (for Qdrant vector store)",
        ),
    ] = "http://localhost:6333",
    qdrant_api_key: Annotated[
        str | None,
        typer.Option(
            "--qdrant-api-key",
            help="Qdrant API key (for Qdrant Cloud)",
        ),
    ] = None,
    reload: Annotated[
        bool,
        typer.Option(
            "--reload",
            help="Enable auto-reload on code changes (development)",
        ),
    ] = False,
) -> None:
    """
    Start the LEAP search server.

    Launches a FastAPI server that provides semantic search over indexed logs.

    Examples:

        # Basic usage with ChromaDB
        leap serve

        # Use Qdrant
        leap serve --vector-store qdrant

        # Custom host and port
        leap serve --host localhost --port 9000

        # Development mode with auto-reload
        leap serve --reload
    """
    try:
        console.print("[bold blue]LEAP - Search Server[/bold blue]")
        console.print(f"Vector Store: {vector_store}")
        console.print(f"Embedding Model: {embedding_model}")
        console.print()

        # Create server configuration
        config = SearchServerConfig(
            host=host,
            port=port,
            vector_store=VectorStoreType(vector_store),
            embedding_model_name=embedding_model,
            chromadb_path=chromadb_path,
            qdrant_url=qdrant_url,
            qdrant_api_key=qdrant_api_key,
        )

        # Create FastAPI app
        fastapi_app = create_app(config)

        # Run with uvicorn
        import uvicorn

        console.print("Starting server...")
        console.print()
        console.print(f"🚀 Server will run at http://{host}:{port}")
        console.print(f"   - Web UI: http://{host}:{port}")
        console.print(f"   - API Docs: http://{host}:{port}/docs")
        console.print()
        console.print("Press Ctrl+C to stop")
        console.print()

        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Server error: {e}", exc_info=True)
        raise typer.Exit(1) from None


@app.command(name="test-search")
def test_search(
    victoria_url: Annotated[
        str,
        typer.Option(
            "--victoria-url",
            help="VictoriaLogs API endpoint URL",
        ),
    ],
    query: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="LogsQL query to fetch logs",
        ),
    ],
    search_url: Annotated[
        str,
        typer.Option(
            "--search-url",
            help="LEAP search backend URL",
        ),
    ],
    source_path: Annotated[
        Path,
        typer.Option(
            "--source-path",
            "-s",
            help="Path to source code for ripgrep fallback",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ],
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of logs to test",
            min=1,
            max=10000,
        ),
    ] = 100,
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-c",
            help="Maximum concurrent search requests",
            min=1,
            max=50,
        ),
    ] = 5,
    start_date: Annotated[
        str | None,
        typer.Option(
            "--start-date",
            help="Query start time (RFC3339 format, e.g., 2025-11-17T00:00:00Z)",
        ),
    ] = None,
    end_date: Annotated[
        str | None,
        typer.Option(
            "--end-date",
            help="Query end time (RFC3339 format, e.g., 2025-11-17T23:59:59Z)",
        ),
    ] = None,
    codebase: Annotated[
        str | None,
        typer.Option(
            "--codebase",
            help="Codebase name to filter search results",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="JSON output file path",
        ),
    ] = Path("test_results.json"),
    report: Annotated[
        Path,
        typer.Option(
            "--report",
            "-r",
            help="Markdown report file path",
        ),
    ] = Path("test_report.md"),
    csv_file: Annotated[
        Path,
        typer.Option(
            "--csv",
            help="CSV metrics file path",
        ),
    ] = Path("test_metrics.csv"),
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Request timeout in seconds",
            min=5,
            max=300,
        ),
    ] = 30,
    resume: Annotated[
        bool,
        typer.Option(
            "--resume",
            help="Resume from checkpoint if available",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose debug logging",
        ),
    ] = False,
) -> None:
    """
    Test search quality by comparing VictoriaLogs data against search backend.

    This command validates the LEAP search system by:
    1. Fetching logs from VictoriaLogs
    2. Querying the search backend for each log
    3. Using ripgrep fallback for logs not found
    4. Calculating metrics (hit rate, response time, false negatives)
    5. Generating reports in JSON, Markdown, and CSV formats

    Examples:

        # Basic usage (test 100 logs from today)
        leap test-search \\
          --victoria-url "http://localhost:9428" \\
          --query '_stream:{namespace="app"} AND error' \\
          --search-url "http://localhost:8000" \\
          --source-path "/home/user/my-project"

        # Advanced usage with custom date range
        leap test-search \\
          --victoria-url "http://victoria.example.com:9428" \\
          --query '_stream:{service="api"} AND _msg:~"database|timeout"' \\
          --search-url "http://search.example.com:8000" \\
          --source-path "/workspace/api-service" \\
          --limit 500 \\
          --concurrency 10 \\
          --start-date "2025-11-17T09:00:00Z" \\
          --end-date "2025-11-17T17:00:00Z" \\
          --codebase "backend-python"

        # Resume interrupted test
        leap test-search \\
          --victoria-url "http://localhost:9428" \\
          --query 'error' \\
          --search-url "http://localhost:8000" \\
          --source-path "/home/user/project" \\
          --resume
    """
    import asyncio
    from datetime import datetime

    from leap.search_tester import (
        RipgrepFallback,
        SearchBackendClient,
        SearchTester,
        TestCheckpoint,
        VictoriaLogsClient,
        display_summary,
        generate_csv_output,
        generate_json_output,
        generate_markdown_report,
    )

    try:
        # Parse dates (default to today if not specified)
        if start_date is None:
            start_dt = datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            start_date_str = start_dt.isoformat()
        else:
            start_date_str = start_date

        if end_date is None:
            end_dt = datetime.now(UTC).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            end_date_str = end_dt.isoformat()
        else:
            end_date_str = end_date

        # Display configuration
        console.print("[bold cyan]LEAP - Search Quality Testing[/bold cyan]")
        console.print()
        console.print("[bold]Configuration:[/bold]")
        console.print(f"  VictoriaLogs: {victoria_url}")
        console.print(f"  Search Backend: {search_url}")
        console.print(f"  Query: {query}")
        console.print(f"  Time Range: {start_date_str} - {end_date_str}")
        console.print(f"  Limit: {limit} logs")
        console.print(f"  Concurrency: {concurrency}")
        if codebase:
            console.print(f"  Codebase: {codebase}")
        console.print()

        # Create metadata for outputs
        metadata = {
            "victoria_url": victoria_url,
            "search_url": search_url,
            "query": query,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "limit": limit,
            "concurrency": concurrency,
            "codebase": codebase,
            "source_path": str(source_path),
            "output_file": str(output),
            "report_file": str(report),
            "csv_file": str(csv_file),
        }

        # Main async function
        async def run_test() -> None:
            # Create clients
            victoria_client = VictoriaLogsClient(victoria_url, timeout=timeout)
            search_client = SearchBackendClient(search_url, timeout=timeout)
            ripgrep_fallback = RipgrepFallback(source_path, timeout=10)

            try:
                # Health checks
                console.print("[bold]Checking services...[/bold]")

                victoria_ok = await victoria_client.health_check()
                if not victoria_ok:
                    console.print(
                        "[yellow]⚠️  Warning: VictoriaLogs health check failed[/yellow]"
                    )

                search_ok = await search_client.health_check()
                if not search_ok:
                    console.print(
                        "[yellow]⚠️  Warning: Search backend health check failed[/yellow]"
                    )

                console.print()

                # Check for checkpoint and resume
                checkpoint_file = Path(".leap_test_checkpoint.json")
                checkpoint = None

                if resume and checkpoint_file.exists():
                    try:
                        checkpoint = TestCheckpoint.load(checkpoint_file)
                        console.print(
                            f"[cyan]📂 Resuming from checkpoint: {len(checkpoint)} tests completed[/cyan]"
                        )
                        console.print()
                    except Exception as e:
                        console.print(
                            f"[yellow]⚠️  Failed to load checkpoint: {e}[/yellow]"
                        )
                        checkpoint = None

                # Fetch logs from VictoriaLogs
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "[cyan]Fetching logs from VictoriaLogs...",
                        total=None,
                    )

                    logs = await victoria_client.query_logs(
                        query=query,
                        start=start_date_str,
                        end=end_date_str,
                        limit=limit,
                    )

                    progress.update(task, completed=True)

                if not logs:
                    console.print("[yellow]⚠️  No logs found![/yellow]")
                    return

                console.print(
                    f"[green]✓[/green] Fetched {len(logs)} logs from VictoriaLogs"
                )
                console.print()

                # Filter out already completed logs (if resuming)
                if checkpoint:
                    remaining_logs = [
                        log for i, log in enumerate(logs) if i not in checkpoint
                    ]
                    console.print(
                        f"[cyan]Remaining: {len(remaining_logs)} logs to test[/cyan]"
                    )
                    console.print()
                else:
                    remaining_logs = logs

                # Create tester
                tester = SearchTester(
                    victoria_client=victoria_client,
                    search_client=search_client,
                    ripgrep_fallback=ripgrep_fallback,
                    concurrency=concurrency,
                    codebase=codebase,
                )

                # Run tests
                results, metrics = await tester.run_tests(remaining_logs)

                # Merge with checkpoint results if resuming
                if checkpoint:
                    all_results = []
                    for i, _log in enumerate(logs):
                        if i in checkpoint:
                            result = checkpoint.get_result(i)
                            if result:
                                all_results.append(result)
                        else:
                            # Map back to result
                            idx_in_remaining = len(
                                [j for j in range(i) if j not in checkpoint]
                            )
                            if idx_in_remaining < len(results):
                                all_results.append(results[idx_in_remaining])

                    results = all_results

                    # Recalculate metrics with all results
                    from leap.search_tester.models import TestMetrics

                    metrics = TestMetrics.from_results(
                        results, metrics.total_duration_seconds
                    )

                    # Delete checkpoint on success
                    checkpoint.delete()

                # Display summary
                display_summary(metrics, metadata)

                # Generate outputs
                console.print("[bold]Generating outputs...[/bold]")

                generate_json_output(results, metrics, metadata, output)
                generate_markdown_report(results, metrics, metadata, report)
                generate_csv_output(results, csv_file)

                console.print("[green]✅ All outputs generated successfully![/green]")

            finally:
                await victoria_client.close()
                await search_client.close()

        # Run async function
        asyncio.run(run_test())

    except KeyboardInterrupt:
        console.print()
        console.print("[yellow]⚠️  Test interrupted by user[/yellow]")
        console.print("[cyan]Use --resume to continue from checkpoint[/cyan]")
        raise typer.Exit(0) from None

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        raise typer.Exit(1) from None


@app.command()
def version() -> None:
    """Display version information."""
    console.print("[bold]LEAP CLI[/bold] version 0.1.0")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
