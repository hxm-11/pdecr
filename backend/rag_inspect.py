"""RAG 诊断脚本：把检索/生成的内部信号摊开，用于人工验证效果。

用法（backend/ 目录）：
    python rag_inspect.py                 # 用内置示例请求
    python rag_inspect.py --full          # 额外跑完整 LangGraph（分类+影响分析+验证+实施）
    python rag_inspect.py --k 8           # 每路召回条数

会分别打印：
  1) 稠密向量检索（真实余弦/内积分数，越大越相似）——判断 embedding 召回质量看这个
  2) BM25 关键词检索（真实 BM25 分数）
  3) EnsembleRetriever 融合后的最终排序（RRF，注意它不回传融合分，只看排序）
  4) --full 时：change_type + 影响分析/验证/实施各模块摘要

不打印密钥。
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()

# 内置示例变更请求（可改成你自己的真实 case）
SAMPLE_REQUEST = {
    "customer_project": "JP360",
    "product_no": "'F03ZS0000B-04",
    "component_no": "F03Z20046V-01",
    "reason": "导油环回油口处未设计倒角，入机壳时导油环发生卡滞，压装不到位",
    "current_design": "回油口无倒角",
    "change_proposal": "回油口增加：C角1x45°和圆角R1",
    "remarks": "回油口增加C角和圆角，避免压装发生卡滞",
}


def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def inspect_retrieval(request: dict, k: int) -> None:
    from app.rag.retrieval.retriever import (
        _LC_STORE_DIR,
        build_query,
        retrieve_cases,
    )

    query = build_query(request)
    print("\n【检索用 query】\n" + query)

    # ---- 1) 稠密向量检索：真实分数 ----
    _print_header(f"1. 稠密向量检索 (text-embedding-3-small)  top-{k}  —— 分数=内积≈余弦，越大越相似")
    try:
        from langchain_community.vectorstores import FAISS

        from app.rag.retrieval.embeddings import get_embeddings

        store = FAISS.load_local(
            str(_LC_STORE_DIR), get_embeddings(), allow_dangerous_deserialization=True
        )
        dense_hits = store.similarity_search_with_score(query, k=k)
        for rank, (doc, score) in enumerate(dense_hits, start=1):
            src = doc.metadata.get("source", "")
            print(f"  #{rank:<2} score={score:.4f}  {src[:70]}")
    except Exception as exc:
        print(f"  稠密检索失败：{exc}")

    # ---- 2) BM25 关键词检索：真实分数 ----
    _print_header(f"2. BM25 关键词检索  top-{k}  —— 分数=BM25，越大越相关")
    try:
        from langchain_community.retrievers import BM25Retriever
        from langchain_community.vectorstores import FAISS

        from app.rag.retrieval.embeddings import get_embeddings

        store = FAISS.load_local(
            str(_LC_STORE_DIR), get_embeddings(), allow_dangerous_deserialization=True
        )
        all_docs = list(store.docstore._dict.values())
        import numpy as np

        bm25 = BM25Retriever.from_documents(all_docs)
        # 直接取底层打分，才能看到真实分数（Retriever 接口本身不回传分）
        tokenized = bm25.preprocess_func(query)
        scores = bm25.vectorizer.get_scores(tokenized)
        top_idx = np.argsort(scores)[::-1][:k]
        for rank, idx in enumerate(top_idx, start=1):
            src = all_docs[idx].metadata.get("source", "")
            print(f"  #{rank:<2} score={scores[idx]:.4f}  {src[:70]}")
    except Exception as exc:
        print(f"  BM25 检索失败：{exc}")

    # ---- 3) 融合后的最终排序（真实融合分）----
    _print_header(
        f"3. 融合最终排序 (稠密0.4 / BM25 0.6，各自归一化后加权)  top-{k}\n"
        "   fused=最终分(0~1)  d=稠密归一化  b=BM25归一化，均越大越好"
    )
    hits = retrieve_cases(request, top_k=k)
    for rank, c in enumerate(hits, start=1):
        m = c.metadata or {}
        print(
            f"  #{rank:<2} fused={c.score:.4f}  "
            f"(d={m.get('_dense_score', 0):.3f} b={m.get('_bm25_score', 0):.3f})  "
            f"{c.source[:60]}"
        )


def inspect_full_graph(request: dict) -> None:
    _print_header("4. 完整 LangGraph 生成结果")
    from app.services.pd_ecr_rag_service import generate_pd_ecr

    result = generate_pd_ecr(request)

    print(f"\n变更类型 change_type: {result.get('change_type', '')}")

    print("\n-- 召回案例（进入生成的上下文）--")
    for r in result.get("retrieved", []):
        print(f"   [{r.get('score', 0):.3f}] {r.get('source', '')[:70]}")

    impact = result.get("impact_analysis", {}) or {}
    print("\n-- 影响分析 impact_analysis --")
    print(f"   摘要: {impact.get('summary', '')[:200]}")
    for it in impact.get("items", []) or []:
        affected = it.get("affected")
        print(f"   [{'受影响' if affected else '不受影响'}] {it.get('key', '')}: {str(it.get('reason', ''))[:80]}")

    vp = result.get("validation_plan", {}) or {}
    print("\n-- 验证计划 validation_plan --")
    print(f"   {str(vp)[:300]}")

    ip = result.get("implementation_plan", {}) or {}
    print("\n-- 实施计划 implementation_plan --")
    print(f"   {str(ip)[:300]}")

    errs = result.get("errors", []) or []
    if errs:
        print("\n-- 错误 errors --")
        for e in errs:
            print(f"   ! {e}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="额外跑完整 LangGraph 生成")
    parser.add_argument("--k", type=int, default=5, help="每路召回条数")
    args = parser.parse_args()

    inspect_retrieval(SAMPLE_REQUEST, k=args.k)
    if args.full:
        inspect_full_graph(SAMPLE_REQUEST)


if __name__ == "__main__":
    main()
