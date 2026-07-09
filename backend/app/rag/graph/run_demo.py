"""跑通 PD-ECR 生成流程的最小示例。

用法（在 backend/ 目录下）::

    python -m app.rag.graph.run_demo

会走一遍 classify -> retrieve -> impact_analysis -> validation_plan
-> implementation_plan，并打印各模块产出。
"""

from __future__ import annotations

import json
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()  # 加载 backend/.env 里的 LLM_API_KEY 等
except Exception:
    pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


SAMPLE_REQUEST = {
    "customer_project": "示例项目 A",
    "mcr_no": "MCR-2025-001",
    "product_no": "P-12345",
    "component_no": "C-67890",
    "reason": "原供应商密封圈材料停产，需替换为等效material。",
    "current_design": "使用 NBR 材质密封圈，硬度 70 Shore A。",
    "change_proposal": "改用 HNBR 材质密封圈，硬度 75 Shore A，接口尺寸不变。",
    "remarks": "需评估耐温和耐介质性能变化。",
}


def main() -> None:
    from app.rag.graph import build_pd_ecr_graph

    graph = build_pd_ecr_graph()
    result = graph.invoke({"request": SAMPLE_REQUEST})

    print("\n===== change_type =====")
    print(result.get("change_type"))

    print("\n===== 检索命中 =====")
    for r in result.get("retrieved", []):
        print(f"  [{r['score']:.3f}] {r['source']}")

    for module in ("impact_analysis", "validation_plan", "implementation_plan"):
        print(f"\n===== {module} =====")
        print(json.dumps(result.get(module, {}), ensure_ascii=False, indent=2))

    if result.get("errors"):
        print("\n===== errors =====")
        for e in result["errors"]:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
