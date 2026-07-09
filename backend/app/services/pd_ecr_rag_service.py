"""PD-ECR RAG 生成服务（供后端其它代码直接调用，无需走 HTTP 接口）。

用法::

    from app.services.pd_ecr_rag_service import generate_pd_ecr

    result = generate_pd_ecr({
        "reason": "...",
        "current_design": "...",
        "change_proposal": "...",
    })
    result["impact_analysis"]        # dict
    result["validation_plan"]        # dict
    result["implementation_plan"]    # dict
    result["retrieved"]              # list[{source, score, text}]

底层是 app.rag.graph 的 LangGraph 流程：
    classify -> retrieve -> impact_analysis -(自检)-> validation_plan -> implementation_plan

- 图只编译一次并缓存（编译开销小，但没必要每次重来）。
- 提供同步 generate_pd_ecr 和异步 agenerate_pd_ecr（在线程池跑，供 async 路由用）。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, TypedDict


class PdEcrRagResult(TypedDict, total=False):
    change_type: str
    retrieved: List[Dict[str, Any]]
    impact_analysis: Dict[str, Any]
    validation_plan: Dict[str, Any]
    implementation_plan: Dict[str, Any]
    errors: List[str]


# 支持的输入字段（与 app.rag.retrieval / pdecr_schema 对齐）
_REQUEST_FIELDS = (
    "customer_project",
    "mcr_no",
    "product_no",
    "component_no",
    "initiator",
    "reason",
    "current_design",
    "change_proposal",
    "remarks",
)


@lru_cache(maxsize=1)
def _get_graph():
    """编译并缓存 LangGraph（首次调用时构建）。"""
    from app.rag.graph import build_pd_ecr_graph

    return build_pd_ecr_graph()


def _clean_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """只保留已知字段，避免把无关键塞进 state。"""
    return {k: request.get(k, "") for k in _REQUEST_FIELDS if request.get(k) is not None}


def _to_result(state: Dict[str, Any]) -> PdEcrRagResult:
    return PdEcrRagResult(
        change_type=state.get("change_type", ""),
        retrieved=state.get("retrieved", []),
        impact_analysis=state.get("impact_analysis", {}),
        validation_plan=state.get("validation_plan", {}),
        implementation_plan=state.get("implementation_plan", {}),
        errors=state.get("errors", []),
    )


def generate_pd_ecr(request: Dict[str, Any]) -> PdEcrRagResult:
    """跑完整 RAG 生成流程，返回各模块结构化结果（同步）。

    request 可用字段见 _REQUEST_FIELDS；缺字段会被当空串处理。
    """
    graph = _get_graph()
    state = graph.invoke({"request": _clean_request(request)})
    return _to_result(state)


async def agenerate_pd_ecr(request: Dict[str, Any]) -> PdEcrRagResult:
    """异步版：在线程池里跑同步图，供 async 路由/服务直接 await。"""
    import anyio

    return await anyio.to_thread.run_sync(generate_pd_ecr, request)
