"""Language detection for log entries.

This module provides functionality to detect the language of log entries
to enable language-specific indexing (separate collections for Russian and English).
"""

from enum import Enum

from langdetect import LangDetectException, detect_langs


class Language(str, Enum):
    """Supported languages for indexing."""

    RUSSIAN = "ru"
    ENGLISH = "en"


def detect_language(text: str, confidence_threshold: float = 0.7) -> Language:
    """Detect the language of a text.

    Uses langdetect to analyze the text and determine if it's Russian or English.
    Falls back to English if detection fails or confidence is low.

    Args:
        text: Text to analyze
        confidence_threshold: Minimum confidence required to use detection result

    Returns:
        Detected language (Language.RUSSIAN or Language.ENGLISH)
    """
    # Handle empty or very short text
    if not text or len(text.strip()) < 3:
        return Language.ENGLISH

    try:
        # Detect language with confidence scores
        langs = detect_langs(text)

        # Check if we have results
        if not langs:
            return Language.ENGLISH

        # Get the most confident result
        top_lang = langs[0]

        # If Russian is detected with high confidence, return Russian
        if top_lang.lang == "ru" and top_lang.prob >= confidence_threshold:
            return Language.RUSSIAN

        # If English is detected with high confidence, return English
        if top_lang.lang == "en" and top_lang.prob >= confidence_threshold:
            return Language.ENGLISH

        # Default to English for low confidence or other languages
        return Language.ENGLISH

    except LangDetectException:
        # If detection fails, default to English
        return Language.ENGLISH


def detect_language_for_log_entry(
    log_template: str, analysis: str | None = None
) -> Language:
    """Detect language for a log entry.

    Combines log_template and analysis (if available) for better detection accuracy.

    Args:
        log_template: The log template text
        analysis: Optional analysis text from the analyzer

    Returns:
        Detected language (Language.RUSSIAN or Language.ENGLISH)
    """
    # Combine template and analysis for better detection
    combined_text = log_template
    if analysis:
        combined_text = f"{log_template} {analysis}"

    return detect_language(combined_text)
