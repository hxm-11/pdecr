"""PD-ECR 知识库入库 CLI。

用法（backend/ 目录）::

    # MinerU 解析产物（*.md，可配同名 *.json）
    python scripts/ingest_pdecr_knowledge.py \
        --input app/rag/knowledge_base/raw --type mineru

    # Excel 源
    python scripts/ingest_pdecr_knowledge.py \
        --input app/rag/excel_source --type excel

    # 自动识别（同时扫 excel 与 mineru）
    python scripts/ingest_pdecr_knowledge.py --input some/dir --type auto

行为：
  - 打印每个文件的处理状态；成功显示 case_id，失败显示原因。
  - 单个文件失败不会中断整批（错误记入 registry）。
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许直接 `python scripts/ingest_pdecr_knowledge.py` 运行（把 backend/ 加进 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="PD-ECR 知识库入库")
    parser.add_argument("--input", required=True, help="输入目录")
    parser.add_argument(
        "--type",
        default="auto",
        choices=["auto", "mineru", "excel", "word"],
        help="来源类型",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="入库成功后重建 FAISS/LangChain 向量索引，使新知识立即可检索",
    )
    args = parser.parse_args()

    # 独立运行时加载 .env（LLM/embedding 配置）
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    from app.rag.ingestion.pipeline import ingest_case_directory
    from app.rag.ingestion.registry import Registry

    input_dir = args.input
    if not Path(input_dir).exists():
        print(f"[error] 输入目录不存在: {input_dir}")
        return 2

    print(f"开始入库: input={input_dir} type={args.type}")
    reg = Registry()
    cases = ingest_case_directory(input_dir, args.type, registry=reg, verbose=True)

    print("\n==== 汇总 ====")
    print(f"本次成功入库 case 数: {len(cases)}")
    failed = [e for e in reg.all_entries() if e.status == "failed"]
    if failed:
        print(f"失败 {len(failed)} 个：")
        for e in failed:
            print(f"  - {e.source_file}: {e.error_message}")

    if args.rebuild_index and cases:
        print("\n开始重建检索索引...")
        from app.rag.ingest import rebuild_index

        if rebuild_index():
            print("检索索引重建完成，新入库知识已进入 FAISS/BM25 主检索链路。")
        else:
            print("检索索引重建未完成，请检查 app/rag/vector_store/pd_ecr_rebuild_status.json。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
