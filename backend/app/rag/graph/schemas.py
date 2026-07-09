"""各模块 LLM 结构化输出的 Pydantic 模型。

字段对齐 app/rag/pdecr_schema.py，用于 model.with_structured_output(...)，
让 LLM 直接吐出结构化 JSON，而不是自由文本再解析。
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


# ── classify ──
class ChangeClassification(BaseModel):
    change_type: str = Field(description="变更类型的简短分类，如 材料变更/尺寸变更/供应商变更/工艺变更")
    rationale: str = Field(description="为什么这样分类，一两句话")


# ── impact_analysis（对应 IMPACT_ANALYSIS_ITEMS 8 个维度）──
class ImpactItem(BaseModel):
    key: str = Field(description="影响维度的 key，如 function_performance")
    label: str = Field(description="影响维度的英文名")
    impacted: bool = Field(description="该维度是否受影响")
    rationale: str = Field(description="判断依据，结合历史案例，中文")


class ImpactAnalysisResult(BaseModel):
    items: List[ImpactItem] = Field(description="逐个维度的影响判断")
    summary: str = Field(description="整体影响分析总结，中文")


# ── validation_plan（对应 VALIDATION_ITEMS）──
class ValidationTask(BaseModel):
    item: str = Field(description="验证项名称，如 Trial Run / BOM check")
    required: bool = Field(description="本次变更是否需要该验证项")
    note: str = Field(default="", description="补充说明")


class ValidationPlanResult(BaseModel):
    tasks: List[ValidationTask]
    summary: str = Field(default="", description="验证计划总结")


# ── implementation_plan（对应 IMPLEMENTATION_DEPARTMENTS）──
class DepartmentAction(BaseModel):
    department: str = Field(description="部门，如 Development / Purchasing / Quality")
    action: str = Field(description="该部门需要执行的动作")
    priority: Literal["high", "medium", "low"] = "medium"


class ImplementationPlanResult(BaseModel):
    actions: List[DepartmentAction]
    summary: str = Field(default="", description="实施计划总结")
