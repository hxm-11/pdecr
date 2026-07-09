"""LangGraph 节点实现。

每个节点是一个纯函数：接收 state，返回要合并进 state 的局部更新（dict）。
LangGraph 会自动做浅合并。

目前完整实现了 classify -> retrieve -> impact_analysis -> self_check 主链，
validation_plan / implementation_plan 已给出可直接启用的实现，
在 graph.py 里按需接线即可。
"""

from __future__ import annotations

from typing import Any, Dict

from app.rag.retrieval import retrieve_cases
from app.rag.retrieval.retriever import build_context

from .llm import get_chat_model
from .schemas import (
    ChangeClassification,
    ImpactAnalysisResult,
    ImplementationPlanResult,
    ValidationPlanResult,
)

MAX_RETRIES = 2

# 影响分析的 8 个固定维度（来自 pdecr_schema.IMPACT_ANALYSIS_ITEMS）
IMPACT_KEYS = [
    "function_performance",
    "interface_appearance",
    "reliability_robustness",
    "other_components",
    "manufacturing_assembly_testing",
    "supplier_part",
    "system_hw_sw_calibration",
    "cost",
]


def _bump_retry(state: Dict[str, Any], key: str) -> Dict[str, int]:
    retries = dict(state.get("retries") or {})
    retries[key] = retries.get(key, 0) + 1
    return retries


# ──────────────────────────────────────────────────────────────
# 1. classify —— 判定变更类型
# ──────────────────────────────────────────────────────────────
def classify_node(state: Dict[str, Any]) -> Dict[str, Any]:
    request = state.get("request", {})
    model = get_chat_model().with_structured_output(ChangeClassification)

    prompt = (
        "你是汽车零部件工程变更（PD-ECR）专家。根据下面的变更请求，判断变更类型。\n\n"
        f"变更理由：{request.get('reason', '')}\n"
        f"当前设计：{request.get('current_design', '')}\n"
        f"变更方案：{request.get('change_proposal', '')}\n"
    )
    try:
        result: ChangeClassification = model.invoke(prompt)
        return {"change_type": result.change_type}
    except Exception as exc:
        return {"change_type": "generic", "errors": [f"classify: {exc}"]}


# ──────────────────────────────────────────────────────────────
# 2. retrieve —— 检索相似历史案例
# ──────────────────────────────────────────────────────────────
def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    request = dict(state.get("request", {}))
    if state.get("change_type"):
        request["_change_type_category"] = state["change_type"]

    chunks = retrieve_cases(request, top_k=5)
    context = build_context(chunks)

    return {
        "retrieved": [
            {"source": c.source, "score": c.score, "text": c.text} for c in chunks
        ],
        "context": context,
    }


# ──────────────────────────────────────────────────────────────
# 3. impact_analysis —— 生成影响分析
# ──────────────────────────────────────────────────────────────
def impact_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    request = state.get("request", {})
    context = state.get("context", "")
    model = get_chat_model().with_structured_output(ImpactAnalysisResult)

    prompt = (
        "你是 PD-ECR 影响分析专家。请针对本次变更，逐一评估以下 8 个维度是否受影响，"
        "并给出中文依据。必须覆盖全部维度：\n"
        f"{', '.join(IMPACT_KEYS)}\n\n"
        "== 本次变更 ==\n"
        f"变更理由：{request.get('reason', '')}\n"
        f"当前设计：{request.get('current_design', '')}\n"
        f"变更方案：{request.get('change_proposal', '')}\n\n"
        "== 相似历史案例（参考）==\n"
        f"{context or '（无检索结果，请基于工程常识判断）'}\n"
    )
    try:
        result: ImpactAnalysisResult = model.invoke(prompt)
        return {"impact_analysis": result.model_dump()}
    except Exception as exc:
        return {
            "impact_analysis": {},
            "retries": _bump_retry(state, "impact_analysis"),
            "errors": [f"impact_analysis: {exc}"],
        }


def impact_self_check(state: Dict[str, Any]) -> str:
    """条件边：检查影响分析是否覆盖全部 8 个维度。

    返回下一个节点名：不合格且还有重试次数 -> 回 impact_analysis，
    否则 -> 结束（或后续模块）。
    """
    result = state.get("impact_analysis") or {}
    items = result.get("items") or []
    covered = {it.get("key") for it in items}
    complete = set(IMPACT_KEYS).issubset(covered)

    retries = (state.get("retries") or {}).get("impact_analysis", 0)
    if not complete and retries < MAX_RETRIES:
        return "retry"
    return "ok"


# ──────────────────────────────────────────────────────────────
# 4.（可选）validation_plan —— 验证计划
# ──────────────────────────────────────────────────────────────
def validation_plan_node(state: Dict[str, Any]) -> Dict[str, Any]:
    request = state.get("request", {})
    context = state.get("context", "")
    model = get_chat_model().with_structured_output(ValidationPlanResult)

    prompt = (
        "你是 PD-ECR 验证计划专家。根据本次变更和影响分析，判断需要哪些验证项"
        "（Trial Run / CMK / MSA / BOM check / Test report / PAV release 等），"
        "并说明原因。\n\n"
        f"变更方案：{request.get('change_proposal', '')}\n"
        f"影响分析：{state.get('impact_analysis', {}).get('summary', '')}\n"
        f"参考案例：\n{context}\n"
    )
    try:
        result: ValidationPlanResult = model.invoke(prompt)
        return {"validation_plan": result.model_dump()}
    except Exception as exc:
        return {"validation_plan": {}, "errors": [f"validation_plan: {exc}"]}


# ──────────────────────────────────────────────────────────────
# 5.（可选）implementation_plan —— 各部门实施计划
# ──────────────────────────────────────────────────────────────
def implementation_plan_node(state: Dict[str, Any]) -> Dict[str, Any]:
    request = state.get("request", {})
    model = get_chat_model().with_structured_output(ImplementationPlanResult)

    prompt = (
        "你是 PD-ECR 实施计划专家。根据本次变更和影响分析，为相关部门"
        "（Development/Purchasing/MFE/COS/Quality/CPJM/MOEX/LOG）分配实施动作。\n\n"
        f"变更方案：{request.get('change_proposal', '')}\n"
        f"影响分析：{state.get('impact_analysis', {}).get('summary', '')}\n"
    )
    try:
        result: ImplementationPlanResult = model.invoke(prompt)
        return {"implementation_plan": result.model_dump()}
    except Exception as exc:
        return {"implementation_plan": {}, "errors": [f"implementation_plan: {exc}"]}
