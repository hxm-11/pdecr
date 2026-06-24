"""
Parse MinerU-generated markdown into structured metadata.

MinerU v3 outputs markdown with tables like:

    | DC No | PD-ECR-0016 |
    | Date  | 2025-03-15  |

This module extracts those tables and maps field headers to internal keys.
"""

from __future__ import annotations

import re
from typing import Any


# ── Field mapping: MinerU / Docling table headers → internal field names ──

MINERU_FIELD_MAP: dict[str, str] = {
    # ── Core identifiers ──
    "DC No": "dc_no",
    "DC No.": "dc_no",
    "Design Change RequestNo": "dc_no",
    "Design Change RequestNo.": "dc_no",
    "RequestNo": "dc_no",
    "RequestNo.": "dc_no",
    "MCR No": "mcr_no",
    "MCR No.": "mcr_no",
    "MCRNo": "mcr_no",
    "MCRNo.": "mcr_no",
    "MCR号": "mcr_no",
    # ── Dates ──
    "Date": "date",
    "日期": "date",
    "Effective date": "date",
    "Effectivedate": "date",
    "Create Date": "create_date",
    "Target Close date": "target_close_date",
    # ── Customer / Project ──
    "Customer project": "customer_project",
    "Customer project Name": "customer_project",
    "CustomerprojectName": "customer_project",
    "客户项目名称": "customer_project",
    # ── Product / Part ──
    "Product No": "product_no",
    "Product No.": "product_no",
    "Component No": "part_no",
    "Component No.": "part_no",
    "Part No": "part_no",
    "Part No.": "part_no",
    "Change part & product Name": "part_name",
    "Changepart&productName": "part_name",
    "更改零部件产品的名称": "part_name",
    # ── Change type & source ──
    "Change type": "change_type",
    "Change Type": "change_type",
    "Sample status": "sample_type",
    "Samplestatus": "sample_type",
    "样件状态": "sample_type",
    "Change from": "change_source",
    "Changefrom": "change_source",
    "变更来源": "change_source",
    # ── Initiator ──
    "Initiator": "initiator",
    "发起人": "initiator",
    "Design": "initiator",
    "设计工程师": "initiator",
    # ── Reason ──
    "Reason of changes": "reason",
    "Reason of change": "reason",
    "Reasonofchanges": "reason",
    "更改理由": "reason",
    # ── Change proposal ──
    "Change proposal": "change_proposal",
    "Current design": "current_design",
    "Remarks": "remarks",
    # ── Change inform to ──
    "Change inform to": "change_inform_to",
    "Changeinformto": "change_inform_to",
    "变更通知人": "change_inform_to",
}


def _clean_key(raw: str) -> str:
    """Normalise a table header cell for matching."""
    return re.sub(r"\s+", " ", str(raw or "")).strip()


def _clean_value(raw: str) -> str:
    """Normalise a table value cell."""
    text = str(raw or "").strip()
    # Drop checkbox markers that sometimes appear in value cells
    text = re.sub(r"\[x\]|\[ \]|\[X\]|☑|☐|☒", "", text)
    return text.strip()


def _is_separator_row(cells: list[str]) -> bool:
    """True if this row is a markdown table separator like |---|---|."""
    if not cells:
        return False
    return all(
        re.fullmatch(r":?-{2,}:?", cell.strip())
        for cell in cells
    )


def parse_markdown_tables(md_text: str) -> dict[str, str]:
    """Extract key-value pairs from all markdown tables in the text.

    Handles tables with 2+ columns where the first column is a field name
    and subsequent columns are values.  Also handles multi-row tables where
    the same header row applies to multiple data rows.

    Returns a flat dict of normalised internal field names to cleaned values.
    """
    results: dict[str, str] = {}
    lines = md_text.splitlines()

    headers: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # ── Detect table rows ──
        if not stripped.startswith("|") or not stripped.endswith("|"):
            in_table = False
            headers = []
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]

        # Skip separator rows
        if _is_separator_row(cells):
            continue

        if not in_table:
            # First row of a table → treat as header
            headers = [_clean_key(c) for c in cells]
            in_table = True
            continue

        # ── Data row inside a table ──
        if not headers:
            continue

        # Align cell count to header count (some tables have ragged rows)
        aligned = cells + [""] * (len(headers) - len(cells))
        aligned = aligned[: len(headers)]

        # Build row dict from headers
        row_dict = dict(zip(headers, aligned))

        # Map known headers to internal field names
        for raw_key, raw_value in row_dict.items():
            clean_key = _clean_key(raw_key)
            clean_val = _clean_value(raw_value)

            if not clean_val:
                continue

            internal_key = MINERU_FIELD_MAP.get(clean_key)
            if internal_key:
                # Only set if not already filled (first occurrence wins —
                # header rows tend to be the most authoritative)
                if internal_key not in results:
                    results[internal_key] = clean_val

    return results


# ── Fallback: key-value line extraction (Docling / structured-md style) ──

_KV_PATTERNS: list[tuple[str, str]] = [
    # Key: Value  (English)
    (r"^(DC\s*No\.?)\s*[:：]\s*(.+)", "dc_no"),
    (r"^(Design\s+Change\s+Request\s*No\.?)\s*[:：]\s*(.+)", "dc_no"),
    (r"^(Request\s*No\.?)\s*[:：]\s*(.+)", "dc_no"),
    (r"^(MCR\s*No\.?)\s*[:：]\s*(.+)", "mcr_no"),
    (r"^(Date)\s*[:：]\s*(.+)", "date"),
    (r"^(Effective\s*date)\s*[:：]\s*(.+)", "date"),
    (r"^(Customer\s*project\s*(?:Name)?)\s*[:：]\s*(.+)", "customer_project"),
    (r"^(Product\s*No\.?)\s*[:：]\s*(.+)", "product_no"),
    (r"^(Component\s*No\.?)\s*[:：]\s*(.+)", "part_no"),
    (r"^(Part\s*No\.?)\s*[:：]\s*(.+)", "part_no"),
    (r"^(Change\s*part\s*[&＆]\s*product\s*Name)\s*[:：]\s*(.+)", "part_name"),
    (r"^(Sample\s*status)\s*[:：]\s*(.+)", "sample_type"),
    (r"^(Change\s*type)\s*[:：]\s*(.+)", "change_type"),
    (r"^(Change\s*from)\s*[:：]\s*(.+)", "change_source"),
    (r"^(Reason\s*of\s*changes?)\s*[:：]\s*(.+)", "reason"),
    (r"^(Change\s*proposal)\s*[:：]\s*(.+)", "change_proposal"),
    (r"^(Current\s*design)\s*[:：]\s*(.+)", "current_design"),
    (r"^(Initiator)\s*[:：]\s*(.+)", "initiator"),
    # Key: Value  (Chinese)
    (r"^(客户项目名称)\s*[:：]\s*(.+)", "customer_project"),
    (r"^(产品号)\s*[:：]\s*(.+)", "product_no"),
    (r"^(更改理由)\s*[:：]\s*(.+)", "reason"),
    (r"^(变更来源)\s*[:：]\s*(.+)", "change_source"),
    (r"^(变更通知人)\s*[:：]\s*(.+)", "change_inform_to"),
    (r"^(发起人)\s*[:：]\s*(.+)", "initiator"),
    (r"^(日期)\s*[:：]\s*(.+)", "date"),
]


def parse_key_value_lines(md_text: str) -> dict[str, str]:
    """Extract key-value pairs from ``Key: Value`` or ``Key：Value`` lines.

    This is a fallback for Docling-style output where metadata fields are
    not in markdown tables but appear as standalone lines.
    """
    results: dict[str, str] = {}

    for line in md_text.splitlines():
        for pattern, internal_key in _KV_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                value = match.group(2).strip()
                if value and internal_key not in results:
                    results[internal_key] = value
                break  # first matching pattern for this line

    return results


# ── Unified entry point ──


def extract_structured_metadata(
    md_text: str,
    *,
    include_kv_fallback: bool = True,
) -> dict[str, str]:
    """Extract metadata from MinerU / Docling markdown text.

    Strategy (in priority order):
    1. Markdown tables (MinerU primary output format)
    2. Key-value lines (Docling / structured-md fallback)

    Returns a flat dict of internal field names to values.
    """
    if not md_text or not md_text.strip():
        return {}

    # ── Tier 1: Markdown tables ──
    table_meta = parse_markdown_tables(md_text)

    if include_kv_fallback:
        # ── Tier 2: Key-value lines (lower priority — only fills gaps) ──
        kv_meta = parse_key_value_lines(md_text)
        for key, value in kv_meta.items():
            if key not in table_meta:
                table_meta[key] = value

    return table_meta


# ── Helpers for downstream consumers ──


def extract_case_no(md_text: str, fallback: str = "") -> str:
    """Try to extract a PD-ECR case number from markdown."""
    meta = extract_structured_metadata(md_text)
    case_no = meta.get("dc_no") or meta.get("case_no") or ""
    if case_no:
        # Normalise: "24_093" → "PDECR24_093"
        if not case_no.lower().startswith("pdecr"):
            case_no = f"PDECR{case_no}"
        return case_no.replace("-", "_")
    return fallback


def extract_metadata_for_ingest(md_text: str) -> dict[str, Any]:
    """Convenience wrapper that returns a dict suitable for
    passing as ``table_metadata`` to ``extract_metadata()`` in
    ``pd_ecr_import_service.py``.
    """
    return extract_structured_metadata(md_text)
