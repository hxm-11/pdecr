"""PD-ECR 生成流程的 LangGraph 编排层。

用法::

    from app.rag.graph import build_pd_ecr_graph

    graph = build_pd_ecr_graph()
    result = graph.invoke({"request": {...}})
    print(result["impact_analysis"])
"""

from .graph import build_pd_ecr_graph

__all__ = ["build_pd_ecr_graph"]
