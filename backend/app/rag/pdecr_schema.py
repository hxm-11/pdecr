"""
PD-ECR template field schema.

Defines every field in a PD-ECR form organised by section, so the
structured extractor can produce clean JSON with the right keys.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────
# Section 0 — Document identification
# ──────────────────────────────────────────────────────────────

IDENTIFICATION_FIELDS = {
    "dc_no": {
        "label": "DC No",
        "aliases": ["Design Change RequestNo", "RequestNo", "DC No."],
        "type": "text",
    },
    "mcr_no": {
        "label": "MCR No",
        "aliases": ["MCR No.", "MCRNo", "MCR号"],
        "type": "text",
    },
    "date": {
        "label": "Date",
        "aliases": ["Effective date", "Effectivedate", "日期"],
        "type": "text",
    },
    "customer_project": {
        "label": "Customer project",
        "aliases": ["Customer project Name", "CustomerprojectName", "客户项目名称"],
        "type": "text",
    },
    "product_no": {
        "label": "Product No",
        "aliases": ["Product No.", "产品号"],
        "type": "text",
    },
    "part_no": {
        "label": "Part No / Component No",
        "aliases": ["Component No.", "ComponentNo", "Part No.", "零部件号", "更改零部件产品的名称"],
        "type": "text",
    },
    "sample_type": {
        "label": "Sample status",
        "aliases": ["Samplestatus", "样件状态", "Sample type"],
        "type": "text",
    },
    "initiator": {
        "label": "Initiator",
        "aliases": ["发起人", "Design", "设计工程师"],
        "type": "text",
    },
    "change_type": {
        "label": "Change type",
        "aliases": ["Change Type"],
        "type": "text",
    },
}

# ──────────────────────────────────────────────────────────────
# Section 1 — Change request
# ──────────────────────────────────────────────────────────────

CHANGE_REQUEST_FIELDS = {
    "change_source": {
        "label": "Change from",
        "aliases": ["Changefrom", "变更来源"],
        "type": "text",
    },
    "reason": {
        "label": "Reason of changes",
        "aliases": ["Reason of change", "Reasonofchanges", "更改理由"],
        "type": "text",
    },
    "change_proposal": {
        "label": "Change proposal",
        "aliases": ["变更描述", "Change description"],
        "type": "text",
    },
    "current_design": {
        "label": "Current design",
        "aliases": [],
        "type": "text",
    },
    "change_inform_to": {
        "label": "Change inform to",
        "aliases": ["Changeinformto", "变更通知人"],
        "type": "text",
    },
}

# ──────────────────────────────────────────────────────────────
# Section 3.1 — Impact analysis (checkbox grid)
# ──────────────────────────────────────────────────────────────

IMPACT_ANALYSIS_ITEMS = [
    {
        "key": "function_performance",
        "label": "Function & Performance",
        "zh": "产品功能性能影响",
    },
    {
        "key": "interface_appearance",
        "label": "Interface and Appearance",
        "zh": "接口和外观影响",
    },
    {
        "key": "reliability_robustness",
        "label": "Reliability and robustness",
        "zh": "产品可靠性、鲁棒性影响",
    },
    {
        "key": "other_components",
        "label": "Other components",
        "zh": "其他零部件影响",
    },
    {
        "key": "manufacturing_assembly_testing",
        "label": "Manufacturing / assembly / testing",
        "zh": "加工、装配、测试影响",
    },
    {
        "key": "supplier_part",
        "label": "Supplier part",
        "zh": "供应商零件影响",
    },
    {
        "key": "system_hw_sw_calibration",
        "label": "System / HW / SW / Calibration / Mechanical",
        "zh": "系统/硬件/软件/标定/机械影响",
    },
    {
        "key": "cost",
        "label": "Influence on cost",
        "zh": "对成本的影响",
    },
]

# ──────────────────────────────────────────────────────────────
# Section 3.3 — Affected documents (checkbox grid)
# ──────────────────────────────────────────────────────────────

AFFECTED_DOCUMENTS_ITEMS = [
    {"key": "interface_fmea", "label": "Interface FMEA / IFMEA", "zh": "接口FMEA"},
    {"key": "product_fmea", "label": "Product FMEA / DFMEA", "zh": "产品FMEA"},
    {"key": "special_characteristics", "label": "Special Characteristics / PSC", "zh": "特殊特性"},
    {"key": "imds", "label": "IMDS", "zh": "IMDS"},
    {"key": "offer_drawing", "label": "Offer drawing", "zh": "报价图"},
    {"key": "tcd", "label": "TCD", "zh": "TCD"},
    {"key": "norm_wb_hf", "label": "Norm, WB, HF", "zh": "标准规范"},
    {"key": "wi_check", "label": "WI Check", "zh": "作业指导书"},
]

# ──────────────────────────────────────────────────────────────
# Section 3.2 — Validation items
# ──────────────────────────────────────────────────────────────

VALIDATION_ITEMS = [
    "Trial Run",
    "Capability Studies CMK",
    "Capability Studies MSA",
    "MAE release",
    "Cleanness test",
    "QZ test",
    "BOM check",
    "Test report",
    "PAV release",
    "Other",
]

# ──────────────────────────────────────────────────────────────
# Section 3.1.9 — Stock / Delivery treatment
# ──────────────────────────────────────────────────────────────

STOCK_DELIVERY_ITEMS = [
    {"key": "mixed_deliveries", "label": "Mixed Deliveries Permissible?"},
    {"key": "first_delivery", "label": "1st delivery after change"},
]

STOCK_DELIVERY_CATEGORIES = [
    "Raw materials",
    "Parts/Subassemble",
    "Finished goods (inhouse)",
    "Finished goods (RDCK)",
    "Finished goods (customer)",
]

# ──────────────────────────────────────────────────────────────
# Section 5/6 — Implementation plan
# ──────────────────────────────────────────────────────────────

IMPLEMENTATION_DEPARTMENTS = [
    "Development",
    "Purchasing",
    "MFE",
    "COS",
    "Quality",
    "CPJM",
    "MOEX",
    "LOG",
]

# ──────────────────────────────────────────────────────────────
# Section 4/7 — Approval / Signoff
# ──────────────────────────────────────────────────────────────

APPROVAL_ROLES = [
    {"key": "development", "role": "Development", "field": "approval_development_person"},
    {"key": "purchasing", "role": "Purchasing", "field": "approval_purchasing_person"},
    {"key": "mfe", "role": "MFE", "field": "approval_mfe_person"},
    {"key": "cos", "role": "COS", "field": "approval_cos_person"},
    {"key": "quality", "role": "Quality", "field": "approval_quality_person"},
    {"key": "cpjm", "role": "CPJM", "field": "approval_cpjm_person"},
    {"key": "moex", "role": "MOEX", "field": "approval_moex_person"},
    {"key": "log", "role": "LOG", "field": "approval_log_person"},
]

# ──────────────────────────────────────────────────────────────
# Output schema (what staged document metadata_json should look like)
# ──────────────────────────────────────────────────────────────

OUTPUT_SCHEMA = {
    "identification": IDENTIFICATION_FIELDS,
    "change_request": CHANGE_REQUEST_FIELDS,
    "impact_analysis": {
        "items": IMPACT_ANALYSIS_ITEMS,
        "stock_delivery": STOCK_DELIVERY_CATEGORIES,
    },
    "affected_documents": AFFECTED_DOCUMENTS_ITEMS,
    "validation_items": VALIDATION_ITEMS,
    "approval": APPROVAL_ROLES,
}
