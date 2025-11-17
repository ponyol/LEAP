"""
Output generators for test results.

This module provides functions to generate various output formats:
- JSON (structured data)
- Markdown (human-readable report)
- CSV (for analytics/Excel)
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from leap.search_tester.models import TestMetrics, TestResult
from leap.utils.logger import get_logger

logger = get_logger(__name__)


def generate_json_output(
    results: list[TestResult],
    metrics: TestMetrics,
    metadata: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Generate JSON output file with complete test data.

    Args:
        results: List of test results
        metrics: Aggregated metrics
        metadata: Test metadata (config, timestamps, etc.)
        output_path: Path to output JSON file

    Example:
        >>> generate_json_output(results, metrics, metadata, Path("results.json"))
    """
    output_data = {
        "metadata": {
            **metadata,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "metrics": metrics.to_dict(),
        "results": [result.to_dict() for result in results],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    logger.info(f"JSON output written to: {output_path}")


def generate_markdown_report(
    results: list[TestResult],
    metrics: TestMetrics,
    metadata: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Generate Markdown report with human-readable summary.

    Args:
        results: List of test results
        metrics: Aggregated metrics
        metadata: Test metadata
        output_path: Path to output Markdown file

    Example:
        >>> generate_markdown_report(results, metrics, metadata, Path("report.md"))
    """
    lines = []

    # Header
    lines.append("# LEAP Search Quality Report")
    lines.append("")
    lines.append(
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    lines.append(f"**Duration**: {metrics.total_duration_seconds:.1f} seconds")
    lines.append("")

    # Test configuration
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- **VictoriaLogs URL**: {metadata.get('victoria_url', 'N/A')}")
    lines.append(f"- **Search Backend URL**: {metadata.get('search_url', 'N/A')}")
    lines.append(f"- **Query**: `{metadata.get('query', 'N/A')}`")
    lines.append(f"- **Time Range**: {metadata.get('start_date', 'N/A')} - {metadata.get('end_date', 'N/A')}")
    lines.append(f"- **Limit**: {metadata.get('limit', 'N/A')} logs")
    lines.append(f"- **Concurrency**: {metadata.get('concurrency', 'N/A')}")
    if metadata.get("codebase"):
        lines.append(f"- **Codebase Filter**: {metadata['codebase']}")
    lines.append("")

    # Summary
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Logs Tested | {metrics.total_logs} |")
    lines.append(
        f"| ✅ Found by Search | {metrics.found_by_search} ({metrics.hit_rate:.1%}) |"
    )
    lines.append(
        f"| ⚠️  Found by Ripgrep Only | {metrics.found_by_ripgrep_only} ({metrics.false_negative_rate:.1%}) |"
    )
    lines.append(
        f"| ❌ Not Found | {metrics.not_found} ({metrics.miss_rate:.1%}) |"
    )
    lines.append("")

    # Performance metrics
    lines.append("## Performance Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(
        f"| Average Response Time | {metrics.avg_response_time_ms:.1f}ms |"
    )
    lines.append(
        f"| Median Response Time (P50) | {metrics.p50_response_time_ms:.1f}ms |"
    )
    lines.append(
        f"| 95th Percentile (P95) | {metrics.p95_response_time_ms:.1f}ms |"
    )
    lines.append(
        f"| 99th Percentile (P99) | {metrics.p99_response_time_ms:.1f}ms |"
    )
    lines.append(
        f"| Min Response Time | {metrics.min_response_time_ms:.1f}ms |"
    )
    lines.append(
        f"| Max Response Time | {metrics.max_response_time_ms:.1f}ms |"
    )
    lines.append("")

    # Search quality
    lines.append("## Search Quality")
    lines.append("")
    lines.append(f"- **Hit Rate**: {metrics.hit_rate:.1%} {'✅' if metrics.hit_rate >= 0.8 else '⚠️'}")
    lines.append(
        f"- **False Negative Rate**: {metrics.false_negative_rate:.1%} {'✅' if metrics.false_negative_rate < 0.1 else '⚠️'}"
    )

    if metrics.avg_match_score is not None:
        lines.append(
            f"- **Average Match Score**: {metrics.avg_match_score:.2f}"
        )
    lines.append("")

    # False negatives (detailed)
    false_negatives = [r for r in results if r.is_false_negative]
    if false_negatives:
        lines.append("---")
        lines.append("")
        lines.append(
            f"## False Negatives ({len(false_negatives)})"
        )
        lines.append("")
        lines.append(
            "These logs exist in source code but weren't found by the search system:"
        )
        lines.append("")

        for i, result in enumerate(false_negatives[:20], start=1):  # Limit to 20
            lines.append(f"### {i}. `{result.log_message[:100]}`")
            lines.append("")
            lines.append(f"- **File**: `{result.ripgrep_file}:{result.ripgrep_line}`")
            lines.append(
                f"- **Similarity**: {result.ripgrep_similarity:.2f}"
            )
            lines.append(f"- **Code**: `{result.ripgrep_match[:150]}`")
            lines.append(
                f"- **Action**: ⚠️  This log should be indexed"
            )
            lines.append("")

        if len(false_negatives) > 20:
            lines.append(
                f"*...and {len(false_negatives) - 20} more (see JSON output for full list)*"
            )
            lines.append("")

    # Not found logs
    not_found = [r for r in results if r.status == "not_found"]
    if not_found:
        lines.append("---")
        lines.append("")
        lines.append(f"## Not Found Anywhere ({len(not_found)})")
        lines.append("")
        lines.append(
            "These logs weren't found in search or source code (might be dynamic or removed):"
        )
        lines.append("")

        for i, result in enumerate(not_found[:20], start=1):  # Limit to 20
            lines.append(f"{i}. `{result.log_message[:150]}`")

        if len(not_found) > 20:
            lines.append(
                f"*...and {len(not_found) - 20} more (see JSON output for full list)*"
            )
        lines.append("")

    # Recommendations
    lines.append("---")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")

    if metrics.hit_rate < 0.7:
        lines.append(
            f"1. 🔴 **Critical**: Hit rate is {metrics.hit_rate:.1%}. Expected >70%. Consider reindexing logs."
        )
    elif metrics.hit_rate < 0.8:
        lines.append(
            f"1. 🟡 **Warning**: Hit rate is {metrics.hit_rate:.1%}. Expected >80%. Some logs may be missing."
        )
    else:
        lines.append(
            f"1. ✅ **Good**: Hit rate is {metrics.hit_rate:.1%}. Search quality is good."
        )

    if metrics.false_negative_rate > 0.1:
        lines.append(
            f"2. ⚠️  **Index missing logs**: {metrics.found_by_ripgrep_only} logs found by ripgrep should be added to the index."
        )

    if metrics.p99_response_time_ms > 1000:
        lines.append(
            f"3. ⚠️  **Performance**: P99 response time is {metrics.p99_response_time_ms:.0f}ms. Consider optimization."
        )

    if metrics.not_found > metrics.total_logs * 0.05:
        lines.append(
            f"4. ℹ️  **Review not-found logs**: {metrics.not_found} logs ({metrics.miss_rate:.1%}) weren't found anywhere. They might be dynamic or removed from codebase."
        )

    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by LEAP Search Tester*")

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Markdown report written to: {output_path}")


def generate_csv_output(
    results: list[TestResult],
    output_path: Path,
) -> None:
    """
    Generate CSV output for analytics/Excel.

    Args:
        results: List of test results
        output_path: Path to output CSV file

    Example:
        >>> generate_csv_output(results, Path("metrics.csv"))
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "log_message",
                "status",
                "search_found",
                "search_response_time_ms",
                "best_match_score",
                "ripgrep_found",
                "ripgrep_file",
                "ripgrep_line",
                "ripgrep_similarity",
                "is_false_negative",
                "victoria_timestamp",
                "victoria_stream",
            ]
        )

        # Data rows
        for result in results:
            writer.writerow(
                [
                    result.log_message[:200],  # Truncate long messages
                    result.status,
                    result.search_found,
                    f"{result.search_response_time_ms:.1f}",
                    (
                        f"{result.best_match_score:.3f}"
                        if result.best_match_score is not None
                        else ""
                    ),
                    result.ripgrep_found,
                    result.ripgrep_file or "",
                    result.ripgrep_line or "",
                    (
                        f"{result.ripgrep_similarity:.3f}"
                        if result.ripgrep_similarity is not None
                        else ""
                    ),
                    result.is_false_negative,
                    result.victoria_timestamp,
                    json.dumps(result.victoria_stream),  # Serialize dict
                ]
            )

    logger.info(f"CSV output written to: {output_path}")


def display_summary(
    metrics: TestMetrics,
    metadata: dict[str, Any],
) -> None:
    """
    Display final summary in console with Rich formatting.

    Args:
        metrics: Test metrics to display
        metadata: Test metadata

    Example:
        >>> display_summary(metrics, metadata)
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Create summary table
    table = Table(show_header=False, box=None, padding=(0, 2))

    table.add_row(
        "[bold]Total Logs:[/bold]",
        str(metrics.total_logs),
    )
    table.add_row("")

    # Results breakdown
    table.add_row(
        "[bold green]✅ Found by Search:[/bold green]",
        f"{metrics.found_by_search} ({metrics.hit_rate:.1%})",
    )
    table.add_row(
        "[bold yellow]⚠️  Found by Ripgrep:[/bold yellow]",
        f"{metrics.found_by_ripgrep_only} ({metrics.false_negative_rate:.1%})",
    )
    table.add_row(
        "[bold red]❌ Not Found:[/bold red]",
        f"{metrics.not_found} ({metrics.miss_rate:.1%})",
    )
    table.add_row("")

    # Performance
    table.add_row(
        "[bold]Avg Response Time:[/bold]",
        f"{metrics.avg_response_time_ms:.1f}ms",
    )
    table.add_row(
        "[bold]P50 / P95 / P99:[/bold]",
        f"{metrics.p50_response_time_ms:.0f}ms / {metrics.p95_response_time_ms:.0f}ms / {metrics.p99_response_time_ms:.0f}ms",
    )
    table.add_row("")

    # Quality
    hit_rate_emoji = "✅" if metrics.hit_rate >= 0.8 else "⚠️"
    table.add_row(
        "[bold]Hit Rate:[/bold]",
        f"{metrics.hit_rate:.1%} {hit_rate_emoji}",
    )

    fn_rate_emoji = "✅" if metrics.false_negative_rate < 0.1 else "⚠️"
    table.add_row(
        "[bold]False Negative Rate:[/bold]",
        f"{metrics.false_negative_rate:.1%} {fn_rate_emoji}",
    )

    if metrics.avg_match_score is not None:
        table.add_row(
            "[bold]Avg Match Score:[/bold]",
            f"{metrics.avg_match_score:.2f}",
        )

    # Display in panel
    console.print()
    console.print(
        Panel(
            table,
            title="[bold cyan]✅ Test Complete![/bold cyan]",
            subtitle=f"Duration: {metrics.total_duration_seconds:.1f}s",
            border_style="cyan",
        )
    )
    console.print()

    # Output files
    console.print("📁 [bold]Outputs Generated:[/bold]")
    console.print(f"  - JSON: {metadata.get('output_file', 'N/A')}")
    console.print(f"  - Report: {metadata.get('report_file', 'N/A')}")
    console.print(f"  - CSV: {metadata.get('csv_file', 'N/A')}")
    console.print()
