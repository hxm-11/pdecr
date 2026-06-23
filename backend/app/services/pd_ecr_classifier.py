"""PD-ECR Change Type Classifier.

Rule-based classification of new PD-ECR requests into ChangeTypeCategory,
with LLM fallback for ambiguous inputs.

Classification uses trigger keyword matching on change_description,
change_reason, and change_type fields. The trigger keyword lists are
derived from patterns.json (the same source as the pattern library).

Usage:
    from app.services.pd_ecr_classifier import classify_change_type

    classification = classify_change_type(request)
    # classification.category -> ChangeTypeCategory
    # classification.confidence -> ConfidenceLevel
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.pd_ecr_patterns import (
    ChangeTypePattern,
    PatternLibrary,
    load_pattern_library,
)
from app.services.pd_ecr_schema import (
    ChangeTypeCategory,
    ClassificationResult,
    ConfidenceLevel,
    NewPdEcrRequest,
    SampleStage,
)

# ---------------------------------------------------------------------------
# LLM fallback cache (simple in-memory, TTL could be added for production)
# ---------------------------------------------------------------------------
_llm_cache: dict[str, ClassificationResult] = {}


def _cache_key(request: NewPdEcrRequest) -> str:
    payload = {
        "change_type": request.change_type,
        "change_description": request.change_description,
        "change_reason": request.change_reason,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Sample stage extraction
# ---------------------------------------------------------------------------


def _extract_sample_stage(text: str) -> SampleStage | None:
    """Extract sample stage (A/B/C/D) from text."""
    t = text.upper().replace(" ", "").replace("-", "")
    if "ASAMPLE" in t or "ASAMP" in t or "A样" in text:
        return SampleStage.A_SAMPLE
    if "BSAMPLE" in t or "BSAMP" in t or "B样" in text:
        return SampleStage.B_SAMPLE
    if "CSAMPLE" in t or "CSAMP" in t or "C样" in text:
        return SampleStage.C_SAMPLE
    if "DSAMPLE" in t or "DSAMP" in t or "D样" in text:
        return SampleStage.D_SAMPLE
    return None


# ---------------------------------------------------------------------------
# Rule-based classification
# ---------------------------------------------------------------------------


def _rule_classify(
    request: NewPdEcrRequest,
    library: PatternLibrary,
) -> ClassificationResult:
    """Rule-based classification via trigger keyword matching."""

    combined_text = (
        f"{request.change_type} {request.change_description} {request.change_reason}"
    ).lower()

    # Score each pattern by trigger keyword overlap
    scores: dict[ChangeTypeCategory, tuple[int, list[str]]] = {}

    for pattern in library.patterns:
        matched_triggers: list[str] = []
        for trigger in pattern.typical_triggers:
            if trigger.lower() in combined_text:
                matched_triggers.append(trigger)

        score = len(matched_triggers) * 3

        # Bonus: sample stage match between request and pattern
        request_stage = _extract_sample_stage(request.change_type)
        if request_stage and request_stage.value in pattern.sample_stages:
            score += 2

        if score > 0:
            scores[pattern.category] = (score, matched_triggers)

    # --- No match at all ---
    if not scores:
        return ClassificationResult(
            category=ChangeTypeCategory.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
            matched_triggers=[],
            sample_stage=_extract_sample_stage(request.change_type),
            classification_method="rule",
            needs_llm_fallback=True,
        )

    # --- Best match ---
    best_category = max(scores, key=lambda k: scores[k][0])
    best_score, best_triggers = scores[best_category]

    confidence = (
        ConfidenceLevel.HIGH
        if best_score >= 8
        else ConfidenceLevel.MEDIUM
        if best_score >= 5
        else ConfidenceLevel.LOW
    )

    return ClassificationResult(
        category=best_category,
        confidence=confidence,
        matched_triggers=best_triggers,
        sample_stage=_extract_sample_stage(request.change_type),
        classification_method="rule",
        needs_llm_fallback=(confidence == ConfidenceLevel.LOW),
    )


# ---------------------------------------------------------------------------
# LLM fallback classification
# ---------------------------------------------------------------------------


def _build_llm_classification_prompt(request: NewPdEcrRequest) -> str:
    """Build a lightweight classification prompt for the LLM fallback."""

    categories_desc = []
    for pattern in load_pattern_library().patterns:
        label = f"{pattern.label_cn} ({pattern.label_en})"
        categories_desc.append(
            f"- **{pattern.category.value}**: {label} — {pattern.description[:120]}"
        )

    return f"""Classify this PD-ECR engineering change request into exactly one category.

## Request
- Change Type: {request.change_type}
- Change Description: {request.change_description}
- Change Reason: {request.change_reason}

## Categories
{chr(10).join(categories_desc)}

Return ONLY a JSON object with these fields:
- `category`: one of the category values listed above
- `confidence`: "high", "medium", or "low"
- `reasoning`: one sentence explaining the classification

Example: {{"category": "first_sample_release", "confidence": "high", "reasoning": "Request describes first A-Sample release for a new project."}}"""


def _llm_classify(
    request: NewPdEcrRequest,
    library: PatternLibrary,
) -> ClassificationResult:
    """LLM-based classification fallback for ambiguous inputs.

    Uses a lightweight structured-output call. Results are cached by
    input hash to avoid repeated API calls.
    """
    # Check cache first
    key = _cache_key(request)
    if key in _llm_cache:
        return _llm_cache[key]

    try:
        from app.core.config import settings  # type: ignore[import-untyped]
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        # If openai not available, return UNKNOWN
        result = ClassificationResult(
            category=ChangeTypeCategory.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
            classification_method="llm",
            needs_llm_fallback=False,
        )
        _llm_cache[key] = result
        return result

    prompt = _build_llm_classification_prompt(request)

    try:
        # Use the configured base URL and API key from settings
        client_kwargs: dict[str, Any] = {}
        if hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
            client_kwargs["api_key"] = settings.OPENAI_API_KEY
        if hasattr(settings, "OPENAI_BASE_URL") and settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL

        client = OpenAI(**client_kwargs)

        # Determine model — prefer a fast/cheap model for classification
        model = getattr(settings, "PD_ECR_CLASSIFIER_MODEL", None) or getattr(
            settings, "OPENAI_MODEL", "gpt-4o-mini"
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an engineering document classifier. Output only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=256,
        )

        content = response.choices[0].message.content or "{}"
        # Strip markdown fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
            content = content.strip()

        parsed = json.loads(content)

        category_raw = parsed.get("category", "unknown")
        try:
            category = ChangeTypeCategory(category_raw)
        except ValueError:
            category = ChangeTypeCategory.UNKNOWN

        confidence_raw = parsed.get("confidence", "low")
        try:
            confidence = ConfidenceLevel(confidence_raw)
        except ValueError:
            confidence = ConfidenceLevel.LOW

        result = ClassificationResult(
            category=category,
            confidence=confidence,
            matched_triggers=[],
            sample_stage=_extract_sample_stage(request.change_type),
            classification_method="llm",
            needs_llm_fallback=False,
        )

    except Exception:
        # On any API error, fall back to UNKNOWN
        result = ClassificationResult(
            category=ChangeTypeCategory.UNKNOWN,
            confidence=ConfidenceLevel.LOW,
            classification_method="llm",
            needs_llm_fallback=False,
        )

    _llm_cache[key] = result
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_change_type(
    request: NewPdEcrRequest,
    library: PatternLibrary | None = None,
) -> ClassificationResult:
    """Classify a new PD-ECR request into a ChangeTypeCategory.

    Strategy:
    1. Rule-based: keyword trigger matching (fast, deterministic)
    2. LLM fallback: only when rule-based confidence is LOW
    3. Results are cached when LLM is used

    Args:
        request: The new PD-ECR request to classify.
        library: Optional pre-loaded pattern library (loads if not provided).

    Returns:
        ClassificationResult with category, confidence, and metadata.
    """
    if library is None:
        library = load_pattern_library()

    result = _rule_classify(request, library)

    if result.needs_llm_fallback:
        llm_result = _llm_classify(request, library)
        # Only use LLM result if it's not UNKNOWN — otherwise keep rule result
        if llm_result.category != ChangeTypeCategory.UNKNOWN:
            return llm_result

    return result


def clear_classification_cache() -> None:
    """Clear the LLM classification cache (useful for testing)."""
    _llm_cache.clear()
