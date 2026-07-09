"""标准 PD-ECR Case Schema（知识库主数据格式）。

所有来源（MinerU 解析的 PDF、Excel、Word、系统表单导出）都必须先转换成
这里定义的 :class:`PdecrCase`，再由它渲染 Markdown / 切 chunk / 建索引。

设计原则：
  - 字段允许为空，但结构固定（缺失字段写 None / 空数组，禁止编造）。
  - 每个重要字段尽量保留 evidence / source_text，方便人工追溯。
  - 提供 model_dump_json 保存 + validate_case() 体检。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# 业务模块名（chunk_type 与 markdown 章节都以此为准）
MODULE_NAMES: tuple[str, ...] = (
    "change_reason",
    "current_design",
    "change_proposal",
    "impact_analysis",
    "validation_plan",
    "implementation_plan",
    "risk_analysis",
    "approval_summary",
    "remarks",
)

# normalize / 校验时期望尽量补齐的关键元数据字段
_KEY_METADATA_FIELDS: tuple[str, ...] = (
    "dc_no",
    "date",
    "customer_project",
    "affected_product_no",
    "component_no",
)


class SourceInfo(BaseModel):
    """来源文件信息，用于追溯原始材料。"""

    source_file: str | None = None
    file_type: str | None = None  # pdf / xlsx / docx / db_export ...
    parser: str | None = None  # mineru / excel / word / db_export ...
    raw_markdown_path: str | None = None
    raw_json_path: str | None = None
    checksum: str | None = None


class PdecrMetadata(BaseModel):
    """案例头部元数据。多值字段统一为 list[str]（见 normalizer）。"""

    dc_no: str | None = None
    date: str | None = None  # YYYY-MM-DD
    mcr_no: str | None = None
    customer_project: list[str] = Field(default_factory=list)
    affected_product_no: list[str] = Field(default_factory=list)
    component_no: list[str] = Field(default_factory=list)
    initiator: str | None = None
    department: str | None = None
    product_family: str | None = None
    change_type: str | None = None


class PdecrModules(BaseModel):
    """九大业务模块正文。抽不到写 None。"""

    change_reason: str | None = None
    current_design: str | None = None
    change_proposal: str | None = None
    impact_analysis: str | None = None
    validation_plan: str | None = None
    implementation_plan: str | None = None
    risk_analysis: str | None = None
    approval_summary: str | None = None
    remarks: str | None = None


class ImpactDepartment(BaseModel):
    department: str | None = None
    is_impacted: bool | None = None
    impact_content: str | None = None
    responsible_person: str | None = None
    evidence: str | None = None


class PdecrTask(BaseModel):
    task_name: str | None = None
    owner: str | None = None
    department: str | None = None
    plan: str | None = None
    result: str | None = None
    status: str | None = None
    evidence: str | None = None


class AttachmentInfo(BaseModel):
    file_name: str | None = None
    file_type: str | None = None
    related_module: str | None = None
    path: str | None = None


class QualityControl(BaseModel):
    """抽取质量 / 人工复核信号。"""

    extraction_status: str = "pending"  # pending / partial / complete / failed
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float | None = None  # 0~1
    needs_human_review: bool = True
    errors: list[str] = Field(default_factory=list)


class PdecrCase(BaseModel):
    """标准 PD-ECR 案例（知识库主数据）。"""

    case_id: str
    source: SourceInfo = Field(default_factory=SourceInfo)
    metadata: PdecrMetadata = Field(default_factory=PdecrMetadata)
    modules: PdecrModules = Field(default_factory=PdecrModules)
    impact_departments: list[ImpactDepartment] = Field(default_factory=list)
    tasks: list[PdecrTask] = Field(default_factory=list)
    attachments: list[AttachmentInfo] = Field(default_factory=list)
    quality_control: QualityControl = Field(default_factory=QualityControl)

    # ── 保存 ──
    def to_json(self, *, indent: int = 2) -> str:
        """序列化为 JSON 字符串（UTF-8 友好，保留中文）。"""
        return self.model_dump_json(indent=indent)

    def save(self, path: str) -> None:
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> PdecrCase:
        from pathlib import Path

        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def validate_case(case: PdecrCase) -> dict[str, Any]:
    """体检一个 case，返回 missing_fields 与 warnings。

    只报告缺失，不修改 case（是否需要人工复核由 normalizer 依此写入
    quality_control）。
    """
    missing_fields: list[str] = []
    warnings: list[str] = []

    if not case.case_id:
        missing_fields.append("case_id")

    md = case.metadata
    for field_name in _KEY_METADATA_FIELDS:
        value = getattr(md, field_name)
        if value in (None, "", []):
            missing_fields.append(f"metadata.{field_name}")

    modules = case.modules
    filled_modules = [
        name for name in MODULE_NAMES if (getattr(modules, name) or "").strip()
    ]
    if not filled_modules:
        warnings.append("no module content extracted")
    for name in MODULE_NAMES:
        if not (getattr(modules, name) or "").strip():
            missing_fields.append(f"modules.{name}")

    if not case.source.source_file:
        missing_fields.append("source.source_file")

    return {
        "missing_fields": missing_fields,
        "warnings": warnings,
        "filled_modules": filled_modules,
    }
