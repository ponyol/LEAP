# LEAP Test-Search Command - Design Document

**Created**: 2025-11-17
**Status**: In Development
**Component**: Search Quality Validation Tool

---

## Executive Summary

This document outlines the implementation plan for the `leap test-search` command, a comprehensive tool for validating the quality and relevance of the LEAP search system. The command compares VictoriaLogs data against the LEAP search backend and uses ripgrep as a fallback to identify indexing gaps.

### Key Objectives

- **Validate Search Quality**: Test search backend against real production logs
- **Measure Performance**: Calculate hit rate, response times, and accuracy metrics
- **Identify Gaps**: Find logs that should be indexed but aren't found
- **Generate Reports**: Provide actionable insights through multiple output formats

---

## Architecture Overview

### System Flow

```
┌──────────────────┐
│  VictoriaLogs    │
│  HTTP API        │
└────────┬─────────┘
         │ 1. Fetch logs with LogsQL query
         ↓
┌──────────────────────────────────────────────┐
│  Test-Search Command                         │
│  ┌─────────────────────────────────────────┐ │
│  │ 1. VictoriaLogs Client                  │ │
│  │    - Fetch logs with time range         │ │
│  │    - Parse _msg, _time, _stream         │ │
│  │    - Apply limit                        │ │
│  └─────────────────────────────────────────┘ │
│                    ↓                          │
│  ┌─────────────────────────────────────────┐ │
│  │ 2. Search Backend Client                │ │
│  │    - Send each log to /api/search       │ │
│  │    - Measure response time              │ │
│  │    - Collect results                    │ │
│  └─────────────────────────────────────────┘ │
│                    ↓                          │
│  ┌─────────────────────────────────────────┐ │
│  │ 3. Ripgrep Fallback (if not found)     │ │
│  │    - Extract keywords from log          │ │
│  │    - Search source code with rg         │ │
│  │    - Calculate similarity score         │ │
│  └─────────────────────────────────────────┘ │
│                    ↓                          │
│  ┌─────────────────────────────────────────┐ │
│  │ 4. Metrics & Analytics                  │ │
│  │    - Hit rate calculation               │ │
│  │    - Response time stats                │ │
│  │    - False negative detection           │ │
│  └─────────────────────────────────────────┘ │
│                    ↓                          │
│  ┌─────────────────────────────────────────┐ │
│  │ 5. Output Generation                    │ │
│  │    - JSON (structured data)             │ │
│  │    - Markdown (report)                  │ │
│  │    - CSV (analytics)                    │ │
│  └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
         │
         ↓
┌──────────────────┐
│  Rich Console    │
│  Live Display    │
└──────────────────┘
```

---

## Technology Stack

### Core Libraries

- **httpx**: Async HTTP client for VictoriaLogs and Search API
- **rich**: Terminal UI with progress bars, tables, and colors
- **tenacity**: Retry logic with exponential backoff
- **regex**: Advanced text processing and keyword extraction
- **pydantic**: Configuration and data validation

### Data Processing

- **Keyword Extraction**: Remove dynamic parts (timestamps, IPs, UUIDs, numbers)
- **Fuzzy Matching**: Compare log messages with source code
- **Similarity Scoring**: Levenshtein distance or Jaccard similarity

---

## CLI Interface

### Command Syntax

```bash
leap test-search \
  --victoria-url "http://localhost:9428" \
  --query '_stream:{namespace="ingress-nginx"} AND _msg:~"api/auth"' \
  --search-url "http://localhost:8000" \
  --source-path "/path/to/project" \
  --limit 100 \
  --concurrency 5 \
  --start-date "2025-11-17T00:00:00Z" \
  --end-date "2025-11-17T23:59:59Z" \
  --output results.json \
  --report report.md \
  --csv metrics.csv \
  --resume
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--victoria-url` | URL | *Required* | VictoriaLogs API endpoint |
| `--query` | String | *Required* | LogsQL query to fetch logs |
| `--search-url` | URL | *Required* | LEAP search backend URL |
| `--source-path` | Path | *Required* | Path to source code for ripgrep fallback |
| `--limit` | Integer | `100` | Maximum number of logs to test |
| `--concurrency` | Integer | `5` | Parallel search requests |
| `--start-date` | ISO8601 | Today 00:00 | Query start time (RFC3339) |
| `--end-date` | ISO8601 | Today 23:59 | Query end time (RFC3339) |
| `--output` | Path | `test_results.json` | JSON output file |
| `--report` | Path | `test_report.md` | Markdown report file |
| `--csv` | Path | `test_metrics.csv` | CSV metrics file |
| `--timeout` | Integer | `30` | Request timeout in seconds |
| `--resume` | Boolean | `false` | Resume from checkpoint |
| `--verbose` | Boolean | `false` | Enable debug logging |

### Examples

#### Basic Usage

```bash
# Test with default settings (today's logs, limit 100)
leap test-search \
  --victoria-url "http://localhost:9428" \
  --query '_stream:{namespace="app"} AND error' \
  --search-url "http://localhost:8000" \
  --source-path "/home/user/my-app"
```

#### Advanced Usage

```bash
# Test specific time range with custom output
leap test-search \
  --victoria-url "http://victoria.example.com:9428" \
  --query '_stream:{service="api"} AND _msg:~"database|timeout"' \
  --search-url "http://search.example.com:8000" \
  --source-path "/workspace/api-service" \
  --limit 500 \
  --concurrency 10 \
  --start-date "2025-11-17T09:00:00Z" \
  --end-date "2025-11-17T17:00:00Z" \
  --output results_20251117.json \
  --report report_20251117.md \
  --csv metrics_20251117.csv
```

#### Resume After Interruption

```bash
# Resume previous test
leap test-search \
  --victoria-url "http://localhost:9428" \
  --query '_stream:{app="frontend"}' \
  --search-url "http://localhost:8000" \
  --source-path "/app/frontend" \
  --resume
```

---

## Data Models

### VictoriaLogs Response

```json
{
  "_msg": "Failed to connect to database timeout=30s",
  "_time": "2025-11-17T10:30:45.123Z",
  "_stream": "{namespace=\"backend\",pod=\"api-7d9f8c\",container=\"app\"}",
  "level": "error",
  "source": "db.go:156"
}
```

### LEAP Search Request

```json
{
  "query": "Failed to connect to database timeout",
  "top_k": 5,
  "language": "auto",
  "codebase": "backend-api"
}
```

### LEAP Search Response

```json
{
  "results": [
    {
      "id": "abc123",
      "log_template": "Failed to connect to database",
      "analysis": "This error occurs when...",
      "severity": "ERROR",
      "source_file": "src/db.go:156",
      "score": 0.94,
      "metadata": {...}
    }
  ],
  "total_found": 3,
  "search_time_ms": 234
}
```

### Test Result Schema

```python
@dataclass
class TestResult:
    """Single log test result."""

    # Input data
    log_message: str
    victoria_timestamp: str
    victoria_stream: dict[str, str]

    # Search results
    search_found: bool
    search_response_time_ms: float
    search_results: list[dict] | None
    best_match_score: float | None

    # Ripgrep fallback
    ripgrep_found: bool
    ripgrep_file: str | None
    ripgrep_line: int | None
    ripgrep_match: str | None
    ripgrep_similarity: float | None

    # Classification
    status: Literal["found", "fallback_found", "not_found"]
    is_false_negative: bool  # Found by rg but not by search


@dataclass
class TestMetrics:
    """Aggregated test metrics."""

    total_logs: int

    # Search performance
    found_by_search: int
    found_by_ripgrep_only: int
    not_found: int

    # Rates
    hit_rate: float  # found_by_search / total
    false_negative_rate: float  # found_by_ripgrep_only / total
    miss_rate: float  # not_found / total

    # Timing
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float

    # Search quality
    avg_match_score: float | None
    total_duration_seconds: float
```

---

## Implementation Details

### 1. VictoriaLogs Client

```python
class VictoriaLogsClient:
    """Client for fetching logs from VictoriaLogs."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def query_logs(
        self,
        query: str,
        start: str,
        end: str,
        limit: int,
    ) -> list[VictoriaLog]:
        """
        Fetch logs from VictoriaLogs.

        Args:
            query: LogsQL query string
            start: Start time (RFC3339)
            end: End time (RFC3339)
            limit: Maximum number of logs

        Returns:
            List of VictoriaLog objects
        """
        url = f"{self.base_url}/select/logsql/query"
        params = {
            "query": query,
            "start": start,
            "end": end,
            "limit": limit,
        }

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        # Parse JSONL response (one JSON object per line)
        logs = []
        for line in response.text.strip().split("\n"):
            if line:
                data = json.loads(line)
                logs.append(VictoriaLog.parse_obj(data))

        return logs
```

### 2. Search Backend Client

```python
class SearchBackendClient:
    """Client for LEAP search backend."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        codebase: str | None = None,
    ) -> SearchResponse:
        """
        Search for log in LEAP backend.

        Args:
            query: Log message to search
            top_k: Number of results to return
            codebase: Optional codebase filter

        Returns:
            SearchResponse with results and timing
        """
        url = f"{self.base_url}/api/search"
        payload = {
            "query": query,
            "top_k": top_k,
            "language": "auto",
        }
        if codebase:
            payload["codebase"] = codebase

        start_time = time.time()
        response = await self.client.post(url, json=payload)
        response_time_ms = (time.time() - start_time) * 1000

        response.raise_for_status()
        data = response.json()

        return SearchResponse(
            results=data.get("results", []),
            total_found=data.get("total_found", 0),
            search_time_ms=response_time_ms,
        )
```

### 3. Ripgrep Fallback

```python
class RipgrepFallback:
    """Fallback search using ripgrep in source code."""

    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def extract_keywords(self, log_message: str) -> list[str]:
        """
        Extract searchable keywords from log message.

        Removes:
        - Timestamps (ISO8601, Unix, etc.)
        - IP addresses
        - UUIDs
        - Numbers (unless part of identifier)
        - Special characters

        Returns:
            List of keywords
        """
        # Remove timestamps
        text = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}", "", log_message)
        text = re.sub(r"\d{10,13}", "", text)  # Unix timestamps

        # Remove IPs
        text = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "", text)

        # Remove UUIDs
        text = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Extract words (length > 3)
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text)

        # Return unique keywords (lowercase)
        return list(set(word.lower() for word in words))

    async def search_in_code(
        self,
        keywords: list[str],
        max_results: int = 5,
    ) -> list[RipgrepMatch]:
        """
        Search for keywords in source code using ripgrep.

        Args:
            keywords: List of keywords to search
            max_results: Maximum matches to return

        Returns:
            List of RipgrepMatch objects
        """
        if not keywords:
            return []

        # Build regex pattern: match any keyword
        pattern = "|".join(re.escape(kw) for kw in keywords)

        # Run ripgrep
        cmd = [
            "rg",
            "--json",
            "--ignore-case",
            "--max-count", str(max_results),
            pattern,
            str(self.source_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await proc.communicate()

        # Parse ripgrep JSON output
        matches = []
        for line in stdout.decode().strip().split("\n"):
            if line:
                data = json.loads(line)
                if data.get("type") == "match":
                    matches.append(RipgrepMatch.parse_ripgrep_json(data))

        return matches

    def calculate_similarity(
        self,
        log_message: str,
        code_line: str,
    ) -> float:
        """
        Calculate similarity between log and code.

        Uses Jaccard similarity on word sets.

        Returns:
            Similarity score (0.0 - 1.0)
        """
        log_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", log_message.lower()))
        code_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", code_line.lower()))

        if not log_words or not code_words:
            return 0.0

        intersection = len(log_words & code_words)
        union = len(log_words | code_words)

        return intersection / union if union > 0 else 0.0
```

### 4. Main Test Runner

```python
class SearchTester:
    """Main orchestrator for search testing."""

    def __init__(
        self,
        victoria_client: VictoriaLogsClient,
        search_client: SearchBackendClient,
        ripgrep_fallback: RipgrepFallback,
        concurrency: int = 5,
    ) -> None:
        self.victoria_client = victoria_client
        self.search_client = search_client
        self.ripgrep_fallback = ripgrep_fallback
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

    async def test_single_log(
        self,
        log: VictoriaLog,
        progress: Progress | None = None,
        task_id: Any = None,
    ) -> TestResult:
        """Test a single log entry."""
        async with self.semaphore:
            # 1. Try search backend
            try:
                search_response = await self.search_client.search(
                    query=log.msg,
                    top_k=5,
                )

                if search_response.total_found > 0:
                    # Found by search!
                    return TestResult(
                        log_message=log.msg,
                        victoria_timestamp=log.time,
                        victoria_stream=log.stream,
                        search_found=True,
                        search_response_time_ms=search_response.search_time_ms,
                        search_results=search_response.results,
                        best_match_score=search_response.results[0]["score"],
                        ripgrep_found=False,
                        status="found",
                        is_false_negative=False,
                    )

            except Exception as e:
                logger.warning(f"Search failed for log: {e}")

            # 2. Fallback to ripgrep
            keywords = self.ripgrep_fallback.extract_keywords(log.msg)
            rg_matches = await self.ripgrep_fallback.search_in_code(keywords)

            if rg_matches:
                # Found by ripgrep (potential false negative!)
                best_match = max(
                    rg_matches,
                    key=lambda m: self.ripgrep_fallback.calculate_similarity(
                        log.msg, m.line_text
                    ),
                )
                similarity = self.ripgrep_fallback.calculate_similarity(
                    log.msg, best_match.line_text
                )

                return TestResult(
                    log_message=log.msg,
                    victoria_timestamp=log.time,
                    victoria_stream=log.stream,
                    search_found=False,
                    search_response_time_ms=0.0,
                    search_results=None,
                    best_match_score=None,
                    ripgrep_found=True,
                    ripgrep_file=best_match.file_path,
                    ripgrep_line=best_match.line_number,
                    ripgrep_match=best_match.line_text,
                    ripgrep_similarity=similarity,
                    status="fallback_found",
                    is_false_negative=True,
                )

            # 3. Not found anywhere
            return TestResult(
                log_message=log.msg,
                victoria_timestamp=log.time,
                victoria_stream=log.stream,
                search_found=False,
                search_response_time_ms=0.0,
                search_results=None,
                best_match_score=None,
                ripgrep_found=False,
                status="not_found",
                is_false_negative=False,
            )

            if progress and task_id:
                progress.update(task_id, advance=1)

    async def run_tests(
        self,
        logs: list[VictoriaLog],
    ) -> tuple[list[TestResult], TestMetrics]:
        """Run tests on all logs with rich progress display."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            *Progress.get_default_columns(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Testing logs...",
                total=len(logs),
            )

            # Run tests concurrently
            results = await asyncio.gather(
                *[
                    self.test_single_log(log, progress, task)
                    for log in logs
                ]
            )

        # Calculate metrics
        metrics = self._calculate_metrics(results)

        return results, metrics

    def _calculate_metrics(
        self,
        results: list[TestResult],
    ) -> TestMetrics:
        """Calculate aggregated metrics from results."""
        total = len(results)
        found_by_search = sum(1 for r in results if r.search_found)
        found_by_ripgrep_only = sum(1 for r in results if r.is_false_negative)
        not_found = sum(1 for r in results if r.status == "not_found")

        response_times = [
            r.search_response_time_ms
            for r in results
            if r.search_found
        ]

        match_scores = [
            r.best_match_score
            for r in results
            if r.best_match_score is not None
        ]

        return TestMetrics(
            total_logs=total,
            found_by_search=found_by_search,
            found_by_ripgrep_only=found_by_ripgrep_only,
            not_found=not_found,
            hit_rate=found_by_search / total if total > 0 else 0.0,
            false_negative_rate=found_by_ripgrep_only / total if total > 0 else 0.0,
            miss_rate=not_found / total if total > 0 else 0.0,
            avg_response_time_ms=statistics.mean(response_times) if response_times else 0.0,
            min_response_time_ms=min(response_times) if response_times else 0.0,
            max_response_time_ms=max(response_times) if response_times else 0.0,
            p50_response_time_ms=statistics.median(response_times) if response_times else 0.0,
            p95_response_time_ms=self._percentile(response_times, 0.95) if response_times else 0.0,
            p99_response_time_ms=self._percentile(response_times, 0.99) if response_times else 0.0,
            avg_match_score=statistics.mean(match_scores) if match_scores else None,
            total_duration_seconds=0.0,  # Set by caller
        )
```

### 5. Output Generators

#### JSON Output

```json
{
  "metadata": {
    "test_date": "2025-11-17T10:30:00Z",
    "victoria_url": "http://localhost:9428",
    "search_url": "http://localhost:8000",
    "query": "_stream:{namespace=\"app\"} AND error",
    "limit": 100,
    "duration_seconds": 45.2
  },
  "metrics": {
    "total_logs": 100,
    "found_by_search": 87,
    "found_by_ripgrep_only": 10,
    "not_found": 3,
    "hit_rate": 0.87,
    "false_negative_rate": 0.10,
    "miss_rate": 0.03,
    "avg_response_time_ms": 234.5,
    "p50_response_time_ms": 220.0,
    "p95_response_time_ms": 450.0,
    "p99_response_time_ms": 580.0,
    "avg_match_score": 0.91
  },
  "results": [
    {
      "log_message": "Failed to connect to database",
      "status": "found",
      "search_found": true,
      "search_response_time_ms": 234,
      "best_match_score": 0.94,
      "is_false_negative": false
    }
  ]
}
```

#### Markdown Report

````markdown
# LEAP Search Quality Report

**Generated**: 2025-11-17 10:30:00 UTC
**Duration**: 45.2 seconds

---

## Summary

| Metric | Value |
|--------|-------|
| Total Logs Tested | 100 |
| ✅ Found by Search | 87 (87.0%) |
| ⚠️ Found by Ripgrep Only | 10 (10.0%) |
| ❌ Not Found | 3 (3.0%) |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Average Response Time | 234.5ms |
| Median Response Time (P50) | 220.0ms |
| 95th Percentile (P95) | 450.0ms |
| 99th Percentile (P99) | 580.0ms |

## Search Quality

- **Hit Rate**: 87.0% ✅
- **False Negative Rate**: 10.0% ⚠️
- **Average Match Score**: 0.91

---

## False Negatives (Found by Ripgrep, not Search)

These logs exist in source code but weren't found by the search system:

### 1. "Failed to connect to database timeout=30s"

- **File**: `src/db.go:156`
- **Similarity**: 0.85
- **Action**: ⚠️ This log should be indexed

### 2. "User authentication failed"

- **File**: `src/auth.py:89`
- **Similarity**: 0.92
- **Action**: ⚠️ This log should be indexed

---

## Not Found Anywhere

These logs weren't found in search or source code:

1. "Temporary log message for debugging"
2. "Test log entry"

---

## Recommendations

1. **Index missing logs**: 10 logs found by ripgrep should be added to the index
2. **Investigate P99 latency**: 99th percentile response time is 580ms (consider optimization)
3. **Review not-found logs**: 3 logs might be dynamic or removed from codebase
````

#### CSV Output

```csv
log_message,status,search_found,search_response_time_ms,best_match_score,ripgrep_found,ripgrep_file,ripgrep_similarity,is_false_negative
"Failed to connect to database",found,true,234,0.94,false,,,false
"User authentication failed",fallback_found,false,0,,true,src/auth.py:89,0.92,true
"Temporary log message",not_found,false,0,,false,,,false
```

---

## Rich Console Display

### Live Progress Display

```
╭─────────────────────────────────────────────────────────────╮
│  LEAP - Search Quality Testing                             │
├─────────────────────────────────────────────────────────────┤
│  VictoriaLogs: http://localhost:9428                        │
│  Search Backend: http://localhost:8000                      │
│  Query: _stream:{namespace="app"} AND error                 │
│  Time Range: 2025-11-17 00:00:00 - 2025-11-17 23:59:59    │
│  Limit: 100 logs                                           │
╰─────────────────────────────────────────────────────────────╯

⠋ Fetching logs from VictoriaLogs... Done! (100 logs in 1.2s)

⠹ Testing logs... ━━━━━━━━━━━━━━━━━━━━━━━━━━ 45/100 (45%)

╭─────────────────────────────────────────────────────────────╮
│  Live Statistics                                            │
├─────────────────────────────────────────────────────────────┤
│  Tested: 45/100                                             │
│  ✅ Found by Search: 39 (86.7%)                            │
│  ⚠️  Found by Ripgrep: 5 (11.1%)                           │
│  ❌ Not Found: 1 (2.2%)                                    │
│  Avg Response Time: 240ms                                   │
╰─────────────────────────────────────────────────────────────╯
```

### Final Results Display

```
╭─────────────────────────────────────────────────────────────╮
│  Test Complete! ✅                                         │
├─────────────────────────────────────────────────────────────┤
│  Total Duration: 45.2s                                      │
│  Total Logs: 100                                            │
│                                                             │
│  Results:                                                   │
│  ✅ Found by Search:     87 (87.0%)                        │
│  ⚠️  Found by Ripgrep:   10 (10.0%)                        │
│  ❌ Not Found:           3 (3.0%)                          │
│                                                             │
│  Performance:                                               │
│  Avg Response Time: 234.5ms                                 │
│  P50: 220.0ms  P95: 450.0ms  P99: 580.0ms                  │
│                                                             │
│  Quality:                                                   │
│  Hit Rate: 87.0% ✅                                        │
│  False Negative Rate: 10.0% ⚠️                             │
│  Avg Match Score: 0.91                                      │
╰─────────────────────────────────────────────────────────────╯

📁 Outputs Generated:
  - JSON: test_results.json
  - Report: test_report.md
  - CSV: test_metrics.csv
```

---

## Advanced Features

### 1. Resume Capability

```python
class TestCheckpoint:
    """Checkpoint for resuming interrupted tests."""

    checkpoint_file: Path
    completed_indices: set[int]
    partial_results: list[TestResult]

    def save(self) -> None:
        """Save checkpoint to disk."""
        with open(self.checkpoint_file, "w") as f:
            json.dump({
                "completed_indices": list(self.completed_indices),
                "partial_results": [r.dict() for r in self.partial_results],
            }, f)

    @classmethod
    def load(cls, checkpoint_file: Path) -> "TestCheckpoint":
        """Load checkpoint from disk."""
        with open(checkpoint_file) as f:
            data = json.load(f)
        return cls(
            checkpoint_file=checkpoint_file,
            completed_indices=set(data["completed_indices"]),
            partial_results=[
                TestResult(**r) for r in data["partial_results"]
            ],
        )
```

### 2. Retry Logic with Exponential Backoff

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

class SearchBackendClient:
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        stop=stop_after_attempt(4),
    )
    async def search(self, query: str, **kwargs) -> SearchResponse:
        """Search with automatic retry on network errors."""
        # ... implementation
```

### 3. Intelligent Keyword Extraction

```python
def extract_keywords(self, log_message: str) -> list[str]:
    """Extract searchable keywords with advanced heuristics."""

    # 1. Remove common dynamic patterns
    text = log_message
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?Z?", "", text)
    text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "", text)
    text = re.sub(r"\b[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", "", text, flags=re.I)

    # 2. Extract words and preserve common patterns
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text)

    # 3. Filter stopwords
    stopwords = {"the", "and", "for", "with", "from", "this", "that"}
    keywords = [w for w in words if len(w) >= 3 and w.lower() not in stopwords]

    # 4. Add common programming patterns
    patterns = re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+)+", log_message)  # CamelCase
    patterns += re.findall(r"[a-z]+_[a-z_]+", log_message)  # snake_case

    return list(set(keywords + patterns))
```

---

## Error Handling

### Graceful Degradation

```python
async def test_single_log(self, log: VictoriaLog) -> TestResult:
    """Test with comprehensive error handling."""

    # 1. Try search backend
    try:
        search_response = await self.search_client.search(log.msg)
        if search_response.total_found > 0:
            return TestResult(status="found", ...)
    except httpx.TimeoutException:
        logger.warning(f"Search timeout for log: {log.msg[:50]}")
    except httpx.HTTPError as e:
        logger.error(f"Search HTTP error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected search error: {e}")

    # 2. Fallback to ripgrep (always try, even if search failed)
    try:
        keywords = self.ripgrep_fallback.extract_keywords(log.msg)
        matches = await self.ripgrep_fallback.search_in_code(keywords)
        if matches:
            return TestResult(status="fallback_found", ...)
    except Exception as e:
        logger.exception(f"Ripgrep error: {e}")

    # 3. Not found (no error, legitimate outcome)
    return TestResult(status="not_found", ...)
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_search_tester.py

async def test_victoria_logs_client():
    """Test VictoriaLogs client can fetch logs."""
    client = VictoriaLogsClient("http://localhost:9428")
    logs = await client.query_logs(
        query="error",
        start="2025-11-17T00:00:00Z",
        end="2025-11-17T23:59:59Z",
        limit=10,
    )
    assert len(logs) <= 10
    assert all(isinstance(log, VictoriaLog) for log in logs)


async def test_search_backend_client():
    """Test search backend client."""
    client = SearchBackendClient("http://localhost:8000")
    response = await client.search("database error", top_k=5)
    assert isinstance(response, SearchResponse)
    assert response.total_found >= 0


def test_keyword_extraction():
    """Test keyword extraction from log messages."""
    fallback = RipgrepFallback(Path("/app"))

    log = "2025-11-17 10:30:00 Failed to connect to database timeout=30s"
    keywords = fallback.extract_keywords(log)

    assert "failed" in keywords
    assert "connect" in keywords
    assert "database" in keywords
    assert "timeout" in keywords
    assert "2025" not in keywords  # Timestamp removed
```

### Integration Tests

```python
async def test_end_to_end():
    """Test complete workflow."""
    # Setup
    victoria_client = VictoriaLogsClient("http://localhost:9428")
    search_client = SearchBackendClient("http://localhost:8000")
    ripgrep = RipgrepFallback(Path("/workspace/test-project"))

    tester = SearchTester(victoria_client, search_client, ripgrep)

    # Fetch logs
    logs = await victoria_client.query_logs(
        query="error",
        start="2025-11-17T00:00:00Z",
        end="2025-11-17T23:59:59Z",
        limit=10,
    )

    # Run tests
    results, metrics = await tester.run_tests(logs)

    # Assertions
    assert len(results) == len(logs)
    assert metrics.total_logs == len(logs)
    assert 0.0 <= metrics.hit_rate <= 1.0
    assert metrics.avg_response_time_ms >= 0
```

---

## Dependencies

### New Dependencies to Add

```toml
[tool.poetry.dependencies]
# HTTP client
httpx = "^0.27.2"

# Retry logic
tenacity = "^9.0.0"

# Rich console output (already in project)
rich = "^13.9.4"

# Existing dependencies (already in project)
pydantic = "^2.11.0"
```

---

## Performance Considerations

### Concurrency Optimization

- **Default concurrency**: 5 (safe for most backends)
- **Maximum recommended**: 20 (to avoid overwhelming services)
- **Adaptive concurrency**: Could implement based on response times

### Memory Management

- **Streaming results**: Process logs one at a time
- **Checkpoint frequency**: Save every 10 logs
- **Result batching**: Write outputs in batches to reduce I/O

### Network Optimization

- **Connection pooling**: httpx AsyncClient reuses connections
- **Timeout strategy**:
  - VictoriaLogs: 30s (large queries can be slow)
  - Search backend: 30s (model inference time)
  - Ripgrep: 10s (should be fast)

---

## Timeline

**Estimated Implementation Time**: 2-3 days

| Task | Duration | Status |
|------|----------|--------|
| Data models and clients | 4 hours | 🔄 |
| Core testing logic | 4 hours | ⏳ |
| Ripgrep fallback | 3 hours | ⏳ |
| Rich UI and progress | 3 hours | ⏳ |
| Output generators | 3 hours | ⏳ |
| Resume capability | 2 hours | ⏳ |
| Tests and documentation | 3 hours | ⏳ |

---

## Success Criteria

1. ✅ Successfully fetch logs from VictoriaLogs
2. ✅ Query LEAP search backend for each log
3. ✅ Fallback to ripgrep when search fails
4. ✅ Calculate accurate metrics (hit rate, response times)
5. ✅ Generate JSON, Markdown, and CSV outputs
6. ✅ Display live progress with Rich
7. ✅ Resume capability works after interruption
8. ✅ All tests pass: `pytest tests/test_search_tester.py`

---

## Future Enhancements

### Phase 2 Features

1. **Batch Search API**: Send multiple logs in one request
2. **Caching**: Cache search results to avoid duplicate queries
3. **Parallel ripgrep**: Run multiple rg processes for faster fallback
4. **ML-based similarity**: Use embeddings for better similarity scoring
5. **Historical tracking**: Track search quality over time
6. **Alerting**: Send alerts when hit rate drops below threshold
7. **A/B testing**: Compare different search configurations

---

## References

- **VictoriaLogs Docs**: https://docs.victoriametrics.com/victorialogs/
- **VictoriaLogs Query API**: https://docs.victoriametrics.com/victorialogs/querying/
- **LEAP Search API**: [INDEXER_SEARCH_USAGE.md](INDEXER_SEARCH_USAGE.md)
- **httpx Docs**: https://www.python-httpx.org/
- **tenacity Docs**: https://tenacity.readthedocs.io/
- **Rich Progress**: https://rich.readthedocs.io/en/stable/progress.html

---

**Last Updated**: 2025-11-17
**Author**: Claude (Anthropic) + ponyol
**Version**: 1.0
