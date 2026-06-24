"""
LLM-based PD-ECR structured extraction.

Takes cleaned MinerU markdown, sends it to an LLM with a schema prompt,
and returns structured JSON matching pdecr_schema.OUTPUT_SCHEMA.

Falls back gracefully if LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import re

from app.rag.pdecr_schema import (
    IDENTIFICATION_FIELDS,
    CHANGE_REQUEST_FIELDS,
    IMPACT_ANALYSIS_ITEMS,
    AFFECTED_DOCUMENTS_ITEMS,
    VALIDATION_ITEMS,
    APPROVAL_ROLES,
)
from app.rag.text_cleaner import clean_text

logger = logging.getLogger(__name__)

# Truncate input to avoid token blowout
MAX_INPUT_CHARS = 12000


def _build_system_prompt() -> str:
    """Build the system prompt describing the PD-ECR extraction task."""
    id_fields = "\n".join(
        f'    "{key}": "{spec["label"]}{" / ".join(spec.get("aliases", []))}"'
        for key, spec in IDENTIFICATION_FIELDS.items()
    )
    cr_fields = "\n".join(
        f'    "{key}": "{spec["label"]}"'
        for key, spec in CHANGE_REQUEST_FIELDS.items()
    )
    ia_items = "\n".join(
        f'    {{"key": "{item["key"]}", "label": "{item["label"]} ({item["zh"]})", "value": "yes/no", "remark": "...", "confirmed_by": "..."}}'
        for item in IMPACT_ANALYSIS_ITEMS
    )
    ad_items = "\n".join(
        f'    {{"key": "{item["key"]}", "label": "{item["label"]} ({item["zh"]})", "value": "yes/no", "responsible": "...", "due_date": "..."}}'
        for item in AFFECTED_DOCUMENTS_ITEMS
    )
    val_items = ", ".join(f'"{v}"' for v in VALIDATION_ITEMS)
    approval_roles = ", ".join(r["role"] for r in APPROVAL_ROLES)

    return f"""You are a PD-ECR (Product Development Engineering Change Request) document parser.

Given the markdown text extracted from a PD-ECR form (via OCR/MinerU), extract the following structured data.
Return ONLY valid JSON — no markdown fences, no explanations.

## Output schema

{{
  "identification": {{
{id_fields}
  }},
  "change_request": {{
{cr_fields}
  }},
  "impact_analysis": {{
    "items": [
{ia_items}
    ]
  }},
  "affected_documents": [
{ad_items}
  ],
  "validation_items": [
    {{"name": "...", "checked": true/false, "finish_date": "...", "responsible": "...", "comment": "..."}}
  ],
  "implementation": [
    {{"department": "...", "yn": "Y/N", "description": "...", "responsible": "...", "due_date": "..."}}
  ],
  "approval": [
    {{"role": "...", "person": "...", "date": "..."}}
  ]
}}

## Rules

1. Extract values EXACTLY as they appear in the text. Do not invent or guess.
2. If a field is not found, use empty string "".
3. For checkbox items: look for ☑ ☒ √ ✓ [x] [X] markers. Map checked to "yes", unchecked to "no".
4. Date format: keep original format from the document (e.g. "2024-09-03" or "2024.9.4").
5. approved roles: {approval_roles}. Only fill person if explicitly named in the document.
6. validation_items: include {val_items}. Set checked=true if the document shows it was performed.
7. impact_analysis items: the "value" field must be "yes" or "no" based on checkbox state.
8. If the text mentions "No" or "否" next to a checkbox item, value = "no".
9. Preserve Chinese text exactly as written. Do not translate.
10. If the same field appears multiple times, use the first occurrence."""


def _build_user_prompt(md_text: str) -> str:
    truncated = md_text[:MAX_INPUT_CHARS]
    if len(md_text) > MAX_INPUT_CHARS:
        truncated += f"\n\n[... {len(md_text) - MAX_INPUT_CHARS} more characters truncated]"
    return f"Extract the PD-ECR structured data from this markdown:\n\n```markdown\n{truncated}\n```"


def _clean_json_response(content: str) -> str:
    """Strip markdown fences and extract pure JSON."""
    content = content.strip()
    # Remove ```json ... ``` fences
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
    return content


def extract_via_llm(md_text: str) -> dict | None:
    """Run LLM-based structured extraction.

    Returns the parsed JSON dict, or None if LLM is unavailable / fails.
    """
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-4.1")

    if not api_key:
        logger.info("LLM_API_KEY not set — skipping LLM extraction")
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.info("openai package not installed — skipping LLM extraction")
        return None

    cleaned = clean_text(md_text)
    if not cleaned.strip():
        return None

    client = OpenAI(api_key=api_key, base_url=base_url)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_prompt(cleaned)},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
    except Exception as exc:
        logger.warning("LLM extraction call failed: %s", exc)
        return None

    raw = response.choices[0].message.content or ""
    json_text = _clean_json_response(raw)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        # Try to salvage partial JSON
        logger.warning("LLM returned invalid JSON, attempting to salvage")
        # Find the outermost braces
        m = re.search(r"\{.*\}", json_text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        logger.warning("Could not parse LLM response as JSON")
        return None


def extract_with_llm_fallback(
    md_text: str,
    rule_based_extractor=None,
) -> dict:
    """Try LLM extraction first, fall back to rule-based if LLM fails.

    Args:
        md_text: Cleaned MinerU markdown.
        rule_based_extractor: Callable that takes md_text and returns a dict.
                              If None, returns an empty dict on LLM failure.

    Returns:
        Structured PD-ECR dict.
    """
    result = extract_via_llm(md_text)
    if result is not None:
        logger.info("LLM extraction succeeded")
        return result

    logger.info("LLM extraction failed or unavailable — using rule-based fallback")
    if rule_based_extractor is not None:
        return rule_based_extractor(md_text)

    return {}
