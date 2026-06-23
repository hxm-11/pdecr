"""PD-ECR Structured Pattern Knowledge Library.

Loads and queries the engineering change management pattern library
from patterns.json. Patterns represent reusable process knowledge
(independent of specific products, projects, or people) extracted from
historical PD-ECR cases.

Usage:
    from app.services.pd_ecr_patterns import (
        load_pattern_library,
        get_pattern,
        get_checklist_for_stage,
        get_risk_profile,
    )

    library = load_pattern_library()
    pattern = get_pattern(ChangeTypeCategory.FIRST_SAMPLE_RELEASE)
    checklist = get_checklist_for_stage("A", library)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.pd_ecr_schema import ChangeTypeCategory, SampleStage

_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "pd_ecr_patterns"
_PATTERNS_PATH = _DATA_DIR / "patterns.json"


class ChangeTypePattern:
    """A reusable engineering change management pattern."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    @property
    def category(self) -> ChangeTypeCategory:
        return ChangeTypeCategory(self._raw["category"])

    @property
    def label_cn(self) -> str:
        return self._raw.get("label_cn", "")

    @property
    def label_en(self) -> str:
        return self._raw.get("label_en", "")

    @property
    def description(self) -> str:
        return self._raw.get("description", "")

    @property
    def typical_triggers(self) -> list[str]:
        return self._raw.get("typical_triggers", [])

    @property
    def sample_stages(self) -> list[str]:
        return self._raw.get("sample_stages", [])

    @property
    def checklist_template(self) -> dict[str, list[str]]:
        return self._raw.get("checklist_template", {})

    @property
    def risk_profile(self) -> dict[str, str]:
        return self._raw.get("risk_profile", {})

    @property
    def required_verifications(self) -> list[str]:
        return self._raw.get("required_verifications", [])

    @property
    def required_approvals(self) -> list[str]:
        return self._raw.get("required_approvals", [])

    @property
    def affected_documents(self) -> list[str]:
        return self._raw.get("affected_documents", [])

    @property
    def reference_case_ids(self) -> list[str]:
        return self._raw.get("reference_case_ids", [])

    @property
    def common_mistakes(self) -> list[str]:
        return self._raw.get("common_mistakes", [])

    @property
    def implementation_guidance(self) -> str:
        return self._raw.get("implementation_guidance", "")

    def to_dict(self) -> dict[str, Any]:
        return dict(self._raw)


class PatternLibrary:
    """Complete pattern library — all patterns + shared templates."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.version: str = raw.get("version", "0.0.0")
        self.description: str = raw.get("description", "")
        self.patterns: list[ChangeTypePattern] = [
            ChangeTypePattern(p) for p in raw.get("patterns", [])
        ]
        self.review_sheet_template: dict[str, Any] = raw.get("review_sheet_template", {})
        self.sample_stage_checklists: dict[str, dict[str, Any]] = raw.get(
            "sample_stage_checklists", {}
        )
        self.approval_flow_template: dict[str, Any] = raw.get("approval_flow_template", {})

    def get_pattern(self, category: ChangeTypeCategory) -> ChangeTypePattern | None:
        """Get the pattern for a specific change type category."""
        for pattern in self.patterns:
            if pattern.category == category:
                return pattern
        return None

    def get_checklist(self, stage: str | SampleStage) -> dict[str, Any]:
        """Get the pre-condition checklist for a sample stage."""
        stage_key = stage.value if isinstance(stage, SampleStage) else str(stage)
        return self.sample_stage_checklists.get(stage_key, {})

    def get_review_section(self, section_key: str) -> dict[str, Any]:
        """Get a review sheet section by key (e.g. '1_function_performance')."""
        sections = self.review_sheet_template.get("sections", {})
        return sections.get(section_key, {})

    def get_approval_role(self, role_key: str) -> dict[str, Any]:
        """Get approval role info by key (e.g. 'design_engineer', 'pue')."""
        roles = self.approval_flow_template.get("roles", {})
        return roles.get(role_key, {})

    def pattern_count(self) -> int:
        return len(self.patterns)


# ---------------------------------------------------------------------------
# Module-level cache (loaded once on first access)
# ---------------------------------------------------------------------------

_library_cache: PatternLibrary | None = None


@lru_cache(maxsize=1)
def load_pattern_library() -> PatternLibrary:
    """Load the pattern library from JSON. Cached after first call."""
    global _library_cache

    if _library_cache is not None:
        return _library_cache

    if not _PATTERNS_PATH.exists():
        raise FileNotFoundError(
            f"Pattern library not found at {_PATTERNS_PATH}. "
            "Ensure patterns.json exists in backend/app/data/pd_ecr_patterns/."
        )

    raw = json.loads(_PATTERNS_PATH.read_text(encoding="utf-8"))
    _library_cache = PatternLibrary(raw)
    return _library_cache


def reload_pattern_library() -> PatternLibrary:
    """Force-reload the pattern library (useful during development)."""
    global _library_cache
    _library_cache = None
    load_pattern_library.cache_clear()
    return load_pattern_library()


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def get_pattern(category: ChangeTypeCategory) -> ChangeTypePattern | None:
    """Get a single pattern by category."""
    return load_pattern_library().get_pattern(category)


def get_checklist_for_stage(stage: str | SampleStage) -> dict[str, Any]:
    """Get the checklist template for a sample stage (A/B/C/D)."""
    return load_pattern_library().get_checklist(stage)


def get_risk_profile(category: ChangeTypeCategory) -> dict[str, str]:
    """Get the risk assessment profile for a change type."""
    pattern = get_pattern(category)
    if pattern is None:
        return {}
    return pattern.risk_profile


def get_affected_sections(category: ChangeTypeCategory) -> list[str]:
    """Get the review sheet sections typically affected by a change type.

    Returns a list of section keys like ['1_function_performance', '4_product_documents'].
    """
    pattern = get_pattern(category)
    if pattern is None:
        return []

    sections: list[str] = []
    risk_profile = pattern.risk_profile

    section_mapping = {
        "function_performance": "1_function_performance",
        "interface_boundary": "2_interface_boundary",
        "mechanical_strength": "3_mechanical_strength",
        "product_documents": "4_product_documents",
        "stock_treatment": "5_stock_treatment",
    }

    for risk_key, section_key in section_mapping.items():
        if risk_key in risk_profile:
            sections.append(section_key)

    return sections


def pattern_to_prompt_context(pattern: ChangeTypePattern) -> str:
    """Convert a pattern into a readable prompt context block.

    Used when building the LLM generation prompt to describe what
    process pattern should be migrated to the new change request.
    """
    lines = [
        f"## Pattern: {pattern.label_cn} ({pattern.label_en})",
        f"**Category:** {pattern.category.value}",
        f"**Applies to sample stages:** {', '.join(pattern.sample_stages)}",
        f"**Description:** {pattern.description}",
        "",
        "**Typical verification requirements:**",
    ]
    for v in pattern.required_verifications:
        lines.append(f"- {v}")

    lines.append("")
    lines.append("**Risk profile by review area:**")
    for area, guidance in pattern.risk_profile.items():
        lines.append(f"- {area}: {guidance}")

    lines.append("")
    lines.append("**Required approvals (roles, NOT names):**")
    for a in pattern.required_approvals:
        lines.append(f"- {a}")

    lines.append("")
    lines.append("**Affected documents:**")
    for d in pattern.affected_documents:
        lines.append(f"- {d}")

    if pattern.common_mistakes:
        lines.append("")
        lines.append("**Common mistakes to avoid:**")
        for m in pattern.common_mistakes:
            lines.append(f"- ⚠️ {m}")

    if pattern.implementation_guidance:
        lines.append("")
        lines.append(f"**Implementation guidance:** {pattern.implementation_guidance}")

    return "\n".join(lines)
