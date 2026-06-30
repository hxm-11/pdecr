from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PdEcrModuleId(str, Enum):
    BASIC_INFORMATION = "basic_information"
    CHANGE_DESCRIPTION = "change_description"
    REASON_FOR_CHANGE = "reason_for_change"
    IMPACT_ANALYSIS = "impact_analysis"
    IMPLEMENTATION_PLAN = "implementation_plan"
    APPROVAL_SIGNOFF_INFORMATION = "approval_signoff_information"


class RetrievalMode(str, Enum):
    FAISS = "faiss"
    KEYWORD_FALLBACK = "keyword_fallback"
    HYBRID_KEYWORD = "hybrid_keyword"
    HYBRID = "hybrid"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChangeTypeCategory(str, Enum):
    """PD-ECR change type taxonomy derived from 20 historical cases.

    Categories represent the nature of the engineering change, not the
    specific part/product — enabling cross-project pattern migration.
    """

    FIRST_SAMPLE_RELEASE = "first_sample_release"
    TEST_SAMPLE_RELEASE = "test_sample_release"
    CUSTOMER_BOUNDARY_ADJUSTMENT = "customer_boundary_adjustment"
    COST_REDUCTION_COMPONENT = "cost_reduction_component"
    DESIGN_OPTIMIZATION = "design_optimization"
    SUPPLIER_PROCESS_CHANGE = "supplier_process_change"
    PRODUCTION_SPEC_RELEASE = "production_spec_release"
    PRODUCTION_SAMPLE_RELEASE = "production_sample_release"
    COMPONENT_MODIFICATION = "component_modification"
    INSPECTION_LABEL_CHANGE = "inspection_label_change"
    UNKNOWN = "unknown"


class SampleStage(str, Enum):
    A_SAMPLE = "A"
    B_SAMPLE = "B"
    C_SAMPLE = "C"
    D_SAMPLE = "D"


class ExportFormat(str, Enum):
    HTML = "html"
    CSV = "csv"


class DraftStatus(str, Enum):
    V1_MVP_DRAFT = "V1_MVP_DRAFT"


REQUIRED_METADATA_KEYS: tuple[str, ...] = (
    "case_id",
    "dc_no",
    "mcr_no",
    "change_type",
    "product_no",
    "part_no",
    "customer_project",
    "source_file",
)

V1_MODULE_IDS: tuple[PdEcrModuleId, ...] = (
    PdEcrModuleId.BASIC_INFORMATION,
    PdEcrModuleId.CHANGE_DESCRIPTION,
    PdEcrModuleId.REASON_FOR_CHANGE,
    PdEcrModuleId.IMPACT_ANALYSIS,
    PdEcrModuleId.IMPLEMENTATION_PLAN,
    PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION,
)

MODULE_TITLES: dict[PdEcrModuleId, str] = {
    PdEcrModuleId.BASIC_INFORMATION: "Change Request description",
    PdEcrModuleId.CHANGE_DESCRIPTION: "Affection analysis",
    PdEcrModuleId.REASON_FOR_CHANGE: "Validation & Trial Run Results",
    PdEcrModuleId.IMPACT_ANALYSIS: "Validation &Trial run plan result",
    PdEcrModuleId.IMPLEMENTATION_PLAN: "Implementation task plan",
    PdEcrModuleId.APPROVAL_SIGNOFF_INFORMATION: "Implementation result",
}


def get_required_metadata_keys() -> tuple[str, ...]:
    return REQUIRED_METADATA_KEYS


def get_v1_module_ids() -> tuple[PdEcrModuleId, ...]:
    return V1_MODULE_IDS


def normalize_new_pd_ecr_input(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)

    if "change_source" not in normalized and "source" in normalized:
        normalized["change_source"] = normalized.get("source")
    normalized.pop("source", None)

    if "part_no" not in normalized and "component_no" in normalized:
        normalized["part_no"] = normalized.get("component_no")
    normalized.pop("component_no", None)

    if "change_reason" not in normalized and "reason" in normalized:
        normalized["change_reason"] = normalized.get("reason")
    normalized.pop("reason", None)

    if "change_description" not in normalized:
        normalized["change_description"] = (
            normalized.get("change_description")
            or normalized.get("change_proposal")
            or normalized.get("current_design")
            or ""
        )

    allowed_keys = {
        "dc_no",
        "mcr_no",
        "customer_project",
        "product_no",
        "part_no",
        "change_type",
        "change_description",
        "change_reason",
        "change_source",
        "target_close_date",
        "date",
        "initiator",
        "current_design",
        "change_proposal",
        "remarks",
        "top_k",
    }
    return {key: value for key, value in normalized.items() if key in allowed_keys}


class PdEcrBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HistoricalMetadata(PdEcrBaseModel):
    case_id: str
    dc_no: str = ""
    mcr_no: str = ""
    change_type: str = ""
    product_no: str = ""
    part_no: str = ""
    customer_project: str | list[str] = ""
    source_file: str
    date: str = ""
    initiator: str = ""
    sample_status: str | list[str] = ""
    sample_type: str = ""
    reason_for_change: str = ""

    @field_validator("case_id", "source_file")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value


class HistoricalModule(PdEcrBaseModel):
    module_id: PdEcrModuleId
    title: str
    summary: str = ""
    content: str = ""
    source_file: str
    source_pages: list[int] = Field(default_factory=list)
    confidence: ConfidenceLevel | None = None

    @field_validator("title", "source_file")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value


class SourceTrace(PdEcrBaseModel):
    pdf_page: list[int] = Field(default_factory=list)
    raw_md_path: str = ""
    confidence: ConfidenceLevel | None = None
    need_human_check: list[str] = Field(default_factory=list)


class HistoricalCase(PdEcrBaseModel):
    case_id: str
    metadata: HistoricalMetadata
    modules: dict[PdEcrModuleId, HistoricalModule] = Field(default_factory=dict)
    source_file: str
    source_trace: SourceTrace | dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("case_id", "source_file")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def metadata_matches_case(self) -> "HistoricalCase":
        if self.metadata.case_id != self.case_id:
            raise ValueError("metadata.case_id must match case_id")
        if self.metadata.source_file != self.source_file:
            raise ValueError("metadata.source_file must match source_file")
        return self


class NewPdEcrRequest(PdEcrBaseModel):
    dc_no: str = ""
    mcr_no: str = ""
    customer_project: str = ""
    product_no: str = ""
    part_no: str = ""
    change_type: str = ""
    change_description: str
    change_reason: str
    change_source: str = ""
    target_close_date: str = ""
    date: str = ""
    initiator: str = ""
    current_design: str = ""
    change_proposal: str = ""
    remarks: str = ""
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator(
        "change_description",
        "change_reason",
    )
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @classmethod
    def from_legacy_input(cls, data: dict[str, Any]) -> "NewPdEcrRequest":
        return cls.model_validate(normalize_new_pd_ecr_input(data))


class EvidenceSnippet(PdEcrBaseModel):
    source_file: str
    case_id: str
    text: str
    module_id: PdEcrModuleId | None = None
    page: int | None = None
    confidence: ConfidenceLevel | None = None

    @field_validator("source_file", "case_id", "text")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value


class RetrievalContext(PdEcrBaseModel):
    matched_fields: list[str] = Field(default_factory=list)
    keyword_hits: list[str] = Field(default_factory=list)
    semantic_score: float | None = None
    metadata_score: float | None = None
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    module_summary: str = ""


class SimilarCaseResult(PdEcrBaseModel):
    rank: int = Field(ge=1)
    case_id: str
    dc_no: str = ""
    change_type: str = ""
    matched_fields: list[str] = Field(default_factory=list)
    similarity_score: float
    similarity_reason: str = ""
    source_file: str
    module_summary: str
    source_cases: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    retrieval_context: RetrievalContext = Field(default_factory=RetrievalContext)
    pattern_category: str = ""

    @field_validator("case_id", "source_file", "module_summary")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def ensure_source_reference(self) -> "SimilarCaseResult":
        if self.case_id not in self.source_cases:
            self.source_cases.append(self.case_id)
        if self.source_file not in self.source_files:
            self.source_files.append(self.source_file)
        return self


class GeneratedModule(PdEcrBaseModel):
    module_id: PdEcrModuleId
    title: str
    summary: str = ""
    content: str | dict[str, Any]
    source_cases: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    needs_human_input: bool = False
    warnings: list[str] = Field(default_factory=list)
    applied_patterns: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value


class GeneratedDraft(PdEcrBaseModel):
    draft_id: str
    draft_status: DraftStatus = DraftStatus.V1_MVP_DRAFT
    input_snapshot: NewPdEcrRequest
    similar_cases: list[SimilarCaseResult] = Field(default_factory=list)
    modules: list[GeneratedModule]
    report_url: str = ""
    generated_at: str

    @field_validator("draft_id", "generated_at")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def require_six_v1_modules(self) -> "GeneratedDraft":
        module_ids = [module.module_id for module in self.modules]
        expected = set(V1_MODULE_IDS)
        if set(module_ids) != expected or len(module_ids) != len(V1_MODULE_IDS):
            raise ValueError("generated draft must contain exactly the six V1 modules")
        return self


class ClassificationResult(PdEcrBaseModel):
    """Result of classifying a new PD-ECR request into ChangeTypeCategory."""

    category: ChangeTypeCategory
    confidence: ConfidenceLevel
    matched_triggers: list[str] = Field(default_factory=list)
    sample_stage: SampleStage | None = None
    classification_method: str = "rule"  # "rule" or "llm"
    needs_llm_fallback: bool = False


class BasicReportExport(PdEcrBaseModel):
    export_id: str
    draft_id: str
    format: ExportFormat
    draft_status: DraftStatus = DraftStatus.V1_MVP_DRAFT
    input_snapshot: NewPdEcrRequest | None = None
    similar_cases: list[SimilarCaseResult] = Field(default_factory=list)
    modules: list[GeneratedModule] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    download_url: str = ""
    created_at: str

    @field_validator("export_id", "draft_id", "created_at")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("field must not be empty")
        return value
