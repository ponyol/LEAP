"""Unit tests for analyzer validators."""

import pytest
import json
from leap.analyzer.validators import (
    AnalysisResponse,
    extract_json_from_text,
    validate_llm_response,
    is_fallback_response,
)


class TestAnalysisResponse:
    """Test AnalysisResponse model validation."""

    def test_valid_response(self):
        """Test valid response with all fields."""
        response = AnalysisResponse(
            analysis="User authentication failed due to invalid credentials",
            severity="ERROR",
            suggested_action="Check user credentials in database"
        )

        assert response.analysis == "User authentication failed due to invalid credentials"
        assert response.severity == "ERROR"
        assert response.suggested_action == "Check user credentials in database"

    def test_response_without_optional_fields(self):
        """Test response with only required analysis field."""
        response = AnalysisResponse(
            analysis="Debug message for development",
            severity=None,
            suggested_action=None
        )

        assert response.analysis == "Debug message for development"
        assert response.severity is None
        assert response.suggested_action is None

    def test_empty_analysis_raises_error(self):
        """Test that empty analysis raises validation error."""
        with pytest.raises(Exception):
            AnalysisResponse(
                analysis="",
                severity="INFO"
            )

    def test_severity_normalization(self):
        """Test that severity is normalized to uppercase."""
        response = AnalysisResponse(
            analysis="Test",
            severity="info"  # lowercase
        )

        assert response.severity == "INFO"

    def test_invalid_severity_defaults_to_unknown(self):
        """Test that invalid severity defaults to UNKNOWN."""
        response = AnalysisResponse(
            analysis="Test",
            severity="INVALID_LEVEL"
        )

        assert response.severity == "UNKNOWN"

    def test_suggested_action_null_values(self):
        """Test that null-like values in suggested_action become None."""
        for null_value in ["none", "null", "None", "NULL", "n/a", "N/A"]:
            response = AnalysisResponse(
                analysis="Test",
                suggested_action=null_value
            )
            assert response.suggested_action is None

    def test_analysis_too_long_truncation(self):
        """Test that analysis longer than 2000 chars is truncated."""
        long_analysis = "x" * 2500
        response = AnalysisResponse(
            analysis=long_analysis,
            severity="INFO"
        )

        assert len(response.analysis) == 2003  # 2000 + "..."
        assert response.analysis.endswith("...")

    def test_suggested_action_too_long_truncation(self):
        """Test that suggested_action longer than 500 chars is truncated."""
        long_action = "y" * 600
        response = AnalysisResponse(
            analysis="Test",
            suggested_action=long_action
        )

        assert len(response.suggested_action) == 503  # 500 + "..."
        assert response.suggested_action.endswith("...")


class TestExtractJSONFromText:
    """Test JSON extraction from various text formats."""

    def test_direct_json(self):
        """Test direct JSON parsing."""
        text = '{"analysis": "Test", "severity": "INFO"}'
        result = extract_json_from_text(text)

        assert result["analysis"] == "Test"
        assert result["severity"] == "INFO"

    def test_json_in_markdown_code_block(self):
        """Test extraction from ```json ... ``` block."""
        text = """
Here is the analysis:

```json
{
  "analysis": "User login failed",
  "severity": "ERROR"
}
```

That's it!
"""
        result = extract_json_from_text(text)

        assert result["analysis"] == "User login failed"
        assert result["severity"] == "ERROR"

    def test_json_in_plain_code_block(self):
        """Test extraction from ``` ... ``` block."""
        text = """
```
{"analysis": "Test", "severity": "INFO"}
```
"""
        result = extract_json_from_text(text)

        assert result["analysis"] == "Test"

    def test_json_in_text(self):
        """Test extraction of JSON embedded in text."""
        text = 'The result is {"analysis": "Found it", "severity": "INFO"} as shown above.'
        result = extract_json_from_text(text)

        assert result["analysis"] == "Found it"

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises JSONDecodeError."""
        text = "This is not JSON at all"

        with pytest.raises(json.JSONDecodeError):
            extract_json_from_text(text)

    def test_invalid_json_in_markdown_code_block(self):
        """Test extraction fails when JSON block contains invalid JSON."""
        text = """
```json
{invalid json here}
```
"""
        # Should try to parse the block but fail, then try other strategies
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_text(text)

    def test_invalid_json_in_plain_code_block(self):
        """Test extraction fails when code block contains invalid JSON."""
        text = """
```
{this is not: valid json}
```
"""
        # Should try to parse the block but fail, then try other strategies
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_text(text)


class TestValidateLLMResponse:
    """Test LLM response validation with fallbacks."""

    def test_valid_json_response(self):
        """Test validation of valid JSON response."""
        response = '{"analysis": "User login failed", "severity": "ERROR", "suggested_action": "Check credentials"}'

        result = validate_llm_response(response, "login failed", "test.py", 10)

        assert result.analysis == "User login failed"
        assert result.severity == "ERROR"
        assert result.suggested_action == "Check credentials"
        assert not is_fallback_response(result)

    def test_json_in_markdown(self):
        """Test validation of JSON in markdown code block."""
        response = """
```json
{
  "analysis": "Database connection timeout",
  "severity": "CRITICAL",
  "suggested_action": "Check database connectivity"
}
```
"""
        result = validate_llm_response(response, "db timeout", "db.py", 42)

        assert result.analysis == "Database connection timeout"
        assert result.severity == "CRITICAL"
        assert not is_fallback_response(result)

    def test_invalid_json_returns_fallback(self):
        """Test that invalid JSON returns fallback response."""
        response = "This is not valid JSON"

        result = validate_llm_response(response, "test", "test.py", 1)

        assert result.analysis.startswith("[Analysis failed:")
        assert result.severity == "UNKNOWN"
        assert is_fallback_response(result)

    def test_missing_fields_returns_fallback(self):
        """Test that missing required fields returns fallback."""
        response = '{"severity": "INFO"}'  # Missing 'analysis'

        result = validate_llm_response(response, "test", "test.py", 1)

        # Should still try to salvage what it can
        assert result.severity == "INFO"

    def test_malformed_json_returns_fallback(self):
        """Test that malformed JSON returns fallback."""
        response = '{"analysis": "Test", severity: INFO}'  # Invalid JSON (unquoted key)

        result = validate_llm_response(response, "test", "test.py", 1)

        assert is_fallback_response(result)

    def test_validation_error_with_salvage(self):
        """Test that ValidationError tries to salvage what it can."""
        # Missing required 'analysis' field will cause ValidationError
        response = '{"severity": "WARNING", "suggested_action": "Fix this"}'

        result = validate_llm_response(response, "test", "test.py", 1)

        # Should salvage the severity and suggested_action
        assert result.severity == "WARNING"
        # The analysis should have fallback message since it was missing
        assert "[Analysis failed:" in result.analysis

    def test_complete_fallback_on_exception(self):
        """Test complete fallback when even salvage attempt fails."""
        # This will trigger json.JSONDecodeError which is caught
        # The salvage in except ValidationError won't be reached
        response = "completely invalid response with no json at all"

        result = validate_llm_response(response, "test", "test.py", 1)

        assert result.analysis.startswith("[Analysis failed:")
        assert result.severity == "UNKNOWN"
        assert result.suggested_action is None
        assert is_fallback_response(result)


class TestIsFallbackResponse:
    """Test fallback response detection."""

    def test_fallback_response_detection(self):
        """Test that fallback responses are detected."""
        fallback = AnalysisResponse(
            analysis="[Analysis failed: Invalid JSON]",
            severity="UNKNOWN"
        )

        assert is_fallback_response(fallback)

    def test_normal_response_not_fallback(self):
        """Test that normal responses are not detected as fallbacks."""
        normal = AnalysisResponse(
            analysis="User logged in successfully",
            severity="INFO"
        )

        assert not is_fallback_response(normal)

    def test_edge_case_with_brackets(self):
        """Test that normal text with brackets is not flagged as fallback."""
        normal = AnalysisResponse(
            analysis="This log [with brackets] is normal",
            severity="INFO"
        )

        assert not is_fallback_response(normal)
