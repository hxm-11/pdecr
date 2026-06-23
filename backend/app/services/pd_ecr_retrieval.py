from __future__ import annotations

import json
import os
from typing import Any

from app.rag.retriever import retrieve_pd_ecr_results
from app.services.pd_ecr_case_loader import load_historical_cases
from app.services.pd_ecr_classifier import classify_change_type
from app.services.pd_ecr_patterns import (
    ChangeTypePattern,
    PatternLibrary,
    get_pattern,
    load_pattern_library,
)
from app.services.pd_ecr_schema import (
    ChangeTypeCategory,
    ClassificationResult,
    EvidenceSnippet,
    NewPdEcrRequest,
    RetrievalContext,
    RetrievalMode,
    SampleStage,
    SimilarCaseResult,
)

# Feature flag: set PD_ECR_USE_PATTERN_RETRIEVAL=true to enable pattern-based retrieval
_USE_PATTERN_RETRIEVAL = os.getenv("PD_ECR_USE_PATTERN_RETRIEVAL", "false").lower() in (
    "true",
    "1",
    "yes",
)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_sample_stage(text: str) -> str:
    """Return 'A','B','C','D' or empty string."""
    t = text.upper().replace(" ", "").replace("-", "")
    for stage in ("A", "B", "C", "D"):
        if f"{stage}SAMPLE" in t or f"{stage}SAMP" in t or f"{stage}样" in text:
            return stage
    return ""


def _stage_distance(stage_a: str, stage_b: str) -> int:
    """Return 0=same, 1=adjacent, 2+=further."""
    order = {"A": 0, "B": 1, "C": 2, "D": 3}
    return abs(order.get(stage_a, -1) - order.get(stage_b, -1))


def _pattern_relevance_score(
    request: NewPdEcrRequest,
    case_text: str,
    metadata: dict[str, Any],
    classification: ClassificationResult | None,
) -> tuple[float, list[str]]:
    """Score a historical case's relevance to a new request based on process patterns.

    Rewards:
    - Same sample stage: +0.10, adjacent stage: +0.05
    - Same change type category: +0.15
    - Risk profile overlap (review sheet sections): +0.08
    - Does NOT reward customer_project/product_no/part_no exact match
      (those are identifiers, not reusable knowledge).
    """
    score = 0.0
    matched: list[str] = []

    if classification is None:
        return score, matched

    # --- Sample stage matching ---
    request_stage = classification.sample_stage.value if classification.sample_stage else ""
    case_sample_status = _norm(
        metadata.get("sample_status")
        if isinstance(metadata.get("sample_status"), str)
        else " ".join(metadata.get("sample_status", []))
        if isinstance(metadata.get("sample_status"), list)
        else ""
    )
    case_stage = _extract_sample_stage(case_sample_status)

    if request_stage and case_stage:
        dist = _stage_distance(request_stage, case_stage)
        if dist == 0:
            score += 0.10
            matched.append(f"sample_stage:{request_stage}")
        elif dist == 1:
            score += 0.05
            matched.append(f"adjacent_stage:{request_stage}~{case_stage}")

    # --- Change type category matching ---
    if classification.category != ChangeTypeCategory.UNKNOWN:
        # Check if the case belongs to the same category
        # (we don't have case-level classification pre-computed, so we check
        #  against the reference_case_ids in the matched pattern)
        pattern = get_pattern(classification.category)
        if pattern and metadata.get("case_id") in pattern.reference_case_ids:
            score += 0.15
            matched.append(f"category:{classification.category.value}")

    # --- Risk profile overlap (keyword check on review sections) ---
    _review_keywords = [
        ("function_performance", ["功能", "性能", "function", "performance", "system impact"]),
        ("interface_boundary", ["接口", "边界", "interface", "boundary"]),
        ("mechanical_strength", ["机械强度", "耐久", "mechanical", "strength", "durability", "FEA"]),
        ("product_documents", ["FMEA", "IMDS", "TCD", "图纸", "drawing", "BOM", "document"]),
        ("stock_treatment", ["库存", "stock", "报废", "改制", "继续使用"]),
    ]
    request_risk_areas = set()
    combined_request = _norm(
        f"{request.change_description} {request.change_reason} {request.change_type}"
    )
    for area_key, keywords in _review_keywords:
        if any(kw in combined_request for kw in keywords):
            request_risk_areas.add(area_key)

    case_risk_areas = set()
    for area_key, keywords in _review_keywords:
        if any(kw in case_text for kw in keywords):
            case_risk_areas.add(area_key)

    if request_risk_areas and case_risk_areas:
        overlap = request_risk_areas & case_risk_areas
        if overlap:
            score += 0.08
            matched.append(f"risk_overlap:{','.join(sorted(overlap))}")

    return score, matched


# Legacy scoring (used when feature flag is off)
def _metadata_score(request: NewPdEcrRequest, case_text: str, metadata: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    matched: list[str] = []
    for field in ["customer_project", "product_no", "part_no", "change_type"]:
        value = _norm(getattr(request, field))
        if value and (value in case_text or value in _norm(metadata.get(field))):
            score += 0.12
            matched.append(field)
    for field in ["change_source", "change_description", "change_reason"]:
        for token in [item for item in _norm(getattr(request, field)).split() if len(item) >= 3][:8]:
            if token in case_text and field not in matched:
                score += 0.03
                matched.append(field)
    return score, matched


def retrieve_similar_cases(
    input_data: dict[str, Any],
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
) -> tuple[NewPdEcrRequest, list[SimilarCaseResult]]:
    request = NewPdEcrRequest.from_legacy_input({**input_data, "top_k": top_k})
    top_k = max(1, min(int(top_k or request.top_k or 5), 20))
    cases = load_historical_cases()

    # --- Classification (pattern-based retrieval only) ---
    classification: ClassificationResult | None = None
    library: PatternLibrary | None = None
    if _USE_PATTERN_RETRIEVAL:
        try:
            library = load_pattern_library()
            classification = classify_change_type(request, library)
        except Exception:
            classification = None

    raw_results: list[dict[str, Any]] = []
    try:
        query_data = request.model_dump()
        if classification is not None and classification.category != ChangeTypeCategory.UNKNOWN:
            query_data["_change_type_category"] = classification.category.value
        raw_results = retrieve_pd_ecr_results(query_data, top_k=max(top_k * 2, top_k))
    except Exception:
        raw_results = []

    by_source = {case.source_file: case for case in cases}
    by_case_id = {case.case_id: case for case in cases}
    candidates: list[tuple[float, Any, dict[str, Any], list[str]]] = []

    filters = filters or {}

    # --- Choose scoring function ---
    if _USE_PATTERN_RETRIEVAL and classification is not None:
        _score_fn = (
            lambda case_text, metadata: _pattern_relevance_score(
                request, case_text, metadata, classification
            )
        )
    else:
        _score_fn = (
            lambda case_text, metadata: _metadata_score(request, case_text, metadata)
        )

    # --- Score FAISS results ---
    for raw in raw_results:
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        source = str(raw.get("source") or metadata.get("source_file") or metadata.get("document_name") or "")
        case_id = str(metadata.get("case_id") or "")
        case = by_source.get(source) or by_case_id.get(case_id)
        if not case:
            continue
        case_text = json.dumps(case.model_dump(mode="json"), ensure_ascii=False).lower()
        if _filtered_out(filters, case.metadata.model_dump(mode="json")):
            continue
        meta_boost, matched = _score_fn(case_text, case.metadata.model_dump(mode="json"))
        base_score = float(raw.get("score") or 0.0)
        candidates.append((base_score + meta_boost, case, raw, matched))

    # --- Score remaining cases (keyword fallback) ---
    existing_case_ids = {case.case_id for _, case, _, _ in candidates}
    for case in cases:
        if case.case_id in existing_case_ids:
            continue
        metadata = case.metadata.model_dump(mode="json")
        if _filtered_out(filters, metadata):
            continue
        text = json.dumps(case.model_dump(mode="json"), ensure_ascii=False).lower()
        score, matched = _score_fn(text, metadata)
        fallback_score = score if score > 0 else 0.001
        candidates.append(
            (
                fallback_score,
                case,
                {"retrieval_mode": "keyword_fallback", "text": case.raw_text[:1200]},
                matched,
            )
        )

    # --- Layered sorting (pattern-based retrieval) ---
    if _USE_PATTERN_RETRIEVAL and classification is not None:
        # Separate type-matched from cross-type
        pattern = get_pattern(classification.category) if library else None
        type_matched_cases: list[tuple[float, Any, dict[str, Any], list[str]]] = []
        cross_type_cases: list[tuple[float, Any, dict[str, Any], list[str]]] = []

        all_cases = sorted(candidates, key=lambda item: item[0], reverse=True)
        for candidate in all_cases:
            _, case, _, _ = candidate
            if pattern and case.case_id in pattern.reference_case_ids:
                type_matched_cases.append(candidate)
            else:
                cross_type_cases.append(candidate)

        # Ensure at least min(3, top_k) type-matched, fill rest with cross-type
        min_type_matched = min(3, top_k)
        max_cross_type = top_k - min_type_matched

        layered: list[tuple[float, Any, dict[str, Any], list[str]]] = []
        layered.extend(type_matched_cases[:min_type_matched])
        layered.extend(cross_type_cases[:max_cross_type])

        # If still not enough, add more type-matched then cross-type
        remaining = top_k - len(layered)
        if remaining > 0:
            layered.extend(type_matched_cases[min_type_matched : min_type_matched + remaining])
        remaining = top_k - len(layered)
        if remaining > 0:
            layered.extend(cross_type_cases[max_cross_type : max_cross_type + remaining])

        candidates = layered
    else:
        candidates.sort(key=lambda item: item[0], reverse=True)

    results: list[SimilarCaseResult] = []
    seen: set[str] = set()
    for score, case, raw, matched in candidates:
        if case.case_id in seen:
            continue
        seen.add(case.case_id)
        modules_with_content = [module for module in case.modules.values() if module.content]
        module_summary = (
            modules_with_content[0].summary
            if modules_with_content
            else "Historical case has limited extracted module content."
        )
        text = str(raw.get("text") or case.raw_text or module_summary)
        result = SimilarCaseResult(
            rank=len(results) + 1,
            case_id=case.case_id,
            dc_no=case.metadata.dc_no,
            change_type=case.metadata.change_type,
            matched_fields=matched or ["keyword"],
            similarity_score=round(float(score), 4),
            similarity_reason=", ".join(matched) if matched else "Keyword / source-text similarity",
            source_file=case.source_file,
            module_summary=module_summary,
            retrieval_mode=RetrievalMode(str(raw.get("retrieval_mode") or "hybrid_keyword")),
            retrieval_context=RetrievalContext(
                matched_fields=matched,
                keyword_hits=matched,
                semantic_score=float(raw.get("score") or 0.0),
                metadata_score=round(float(score), 4),
                evidence_snippets=[
                    EvidenceSnippet(
                        source_file=case.source_file,
                        case_id=case.case_id,
                        text=text[:600] or module_summary,
                    )
                ],
                module_summary=module_summary,
            ),
            # Populate pattern category when known
            pattern_category=(
                classification.category.value
                if (
                    _USE_PATTERN_RETRIEVAL
                    and classification is not None
                    and pattern is not None
                    and case.case_id in pattern.reference_case_ids
                )
                else ""
            ),
        )
        results.append(result)
        if len(results) >= top_k:
            break

    return request, results


def _filtered_out(filters: dict[str, Any], metadata: dict[str, Any]) -> bool:
    for field, expected in filters.items():
        expected_text = _norm(expected)
        if not expected_text:
            continue
        if expected_text not in _norm(metadata.get(field)):
            return True
    return False
