"""组装 PD-ECR 生成流程图。

当前主链：
    classify -> retrieve -> impact_analysis -> (self_check)
                                                  |  不合格且有重试 -> 回 impact_analysis
                                                  |  合格 -> validation_plan -> implementation_plan -> END

要精简成"只跑影响分析"，把 impact_self_check 的 "ok" 分支直接指到 END 即可。
要加新模块，照着 validation_plan 再加一个 node + 一条 edge。
"""

from __future__ import annotations

from .nodes import (
    classify_node,
    impact_analysis_node,
    impact_self_check,
    implementation_plan_node,
    retrieve_node,
    validation_plan_node,
)
from .state import PdEcrState


def build_pd_ecr_graph():
    """构建并编译 LangGraph。返回可 .invoke(state) 的图对象。"""
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(PdEcrState)

    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("impact_analysis", impact_analysis_node)
    builder.add_node("validation_plan", validation_plan_node)
    builder.add_node("implementation_plan", implementation_plan_node)

    builder.add_edge(START, "classify")
    builder.add_edge("classify", "retrieve")
    builder.add_edge("retrieve", "impact_analysis")

    # 自检：影响分析没覆盖全 8 维度 -> 重跑；否则进入验证计划
    builder.add_conditional_edges(
        "impact_analysis",
        impact_self_check,
        {"retry": "impact_analysis", "ok": "validation_plan"},
    )

    builder.add_edge("validation_plan", "implementation_plan")
    builder.add_edge("implementation_plan", END)

    return builder.compile()
