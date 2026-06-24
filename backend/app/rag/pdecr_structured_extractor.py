"""
Template-aware structured extractor for PD-ECR documents.

Pipeline:
  MinerU markdown
    → section detection (heading patterns)
    → field extraction (markdown tables + key-value lines)
    → structured JSON (matching pdecr_schema.OUTPUT_SCHEMA)
    → row-level chunks (with section/field/page metadata)
"""

from __future__ import annotations

import re
from typing import Any

from app.rag.pdecr_schema import (
    IDENTIFICATION_FIELDS,
    CHANGE_REQUEST_FIELDS,
    IMPACT_ANALYSIS_ITEMS,
    AFFECTED_DOCUMENTS_ITEMS,
    VALIDATION_ITEMS,
    IMPLEMENTATION_DEPARTMENTS,
    APPROVAL_ROLES,
)
from app.rag.text_cleaner import clean_text


# ────────────────────────────────────────────────
# Section detection patterns
# ────────────────────────────────────────────────

_SECTION_MARKERS: list[tuple[str, str]] = [
    # (regex pattern, section_name)
    (r"(?:Step\s*3\.1|Impact\s*[Aa]nalysis|影响分析)", "impact_analysis"),
    (r"(?:Step\s*3\.2|Validation|Quality\s*Assurance|验证项目)", "validation_items"),
    (r"(?:Step\s*3\.3|Affected\s*[Dd]ocuments|受影响文件|Document\s*[Ii]tem)", "affected_documents"),
    (r"(?:Step\s*3\.1\.9|Stock.*Delivery|库存.*发货|Mixed\s*Deliveries)", "stock_delivery"),
    (r"(?:Step\s*[56]|Implementation|实施计划|Implementation\s*task)", "implementation"),
    (r"(?:Step\s*[47]\s*Approval|Signature|Sign.off|审批|签字)", "approval"),
    (r"(?:Reason\s*of\s*changes?|更改理由|变更原因)", "change_request"),
    (r"(?:Change\s*from|变更来源)", "change_request"),
]


def _detect_sections(md_text: str) -> dict[str, str]:
    """Split markdown into named sections based on heading/content patterns."""
    lines = md_text.splitlines()
    sections: dict[str, list[str]] = {}
    current_section = "_header"
    sections[current_section] = []

    for line in lines:
        matched = None
        for pattern, name in _SECTION_MARKERS:
            if re.search(pattern, line, re.I):
                matched = name
                break
        if matched:
            current_section = matched
            if current_section not in sections:
                sections[current_section] = []
        sections[current_section].append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


# ────────────────────────────────────────────────
# Table-value extraction
# ────────────────────────────────────────────────

def _parse_table(text: str) -> list[dict[str, str]]:
    """Parse a markdown table region into list of row dicts."""
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue  # separator row
        if not headers:
            headers = cells
        elif cells:
            row = dict(zip(headers, cells + [""] * (len(headers) - len(cells))))
            rows.append(row)

    return rows


def _extract_checkbox_value(cell_text: str) -> str | None:
    """Infer yes/no from a table cell containing checkbox markers."""
    if any(m in cell_text for m in ("☑", "☒", "√", "✓", "[x]", "[X]", "checked")):
        return "yes"
    if any(m in cell_text for m in ("☐", "[ ]", "[  ]")):
        return "no"
    t = cell_text.strip().lower()
    if t in ("yes", "是", "no", "否"):
        return t
    return None


# ────────────────────────────────────────────────
# Main extractor
# ────────────────────────────────────────────────

def extract_structured(md_text: str) -> dict[str, Any]:
    """Extract structured PD-ECR data from MinerU markdown.

    Returns a dict matching the OUTPUT_SCHEMA structure.
    """
    cleaned = clean_text(md_text)
    sections = _detect_sections(cleaned)
    all_text = cleaned  # fallback for global search

    result: dict[str, Any] = {
        "identification": {},
        "change_request": {},
        "impact_analysis": {"items": [], "stock_delivery": []},
        "affected_documents": [],
        "validation_items": [],
        "implementation": [],
        "approval": [],
        "raw_sections": list(sections.keys()),
    }

    # ── Identification fields ──
    result["identification"] = _extract_identification(all_text, sections)

    # ── Change request ──
    cr_text = sections.get("change_request", all_text)
    result["change_request"] = _extract_change_request(cr_text, all_text)

    # ── Impact analysis (table-driven) ──
    ia_text = sections.get("impact_analysis", "")
    stock_text = sections.get("stock_delivery", "")
    result["impact_analysis"]["items"] = _extract_impact_items(
        ia_text or all_text
    )
    result["impact_analysis"]["stock_delivery"] = _extract_stock_delivery(
        stock_text or ia_text or all_text
    )

    # ── Affected documents ──
    ad_text = sections.get("affected_documents", "")
    result["affected_documents"] = _extract_affected_documents(ad_text or all_text)

    # ── Validation items ──
    val_text = sections.get("validation_items", "")
    result["validation_items"] = _extract_validation_items(val_text or all_text)

    # ── Implementation ──
    impl_text = sections.get("implementation", "")
    result["implementation"] = _extract_implementation(impl_text or all_text)

    # ── Approval ──
    app_text = sections.get("approval", "")
    result["approval"] = _extract_approval(app_text or all_text)

    return result


def _find_field(text: str, spec: dict) -> str:
    """Try to find a field value from text using aliases."""
    # Try markdown table key-value
    for line in text.splitlines():
        low = line.lower()
        for alias in [spec["label"]] + spec.get("aliases", []):
            if alias.lower() in low:
                # Table cell pattern: | alias | value |
                if "|" in line:
                    cells = [c.strip() for c in line.split("|") if c.strip()]
                    for i, c in enumerate(cells):
                        if alias.lower() in c.lower() and i + 1 < len(cells):
                            return cells[i + 1]
                # Key: value pattern
                m = re.search(rf"{re.escape(alias)}\s*[:：]\s*(.+)", line, re.I)
                if m:
                    return m.group(1).strip()
    return ""


def _extract_identification(all_text: str, sections: dict) -> dict:
    header = sections.get("_header", all_text)
    result = {}
    for key, spec in IDENTIFICATION_FIELDS.items():
        val = _find_field(header, spec)
        if val:
            result[key] = val
    return result


def _extract_change_request(section_text: str, all_text: str) -> dict:
    result = {}
    for key, spec in CHANGE_REQUEST_FIELDS.items():
        val = _find_field(section_text, spec)
        if not val:
            val = _find_field(all_text, spec)
        if val:
            result[key] = val
    return result


def _extract_impact_items(text: str) -> list[dict]:
    """Match impact-analysis checkbox rows against IMPACT_ANALYSIS_ITEMS."""
    items = []
    for item_def in IMPACT_ANALYSIS_ITEMS:
        entry = {
            "key": item_def["key"],
            "label": item_def["label"],
            "zh": item_def["zh"],
            "value": "",
            "remark": "",
            "confirmed_by": "",
        }
        for line in text.splitlines():
            low = line.lower()
            keywords = [item_def["label"].lower(), item_def["zh"].lower()]
            if not any(kw in low for kw in keywords):
                continue
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                for i, c in enumerate(cells):
                    v = _extract_checkbox_value(c)
                    if v:
                        entry["value"] = v
                if len(cells) >= 5:
                    entry["confirmed_by"] = cells[-1] if not _extract_checkbox_value(cells[-1]) else cells[-2]
                entry["remark"] = cells[-1] if len(cells) >= 3 else ""
            else:
                # Inline checkbox pattern: "No ☐  Yes ☑"
                if re.search(r"(?:yes|是).*?(☑|☒|√|✓|\[x\])", line, re.I):
                    entry["value"] = "yes"
                elif re.search(r"(?:no|否).*?(☑|☒|√|✓|\[x\])", line, re.I):
                    entry["value"] = "no"
            break
        items.append(entry)
    return items


def _extract_affected_documents(text: str) -> list[dict]:
    items = []
    for doc_def in AFFECTED_DOCUMENTS_ITEMS:
        entry = {
            "key": doc_def["key"],
            "label": doc_def["label"],
            "value": "",
            "responsible": "",
            "due_date": "",
        }
        for line in text.splitlines():
            low = line.lower()
            keywords = [doc_def["label"].lower(), doc_def["zh"].lower()]
            if not any(kw in low for kw in keywords):
                continue
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                for c in cells:
                    v = _extract_checkbox_value(c)
                    if v:
                        entry["value"] = v
                if len(cells) >= 5:
                    entry["responsible"] = cells[-2] if len(cells) >= 5 else ""
                    entry["due_date"] = cells[-1] if len(cells) >= 6 else ""
            break
        items.append(entry)
    return items


def _extract_validation_items(text: str) -> list[dict]:
    items = []
    for val_name in VALIDATION_ITEMS:
        entry = {"name": val_name, "checked": False, "finish_date": "", "responsible": "", "comment": ""}
        for line in text.splitlines():
            if val_name.lower() in line.lower():
                entry["checked"] = any(m in line for m in ("☑", "☒", "√", "✓", "[x]", "[X]"))
                if "|" in line:
                    cells = [c.strip() for c in line.split("|") if c.strip()]
                    if len(cells) >= 3:
                        entry["finish_date"] = cells[2] if len(cells) > 2 else ""
                    if len(cells) >= 4:
                        entry["responsible"] = cells[3] if len(cells) > 3 else ""
                break
        items.append(entry)
    return items


def _extract_stock_delivery(text: str) -> list[dict]:
    """Extract stock/delivery treatment rows."""
    items = []
    categories = [
        ("Raw materials", "原材料"),
        ("Parts/Subassemble", "零件/分总成"),
        ("Finished goods (inhouse)", "厂内成品"),
        ("Finished goods (RDCK)", "RDCK外库成品"),
        ("Finished goods (customer)", "客户处成品"),
    ]
    for label, zh in categories:
        entry = {"label": label, "zh": zh, "treatment": "", "remark": ""}
        for line in text.splitlines():
            if label.lower() in line.lower() or zh in line:
                if "|" in line:
                    cells = [c.strip() for c in line.split("|") if c.strip()]
                    # Look for checkbox-marked treatment option
                    for i, c in enumerate(cells):
                        v = _extract_checkbox_value(c)
                        if v == "yes":
                            # The cell before this one is likely the treatment label
                            if i > 0:
                                entry["treatment"] = cells[i - 1]
                            elif i + 1 < len(cells):
                                entry["treatment"] = cells[i + 1]
                    if len(cells) >= 6:
                        entry["remark"] = cells[-1]
                break
        items.append(entry)
    return items


def _extract_implementation(text: str) -> list[dict]:
    """Extract implementation plan rows keyed by department."""
    items = []
    for dept in IMPLEMENTATION_DEPARTMENTS:
        entry = {"department": dept, "yn": "", "description": "", "responsible": "", "due_date": ""}
        for line in text.splitlines():
            if dept.lower() in line.lower() and "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2:
                    entry["yn"] = cells[1] if len(cells) > 1 else ""
                if len(cells) >= 3:
                    entry["description"] = cells[2] if len(cells) > 2 else ""
                if len(cells) >= 4:
                    entry["responsible"] = cells[3] if len(cells) > 3 else ""
                if len(cells) >= 5:
                    entry["due_date"] = cells[4] if len(cells) > 4 else ""
                break
        items.append(entry)
    return items


def _extract_approval(text: str) -> list[dict]:
    """Extract approval/signoff rows."""
    items = []
    for role in APPROVAL_ROLES:
        entry = {"role": role["role"], "person": "", "date": ""}
        patterns = [
            role["role"].lower(),
            role["key"],
        ]
        for line in text.splitlines():
            low = line.lower()
            if not any(p in low for p in patterns):
                continue
            if "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                for i, c in enumerate(cells):
                    if any(p in c.lower() for p in patterns) and i + 1 < len(cells):
                        entry["person"] = cells[i + 1]
                        if i + 2 < len(cells):
                            entry["date"] = cells[i + 2]
            else:
                m = re.search(rf"({'|'.join(map(re.escape, patterns))})\s*[:：]\s*(.+)", line, re.I)
                if m:
                    entry["person"] = m.group(2).strip()
            break
        items.append(entry)
    return items


# ────────────────────────────────────────────────
# Row-level chunk builder
# ────────────────────────────────────────────────

def build_row_chunks(structured: dict[str, Any], source_file: str, file_id: str) -> list[dict[str, Any]]:
    """Convert structured PD-ECR JSON into row-level chunks with metadata.

    Each chunk is a self-contained piece of text with its section, field,
    and source metadata — ready for embedding into FAISS.
    """
    chunks: list[dict[str, Any]] = []
    chunk_idx = 0
    base_meta = {
        "file_id": file_id,
        "source_file": source_file,
        "document_type": "pdecr_structured",
    }

    def _add(section: str, field: str, text: str, page_no: int = 1, **extra):
        nonlocal chunk_idx
        if not text or not text.strip():
            return
        chunks.append({
            **base_meta,
            "chunk_index": chunk_idx,
            "section": section,
            "field": field,
            "page_no": page_no,
            "text": text.strip(),
            **extra,
        })
        chunk_idx += 1

    # ── Identification ──
    for key, val in structured.get("identification", {}).items():
        spec = IDENTIFICATION_FIELDS.get(key, {})
        label = spec.get("label", key)
        _add("identification", key, f"{label}: {val}" if val else "")

    # ── Change request ──
    for key, val in structured.get("change_request", {}).items():
        spec = CHANGE_REQUEST_FIELDS.get(key, {})
        label = spec.get("label", key)
        _add("change_request", key, f"{label}: {val}" if val else "")

    # ── Impact analysis — one chunk per item row ──
    for item in structured.get("impact_analysis", {}).get("items", []):
        text = (
            f"{item.get('label', '')} ({item.get('zh', '')})\n"
            f"Impact: {item.get('value', 'N/A')}\n"
            f"Remark: {item.get('remark', '')}\n"
            f"Confirmed by: {item.get('confirmed_by', '')}"
        )
        _add("impact_analysis", item.get("key", ""), text)

    # ── Affected documents — one chunk per doc row ──
    for doc in structured.get("affected_documents", []):
        text = (
            f"{doc.get('label', '')}\n"
            f"Affected: {doc.get('value', 'N/A')}\n"
            f"Responsible: {doc.get('responsible', '')}\n"
            f"Due: {doc.get('due_date', '')}"
        )
        _add("affected_documents", doc.get("key", ""), text)

    # ── Validation items — one chunk per validation ──
    for val in structured.get("validation_items", []):
        text = (
            f"Validation: {val.get('name', '')}\n"
            f"Required: {'Yes' if val.get('checked') else 'No'}\n"
            f"Finish: {val.get('finish_date', '')}\n"
            f"Resp: {val.get('responsible', '')}\n"
            f"Comment: {val.get('comment', '')}"
        )
        _add("validation_items", val.get("name", ""), text)

    # ── Implementation — one chunk per department ──
    for impl in structured.get("implementation", []):
        text = (
            f"Department: {impl.get('department', '')}\n"
            f"Required: {impl.get('yn', '')}\n"
            f"Description: {impl.get('description', '')}\n"
            f"Responsible: {impl.get('responsible', '')}\n"
            f"Due: {impl.get('due_date', '')}"
        )
        _add("implementation", impl.get("department", ""), text)

    # ── Approval — one chunk per role ──
    for app in structured.get("approval", []):
        text = (
            f"Approver: {app.get('role', '')}\n"
            f"Person: {app.get('person', '')}\n"
            f"Date: {app.get('date', '')}"
        )
        _add("approval", app.get("role", ""), text)

    return chunks
