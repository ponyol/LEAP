"""Validation and sanitization for LLM responses."""

import json
import re
import logging
from typing import Any, cast
from pydantic import BaseModel, ValidationError, field_validator

logger = logging.getLogger(__name__)


class AnalysisResponse(BaseModel):
    """Expected structure from LLM for log analysis.

    This model defines the schema that LLM responses must conform to.
    All fields are validated and sanitized before being used in the output.
    """

    analysis: str
    severity: str | None = None
    suggested_action: str | None = None

    @field_validator("analysis")
    @classmethod
    def validate_analysis(cls, v: str) -> str:
        """Ensure analysis is non-empty and reasonably sized."""
        if not v or not v.strip():
            raise ValueError("Analysis cannot be empty")
        if len(v) > 2000:
            logger.warning(f"Analysis too long ({len(v)} chars), truncating")
            return v[:2000] + "..."
        return v.strip()

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        """Validate severity is one of the expected values."""
        if v is None:
            return None

        valid_severities = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "UNKNOWN"}
        normalized = v.upper().strip()

        if normalized not in valid_severities:
            logger.warning(f"Invalid severity '{v}', defaulting to UNKNOWN")
            return "UNKNOWN"

        return normalized

    @field_validator("suggested_action")
    @classmethod
    def validate_suggested_action(cls, v: str | None) -> str | None:
        """Sanitize suggested action."""
        if v is None or v.strip().lower() in ("none", "null", "n/a"):
            return None
        if len(v) > 500:
            logger.warning(f"Suggested action too long ({len(v)} chars), truncating")
            return v[:500] + "..."
        return v.strip()


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract JSON from text that may contain markdown code blocks.

    This function tries multiple strategies to extract valid JSON:
    1. Direct JSON parsing
    2. Extract from ```json ... ``` markdown blocks
    3. Extract from ``` ... ``` code blocks
    4. Extract first {...} or [...] found in text

    Args:
        text: Raw text that may contain JSON

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Strategy 1: Direct parsing
    try:
        return cast(dict[str, Any], json.loads(text))
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from ```json ... ```
    json_block_match = re.search(
        r'```json\s*(\{.*?\})\s*```',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if json_block_match:
        try:
            return cast(dict[str, Any], json.loads(json_block_match.group(1)))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Extract from ``` ... ```
    code_block_match = re.search(
        r'```\s*(\{.*?\})\s*```',
        text,
        re.DOTALL
    )
    if code_block_match:
        try:
            return cast(dict[str, Any], json.loads(code_block_match.group(1)))
        except json.JSONDecodeError:
            pass

    # Strategy 4: Extract first {...} found
    brace_match = re.search(r'\{.*\}', text, re.DOTALL)
    if brace_match:
        try:
            return cast(dict[str, Any], json.loads(brace_match.group(0)))
        except json.JSONDecodeError:
            pass

    # All strategies failed
    raise json.JSONDecodeError(
        f"Could not extract valid JSON from text: {text[:200]}...",
        text,
        0
    )


def validate_llm_response(
    raw_response: str,
    log_template: str,
    file_path: str,
    line_number: int
) -> AnalysisResponse:
    """Validate and parse LLM response with robust error handling.

    This is the main validation entry point. It implements a multi-stage
    validation pipeline with fallbacks at each stage.

    Validation Pipeline:
    1. Extract JSON from response text
    2. Validate against AnalysisResponse schema
    3. Return validated response

    If validation fails at any stage, detailed error information is logged
    for later manual review.

    Args:
        raw_response: Raw text from LLM
        log_template: Original log template (for error logging)
        file_path: Source file path (for error logging)
        line_number: Source line number (for error logging)

    Returns:
        Validated AnalysisResponse (may be fallback if validation failed)
    """
    try:
        # Stage 1: Extract JSON
        data = extract_json_from_text(raw_response)

        # Stage 2: Validate schema
        return AnalysisResponse(**data)

    except json.JSONDecodeError as e:
        logger.error(
            f"JSON decode error for {file_path}:{line_number}",
            extra={
                "log_template": log_template,
                "error": str(e),
                "raw_response": raw_response[:500]
            }
        )
        # Return fallback
        return AnalysisResponse(
            analysis="[Analysis failed: Invalid JSON response from LLM]",
            severity="UNKNOWN",
            suggested_action=None
        )

    except ValidationError as e:
        logger.error(
            f"Validation error for {file_path}:{line_number}",
            extra={
                "log_template": log_template,
                "error": str(e),
                "raw_response": raw_response[:500]
            }
        )
        # Try to salvage what we can
        try:
            data = extract_json_from_text(raw_response)
            return AnalysisResponse(
                analysis=data.get("analysis", "[Analysis failed: Missing analysis field]"),
                severity=data.get("severity", "UNKNOWN"),
                suggested_action=data.get("suggested_action")
            )
        except Exception:
            # Complete fallback
            return AnalysisResponse(
                analysis="[Analysis failed: Response validation error]",
                severity="UNKNOWN",
                suggested_action=None
            )

    except Exception as e:
        logger.error(
            f"Unexpected error validating response for {file_path}:{line_number}",
            extra={
                "log_template": log_template,
                "error": str(e),
                "raw_response": raw_response[:500]
            }
        )
        return AnalysisResponse(
            analysis=f"[Analysis failed: {type(e).__name__}]",
            severity="UNKNOWN",
            suggested_action=None
        )


def is_fallback_response(response: AnalysisResponse) -> bool:
    """Check if response is a fallback (validation failed).

    Args:
        response: Validated AnalysisResponse

    Returns:
        True if this is a fallback response (failed validation)
    """
    return response.analysis.startswith("[Analysis failed:")
