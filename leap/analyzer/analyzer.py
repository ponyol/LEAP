"""Main analyzer orchestration and caching logic."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .batch_processor import process_batch
from .config import AnalyzerConfig
from .providers import TokenUsage, get_provider
from .validators import is_fallback_response, validate_llm_response

logger = logging.getLogger(__name__)


class TokenAccumulator:
    """Accumulates token usage statistics across multiple API calls."""

    def __init__(self) -> None:
        """Initialize token accumulator."""
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    def add(self, usage: TokenUsage | None) -> None:
        """Add token usage from a single API call.

        Args:
            usage: Token usage from API response (can be None for local models)
        """
        if usage:
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens
            self.total_tokens += usage.total_tokens

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary for serialization.

        Returns:
            Dict with input_tokens, output_tokens, total_tokens
        """
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens
        }


class AnalysisCache:
    """Cache for LLM analysis results to avoid duplicate API calls.

    The cache key is a hash of (log_template + code_context + language).
    This allows deduplication of identical log entries even if they appear
    in different files or lines.
    """

    def __init__(self, enabled: bool = True):
        """Initialize analysis cache.

        Args:
            enabled: Whether caching is enabled
        """
        self.enabled = enabled
        self._cache: dict[str, dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0

    def _compute_key(self, entry: dict[str, Any]) -> str:
        """Compute cache key from log entry.

        Args:
            entry: Log entry dict with log_template, code_context, language

        Returns:
            Hash string to use as cache key
        """
        # Create a stable string representation
        cache_input = (
            f"{entry.get('log_template', '')}\n"
            f"{entry.get('code_context', '')}\n"
            f"{entry.get('language', '')}"
        )

        # Hash it for compact key
        return hashlib.sha256(cache_input.encode()).hexdigest()

    def get(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Retrieve cached analysis for entry.

        Args:
            entry: Log entry to look up

        Returns:
            Cached analysis result, or None if not found
        """
        if not self.enabled:
            return None

        key = self._compute_key(entry)
        result = self._cache.get(key)

        if result:
            self._hits += 1
            logger.debug(f"Cache hit for {entry.get('file_path')}:{entry.get('line_number')}")
        else:
            self._misses += 1

        return result

    def set(self, entry: dict[str, Any], result: dict[str, Any]) -> None:
        """Store analysis result in cache.

        Args:
            entry: Log entry that was analyzed
            result: Analysis result to cache
        """
        if not self.enabled:
            return

        key = self._compute_key(entry)
        self._cache[key] = result

    def stats(self) -> dict[str, int | float]:
        """Get cache statistics.

        Returns:
            Dict with hits, misses, size, hit_rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "hit_rate": round(hit_rate, 2)
        }


class LogAnalyzer:
    """Main analyzer class for processing log entries with LLM.

    This class orchestrates the entire analysis pipeline:
    1. Load raw logs
    2. Check cache for duplicates
    3. Build prompts from templates
    4. Call LLM provider
    5. Validate responses
    6. Save analyzed logs
    """

    def __init__(self, config: AnalyzerConfig):
        """Initialize analyzer with configuration.

        Args:
            config: Analyzer configuration

        Raises:
            ValueError: If configuration is invalid
        """
        self.config = config
        config.validate_provider_config()

        self.provider = get_provider(config)
        self.cache = AnalysisCache(enabled=config.enable_cache)
        self.token_usage = TokenAccumulator()
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> dict[str, str]:
        """Load prompt templates from files.

        Returns:
            Dict mapping prompt type to template string

        Raises:
            FileNotFoundError: If prompt files don't exist
        """
        prompts = {}
        lang = self.config.language

        # Determine base directory for prompts
        # If running from package, prompts are in project root
        base_dir = Path(__file__).parent.parent.parent / "prompts"

        # Load analysis prompt
        if self.config.analysis_prompt_path:
            prompt_path = Path(self.config.analysis_prompt_path)
        else:
            prompt_path = base_dir / f"analysis_{lang}.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Analysis prompt not found: {prompt_path}. "
                f"Create this file or specify --analysis-prompt"
            )

        prompts["analysis"] = prompt_path.read_text()

        logger.info(f"Loaded prompt template: {prompt_path}")
        return prompts

    def _build_prompt(self, entry: dict[str, Any]) -> str:
        """Build prompt from template and log entry data.

        Args:
            entry: Log entry dict with all fields

        Returns:
            Formatted prompt string
        """
        template = self.prompts["analysis"]

        # Format template with entry data
        return template.format(
            language=entry.get("language", "unknown"),
            log_template=entry.get("log_template", ""),
            code_context=entry.get("code_context", ""),
            file_path=entry.get("file_path", ""),
            line_number=entry.get("line_number", 0)
        )

    async def analyze_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Analyze single log entry with caching.

        Args:
            entry: Log entry dict from raw_logs.json

        Returns:
            Analyzed log entry with analysis, severity, suggested_action
        """
        # Check cache first
        cached = self.cache.get(entry)
        if cached:
            return cached

        try:
            # Build prompt
            prompt = self._build_prompt(entry)

            # Call LLM with retry
            response = await self.provider.complete_with_retry(
                prompt=prompt,
                model=self.config.model,
                max_tokens=1024,
                temperature=0.0,
                max_retries=self.config.max_retries
            )

            # Track token usage
            self.token_usage.add(response.usage)

            # Validate response
            validated = validate_llm_response(
                response.text,
                entry.get("log_template", ""),
                entry.get("file_path", ""),
                entry.get("line_number", 0)
            )

            # Build result
            result = {
                "log_template": entry.get("log_template", ""),
                "analysis": validated.analysis,
                "severity": validated.severity,
                "suggested_action": validated.suggested_action,
                "language": entry.get("language", ""),
                "source_file": f"{entry.get('file_path', '')}:{entry.get('line_number', 0)}"
            }

            # Cache if not a fallback response
            if not is_fallback_response(validated):
                self.cache.set(entry, result)

            return result

        except Exception as e:
            logger.error(
                f"Failed to analyze {entry.get('file_path')}:{entry.get('line_number')}: {e}"
            )

            # Return fallback
            return {
                "log_template": entry.get("log_template", ""),
                "analysis": f"[Analysis failed: {type(e).__name__}]",
                "severity": "UNKNOWN",
                "suggested_action": None,
                "language": entry.get("language", ""),
                "source_file": f"{entry.get('file_path', '')}:{entry.get('line_number', 0)}"
            }

    async def analyze_batch(self, entries: list[dict[str, Any]]) -> list[dict[str, Any] | None]:
        """Analyze multiple entries in parallel.

        Args:
            entries: List of log entries

        Returns:
            List of analyzed entries (same order as input)
        """
        logger.info(f"Analyzing {len(entries)} log entries with concurrency={self.config.concurrency}")

        results: list[dict[str, Any] | None] = await process_batch(
            entries,
            self.analyze_entry,
            concurrency=self.config.concurrency,
            show_progress=True,
            on_error="continue"  # Continue on errors, return None for failed items
        )

        # Log cache statistics
        stats = self.cache.stats()
        logger.info(
            f"Cache statistics: {stats['hits']} hits, {stats['misses']} misses, "
            f"{stats['hit_rate']}% hit rate, {stats['size']} unique entries"
        )

        return results

    async def analyze_file(
        self,
        input_path: str,
        output_path: str
    ) -> dict[str, Any]:
        """Main entry point: analyze raw_logs.json → analyzed_logs.json.

        Args:
            input_path: Path to raw_logs.json
            output_path: Path to output analyzed_logs.json

        Returns:
            Statistics about the analysis run

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If input file is invalid
        """
        # 1. Load raw logs
        input_file = Path(input_path)
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        with open(input_file) as f:
            data = json.load(f)

        # Handle both formats: list directly or {"logs": [...]}
        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("logs", [])
        else:
            raise ValueError(f"Invalid format in {input_path}: expected list or dict")

        if not entries:
            raise ValueError(f"No log entries found in {input_path}")

        logger.info(f"Loaded {len(entries)} log entries from {input_path}")

        # 2. Health check
        logger.info(f"Performing health check for provider: {self.config.provider}")
        if not await self.provider.health_check():
            raise RuntimeError(
                f"Provider {self.config.provider} failed health check. "
                f"Check your configuration and network connectivity."
            )
        logger.info("Health check passed")

        # 3. Process batch
        results = await self.analyze_batch(entries)

        # 4. Count successes and failures
        successful = sum(1 for r in results if r and not r["analysis"].startswith("[Analysis failed:"))
        failed = len(results) - successful

        # 5. Save results
        metadata: dict[str, Any] = {
            "provider": self.config.provider,
            "model": self.config.model,
            "language": self.config.language,
            "total_entries": len(results),
            "successful": successful,
            "failed": failed,
            "cache_stats": self.cache.stats(),
            "token_usage": self.token_usage.to_dict()
        }

        output_data: dict[str, Any] = {
            "analyzed_logs": results,
            "metadata": metadata
        }

        output_file = Path(output_path)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Analysis complete: {output_path}")
        logger.info(f"Success: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")

        if failed > 0:
            logger.warning(f"Failed: {failed}/{len(results)} ({failed/len(results)*100:.1f}%)")

        return metadata
