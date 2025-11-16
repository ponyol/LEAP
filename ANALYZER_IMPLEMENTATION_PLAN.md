# LEAP Analyzer - LLM Component Implementation Plan

**Version:** 1.0
**Date:** 2025-11-16
**Status:** Ready for Implementation

---

## 1. Executive Summary

This document outlines the implementation plan for the **leap-analyzer** LLM component, which will analyze log statements extracted by **leap-cli** and generate human-readable explanations with additional metadata (severity, suggested_action).

### Key Requirements

- **Multi-provider support:** Anthropic Claude, Amazon Bedrock, Ollama, LMStudio
- **Configuration:** Environment variables + CLI arguments
- **Output language:** English (default), Russian (optional via CLI)
- **Concurrency:** Configurable via CLI for batch processing
- **Output fields:** analysis, severity, suggested_action
- **Prompt customization:** External prompt files for easy testing/tuning

---

## 2. Architecture Overview

```
┌─────────────────┐
│   leap-cli      │
│  (Component 1)  │
└────────┬────────┘
         │ raw_logs.json
         ▼
┌─────────────────────────────────────────┐
│         leap-analyzer                   │
│  ┌─────────────────────────────────┐   │
│  │  CLI Interface (cli.py)         │   │
│  └──────────────┬──────────────────┘   │
│                 ▼                       │
│  ┌─────────────────────────────────┐   │
│  │  Analyzer Core (analyzer.py)    │   │
│  │  - Load raw_logs.json           │   │
│  │  - Batch processing             │   │
│  │  - Error handling + validation  │   │
│  └──────────────┬──────────────────┘   │
│                 ▼                       │
│  ┌─────────────────────────────────┐   │
│  │  LLM Providers (providers/)     │   │
│  │  - Anthropic                    │   │
│  │  - Bedrock                      │   │
│  │  - Ollama                       │   │
│  │  - LMStudio                     │   │
│  └──────────────┬──────────────────┘   │
│                 ▼                       │
│  ┌─────────────────────────────────┐   │
│  │  Validators (validators.py)     │   │
│  │  - JSON schema validation       │   │
│  │  - Fallback handling            │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
         │ analyzed_logs.json
         ▼
┌─────────────────┐
│   RAG Index     │
│  (Component 3)  │
└─────────────────┘
```

---

## 3. Directory Structure

```
leap/
├── analyzer/
│   ├── __init__.py              # Public API exports
│   ├── analyzer.py              # Core analysis logic
│   ├── config.py                # Configuration management
│   ├── batch_processor.py       # Async batch processing with concurrency
│   ├── validators.py            # JSON response validation
│   │
│   └── providers/
│       ├── __init__.py          # Provider factory
│       ├── base.py              # Abstract base provider
│       ├── anthropic.py         # Anthropic Claude implementation
│       ├── bedrock.py           # Amazon Bedrock implementation
│       ├── ollama.py            # Ollama local implementation
│       └── lmstudio.py          # LMStudio local implementation
│
├── prompts/                     # External prompt templates
│   ├── analysis_en.txt          # English analysis prompt
│   ├── analysis_ru.txt          # Russian analysis prompt
│   ├── severity_en.txt          # English severity classification
│   ├── severity_ru.txt          # Russian severity classification
│   ├── suggested_action_en.txt  # English suggested action
│   └── suggested_action_ru.txt  # Russian suggested action
│
└── cli.py                       # Extended with 'analyze' command
```

---

## 4. Module Specifications

### 4.1 `analyzer/config.py`

**Purpose:** Centralized configuration management for analyzer

```python
from pydantic import BaseModel, Field
from typing import Literal

class AnalyzerConfig(BaseModel):
    """Configuration for LEAP Analyzer"""

    # LLM Provider
    provider: Literal["anthropic", "bedrock", "ollama", "lmstudio"] = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"

    # API Configuration
    api_key: str | None = None  # From env: ANTHROPIC_API_KEY, etc.
    api_base: str | None = None  # For Ollama/LMStudio: http://localhost:11434

    # AWS Bedrock specific
    aws_region: str | None = None
    aws_profile: str | None = None

    # Processing
    concurrency: int = Field(default=10, ge=1, le=50)
    max_retries: int = Field(default=3, ge=1, le=10)
    timeout: int = Field(default=60, ge=10, le=300)

    # Output
    language: Literal["en", "ru"] = "en"

    # Prompts (paths to custom prompt files)
    analysis_prompt_path: str | None = None
    severity_prompt_path: str | None = None
    action_prompt_path: str | None = None

    @classmethod
    def from_env(cls, **overrides) -> "AnalyzerConfig":
        """Load config from environment variables + CLI overrides"""
        pass
```

---

### 4.2 `analyzer/providers/base.py`

**Purpose:** Abstract interface for all LLM providers

```python
from abc import ABC, abstractmethod
from typing import Any

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs
    ) -> str:
        """
        Generate completion from LLM

        Returns:
            Raw text response from the model

        Raises:
            ProviderError: On API errors
            TimeoutError: On timeout
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available and configured correctly"""
        pass
```

---

### 4.3 `analyzer/providers/anthropic.py`

**Implementation:**

```python
import os
from anthropic import AsyncAnthropic
from .base import LLMProvider

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        self.client = AsyncAnthropic(api_key=self.api_key)

    async def complete(
        self,
        prompt: str,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs
    ) -> str:
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def health_check(self) -> bool:
        try:
            await self.complete("Test", max_tokens=10)
            return True
        except Exception:
            return False
```

**Similar implementations for:**
- `bedrock.py` (boto3 async client)
- `ollama.py` (httpx to http://localhost:11434/api/generate)
- `lmstudio.py` (httpx to http://localhost:1234/v1/chat/completions)

---

### 4.4 `analyzer/validators.py`

**Purpose:** Validate and sanitize LLM responses

```python
import json
from pydantic import BaseModel, ValidationError
from typing import Any

class AnalysisResponse(BaseModel):
    """Expected structure from LLM for analysis"""
    analysis: str
    severity: str | None = None
    suggested_action: str | None = None

def validate_analysis_response(raw_response: str) -> AnalysisResponse:
    """
    Validate LLM response against expected schema

    Returns:
        Validated AnalysisResponse

    Raises:
        ValidationError: If response is malformed or missing required fields
    """
    try:
        # Try to parse JSON
        data = json.loads(raw_response)
        return AnalysisResponse(**data)
    except json.JSONDecodeError as e:
        # Fallback: try to extract JSON from markdown code blocks
        import re
        match = re.search(r'```json\s*(\{.*?\})\s*```', raw_response, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return AnalysisResponse(**data)
        raise ValidationError(f"Invalid JSON response: {e}")
    except ValidationError as e:
        raise ValidationError(f"Response missing required fields: {e}")
```

---

### 4.5 `analyzer/batch_processor.py`

**Purpose:** Process multiple log entries concurrently with rate limiting

```python
import asyncio
from typing import Callable, Any
from asyncio import Semaphore

async def process_batch(
    items: list[Any],
    processor: Callable,
    concurrency: int = 10,
    on_progress: Callable[[int, int], None] | None = None
) -> list[Any]:
    """
    Process items in parallel with concurrency limit

    Args:
        items: List of items to process
        processor: Async function to process each item
        concurrency: Max concurrent tasks
        on_progress: Callback for progress updates (current, total)

    Returns:
        List of results (or exceptions if any failed)
    """
    semaphore = Semaphore(concurrency)
    total = len(items)
    completed = 0

    async def process_with_limit(item):
        nonlocal completed
        async with semaphore:
            result = await processor(item)
            completed += 1
            if on_progress:
                on_progress(completed, total)
            return result

    tasks = [process_with_limit(item) for item in items]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

---

### 4.6 `analyzer/analyzer.py`

**Purpose:** Main analysis orchestration

```python
import json
import asyncio
from pathlib import Path
from .config import AnalyzerConfig
from .providers import get_provider
from .validators import validate_analysis_response
from .batch_processor import process_batch

class LogAnalyzer:
    """Main analyzer class for processing log entries with LLM"""

    def __init__(self, config: AnalyzerConfig):
        self.config = config
        self.provider = get_provider(config)
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> dict[str, str]:
        """Load prompt templates from files or use defaults"""
        prompts = {}
        lang = self.config.language

        # Load analysis prompt
        if self.config.analysis_prompt_path:
            prompts["analysis"] = Path(self.config.analysis_prompt_path).read_text()
        else:
            prompts["analysis"] = Path(f"prompts/analysis_{lang}.txt").read_text()

        # Similar for severity and suggested_action
        # ...

        return prompts

    def _build_prompt(self, entry: dict, prompt_type: str) -> str:
        """Build prompt from template + log entry data"""
        template = self.prompts[prompt_type]
        return template.format(
            language=entry["language"],
            log_template=entry["log_template"],
            code_context=entry["code_context"],
            file_path=entry["file_path"],
            line_number=entry["line_number"]
        )

    async def analyze_entry(self, entry: dict) -> dict:
        """Analyze single log entry"""
        try:
            # 1. Get analysis
            analysis_prompt = self._build_prompt(entry, "analysis")
            analysis_response = await self.provider.complete(
                analysis_prompt,
                model=self.config.model,
                max_tokens=512,
                temperature=0.0
            )

            # 2. Validate response
            validated = validate_analysis_response(analysis_response)

            # 3. Return enriched entry
            return {
                "log_template": entry["log_template"],
                "analysis": validated.analysis,
                "severity": validated.severity,
                "suggested_action": validated.suggested_action,
                "language": entry["language"],
                "source_file": f"{entry['file_path']}:{entry['line_number']}"
            }

        except Exception as e:
            # Fallback for failed analysis
            return {
                "log_template": entry["log_template"],
                "analysis": f"[Analysis failed: {str(e)}]",
                "severity": "unknown",
                "suggested_action": None,
                "language": entry["language"],
                "source_file": f"{entry['file_path']}:{entry['line_number']}"
            }

    async def analyze_batch(self, entries: list[dict]) -> list[dict]:
        """Analyze multiple entries with progress tracking"""
        def on_progress(current, total):
            print(f"Progress: {current}/{total} ({current/total*100:.1f}%)")

        return await process_batch(
            entries,
            self.analyze_entry,
            concurrency=self.config.concurrency,
            on_progress=on_progress
        )

    async def analyze_file(self, input_path: str, output_path: str):
        """Main entry point: analyze raw_logs.json → analyzed_logs.json"""
        # 1. Load raw logs
        with open(input_path) as f:
            data = json.load(f)

        entries = data.get("logs", [])
        print(f"Loaded {len(entries)} log entries from {input_path}")

        # 2. Health check
        if not await self.provider.health_check():
            raise RuntimeError(f"Provider {self.config.provider} failed health check")

        # 3. Process batch
        results = await self.analyze_batch(entries)

        # 4. Save results
        output_data = {
            "analyzed_logs": results,
            "metadata": {
                "provider": self.config.provider,
                "model": self.config.model,
                "language": self.config.language,
                "total_entries": len(results)
            }
        }

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"Analysis complete: {output_path}")
```

---

## 5. CLI Interface

### 5.1 Extended `cli.py`

Add new `analyze` command to existing CLI:

```python
@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="analyzed_logs.json", help="Output file path")
@click.option("--provider", type=click.Choice(["anthropic", "bedrock", "ollama", "lmstudio"]), default="anthropic")
@click.option("--model", default="claude-3-5-sonnet-20241022", help="Model name")
@click.option("--concurrency", "-c", type=int, default=10, help="Concurrent requests")
@click.option("--language", "-l", type=click.Choice(["en", "ru"]), default="en", help="Analysis language")
@click.option("--analysis-prompt", type=click.Path(exists=True), help="Custom analysis prompt file")
@click.option("--severity-prompt", type=click.Path(exists=True), help="Custom severity prompt file")
@click.option("--action-prompt", type=click.Path(exists=True), help="Custom action prompt file")
def analyze(
    input_file: str,
    output: str,
    provider: str,
    model: str,
    concurrency: int,
    language: str,
    analysis_prompt: str | None,
    severity_prompt: str | None,
    action_prompt: str | None
):
    """Analyze logs with LLM to generate human-readable explanations"""

    config = AnalyzerConfig(
        provider=provider,
        model=model,
        concurrency=concurrency,
        language=language,
        analysis_prompt_path=analysis_prompt,
        severity_prompt_path=severity_prompt,
        action_prompt_path=action_prompt
    )

    analyzer = LogAnalyzer(config)
    asyncio.run(analyzer.analyze_file(input_file, output))
```

### 5.2 Usage Examples

```bash
# Basic usage with Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."
leap analyze raw_logs.json --output analyzed_logs.json

# With custom concurrency
leap analyze raw_logs.json -c 20

# Using Ollama locally
leap analyze raw_logs.json --provider ollama --model llama3:8b

# Russian language analysis
leap analyze raw_logs.json -l ru

# Custom prompts for testing
leap analyze raw_logs.json \
  --analysis-prompt ./my_custom_prompt.txt \
  --severity-prompt ./my_severity_prompt.txt
```

---

## 6. Prompt Templates

### 6.1 `prompts/analysis_en.txt`

```
You are a senior software engineer analyzing a log statement from source code.

## Context
- **Programming Language:** {language}
- **Log Template:** {log_template}
- **File Location:** {file_path}:{line_number}

## Code Context:
```
{code_context}
```

## Task
Explain in 1-2 concise sentences:
1. **WHY** this log statement was written (the business/technical reason)
2. **WHAT CONDITION** triggers this log to be emitted
3. Reference specific variable names or function calls from the code context where relevant

## Additional Analysis
- **Severity:** Classify as one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Suggested Action:** What should a developer/operator do when they see this log? (1 sentence, or "None" if informational)

## Output Format (JSON only, no markdown):
{{
  "analysis": "Your 1-2 sentence explanation here",
  "severity": "INFO",
  "suggested_action": "Check database connectivity" or None
}}

IMPORTANT: Respond with ONLY valid JSON. Do not include markdown code blocks or any other text.
```

### 6.2 `prompts/analysis_ru.txt`

```
Вы - старший разработчик, анализирующий выражение логирования в исходном коде.

## Контекст
- **Язык программирования:** {language}
- **Шаблон лога:** {log_template}
- **Расположение файла:** {file_path}:{line_number}

## Контекст кода:
```
{code_context}
```

## Задача
Объясните в 1-2 кратких предложениях:
1. **ПОЧЕМУ** этот лог был написан (бизнес/техническая причина)
2. **КАКОЕ УСЛОВИЕ** вызывает запись этого лога
3. Ссылайтесь на конкретные имена переменных или вызовы функций из контекста кода

## Дополнительный анализ
- **Серьёзность:** Классифицируйте как: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Рекомендуемое действие:** Что должен сделать разработчик/оператор при появлении этого лога? (1 предложение или "None" для информационных)

## Формат вывода (только JSON, без markdown):
{{
  "analysis": "Ваше объяснение в 1-2 предложениях",
  "severity": "INFO",
  "suggested_action": "Проверьте подключение к базе данных" или None
}}

ВАЖНО: Отвечайте ТОЛЬКО валидным JSON. Не используйте markdown code blocks или другой текст.
```

---

## 7. Error Handling & Validation Strategy

### 7.1 Validation Pipeline

```
LLM Response
    ↓
[1] JSON Parsing (strict)
    ↓ (fail)
[2] Markdown Code Block Extraction
    ↓ (fail)
[3] Retry with different prompt (max 2 retries)
    ↓ (fail)
[4] Fallback Response
    {
      "analysis": "[Analysis unavailable - LLM returned invalid response]",
      "severity": "unknown",
      "suggested_action": None
    }
```

### 7.2 Logging Strategy

All validation failures must be logged to a separate file:

```
failed_analyses.log (structured JSON)
{
  "timestamp": "2025-11-16T10:30:00Z",
  "entry": {
    "file_path": "src/main.py",
    "line_number": 42,
    "log_template": "User login failed"
  },
  "error": "ValidationError: missing field 'analysis'",
  "raw_response": "The user tried to log in but..."
}
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# tests/test_validators.py
def test_valid_json_response():
    response = '{"analysis": "Test", "severity": "INFO", "suggested_action": None}'
    result = validate_analysis_response(response)
    assert result.analysis == "Test"
    assert result.severity == "INFO"

def test_markdown_code_block_extraction():
    response = '```json\n{"analysis": "Test"}\n```'
    result = validate_analysis_response(response)
    assert result.analysis == "Test"

def test_invalid_response_raises_error():
    with pytest.raises(ValidationError):
        validate_analysis_response("This is not JSON")
```

### 8.2 Integration Tests

```python
# tests/test_analyzer_integration.py
@pytest.mark.asyncio
async def test_analyze_single_entry_anthropic():
    """Test end-to-end with real Anthropic API (requires API key)"""
    config = AnalyzerConfig(provider="anthropic", model="claude-3-5-sonnet-20241022")
    analyzer = LogAnalyzer(config)

    entry = {
        "log_template": "User login failed",
        "code_context": "if not user.authenticate():\n    logger.error('User login failed')",
        "language": "python",
        "file_path": "test.py",
        "line_number": 10
    }

    result = await analyzer.analyze_entry(entry)
    assert "analysis" in result
    assert result["severity"] in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
```

### 8.3 Mock Tests (for CI/CD without API keys)

```python
@pytest.mark.asyncio
async def test_analyze_with_mock_provider():
    """Test with mocked LLM provider"""
    mock_provider = MockProvider(
        response='{"analysis": "Test analysis", "severity": "INFO", "suggested_action": None}'
    )

    config = AnalyzerConfig(provider="mock")
    analyzer = LogAnalyzer(config)
    analyzer.provider = mock_provider

    result = await analyzer.analyze_entry(test_entry)
    assert result["analysis"] == "Test analysis"
```

---

## 9. Implementation Phases

### Phase 1: Core Infrastructure (Days 1-2)
- [ ] Create `analyzer/` module structure
- [ ] Implement `config.py` with Pydantic models
- [ ] Implement `providers/base.py` abstract interface
- [ ] Implement `validators.py` with JSON validation
- [ ] Write unit tests for validators

### Phase 2: Provider Implementations (Days 3-4)
- [ ] Implement `providers/anthropic.py`
- [ ] Implement `providers/bedrock.py`
- [ ] Implement `providers/ollama.py`
- [ ] Implement `providers/lmstudio.py`
- [ ] Write provider health checks
- [ ] Test each provider independently

### Phase 3: Batch Processing (Day 5)
- [ ] Implement `batch_processor.py` with async concurrency
- [ ] Add progress tracking (stdout + optional JSON file)
- [ ] Test with mock data (100+ entries)

### Phase 4: Analyzer Core (Days 6-7)
- [ ] Implement `analyzer.py` main orchestration
- [ ] Implement prompt loading from files
- [ ] Implement error handling + fallback logic
- [ ] End-to-end test with small dataset (10 entries)

### Phase 5: Prompts (Day 8)
- [ ] Create `prompts/analysis_en.txt`
- [ ] Create `prompts/analysis_ru.txt`
- [ ] Create severity and action prompts (en + ru)
- [ ] Test prompt variations with real LLM

### Phase 6: CLI Integration (Day 9)
- [ ] Add `analyze` command to `cli.py`
- [ ] Add all CLI options (provider, model, concurrency, etc.)
- [ ] Test CLI end-to-end with all providers

### Phase 7: Testing & Documentation (Day 10)
- [ ] Write integration tests
- [ ] Write usage documentation
- [ ] Performance testing (1000+ entries)
- [ ] Final review + bug fixes

---

## 10. Configuration Examples

### 10.1 Environment Variables

```bash
# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# AWS Bedrock
export AWS_REGION="us-east-1"
export AWS_PROFILE="my-profile"

# Ollama (local)
export OLLAMA_API_BASE="http://localhost:11434"

# LMStudio (local)
export LMSTUDIO_API_BASE="http://localhost:1234"
```

### 10.2 Config File (future enhancement)

```yaml
# leap-config.yaml
analyzer:
  provider: anthropic
  model: claude-3-5-sonnet-20241022
  concurrency: 15
  language: en

  prompts:
    analysis: ./custom_prompts/my_analysis.txt
```

---

## 11. Performance Estimates

### 11.1 Cost Analysis (Anthropic Claude Sonnet 3.5)

For **1268 logs** (from current project):

- **Input tokens per entry:** ~500 (prompt + code context)
- **Output tokens per entry:** ~150 (analysis + severity + action)
- **Total input:** 1268 × 500 = 634K tokens
- **Total output:** 1268 × 150 = 190K tokens

**Cost:**
- Input: 634K tokens × $3.00 / 1M = **$1.90**
- Output: 190K tokens × $15.00 / 1M = **$2.85**
- **Total: ~$4.75 per full project analysis**

### 11.2 Time Estimates

With concurrency=10:
- **Time per request:** ~2-3 seconds (network + LLM)
- **Total batches:** 1268 / 10 = 127 batches
- **Estimated time:** 127 × 2.5s = **~5-6 minutes**

With concurrency=20 (if rate limits allow):
- **Estimated time:** **~3 minutes**

---

## 12. Future Enhancements

### 12.1 Short-term (v1.1)
- [ ] Caching for identical log_template + code_context pairs (deduplication)
- [ ] Resume capability (skip already-analyzed entries)
- [ ] Progress bar (rich/tqdm instead of plain text)

### 12.2 Long-term (v2.0)
- [ ] Streaming responses for real-time feedback
- [ ] Multi-modal analysis (include referenced code from other files)
- [ ] Automated prompt A/B testing
- [ ] Cost tracking and optimization suggestions

---

## 13. Success Criteria

✅ **Functionality:**
- All 4 providers (Anthropic, Bedrock, Ollama, LMStudio) work correctly
- 95%+ success rate for valid JSON responses
- Graceful fallback for failed analyses

✅ **Performance:**
- Process 1000 logs in <10 minutes (concurrency=10)
- <5% of entries require fallback responses

✅ **Usability:**
- CLI is intuitive with sensible defaults
- Custom prompts can be tested without code changes
- Clear progress indication during long runs

✅ **Code Quality:**
- 80%+ test coverage
- All modules follow CLAUDE.md guidelines (async-first, FP, structured logging)
- Type hints on all public APIs

---

## 14. Open Questions

1. **Rate Limiting:** Should we add per-provider rate limiting (requests/second)?
2. **Retries:** Should we retry on specific error types (timeout, rate limit) differently?
3. **Output Format:** JSON only, or also support YAML/TOML?
4. **Structured Outputs:** Should we use Anthropic's structured output API (beta) instead of prompt engineering?

---

**Ready to proceed with implementation!**
