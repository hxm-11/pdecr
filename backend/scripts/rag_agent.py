"""PD-ECR RAG maintenance and evaluation agent.

Run from backend/:

    poetry run python scripts/rag_agent.py status
    poetry run python scripts/rag_agent.py sync --input app/rag/knowledge_base/raw
    poetry run python scripts/rag_agent.py watch --interval 300
    poetry run python scripts/rag_agent.py eval --top-k 5
    poetry run python scripts/rag_agent.py query --reason "导油环回油口卡滞" --change-proposal "增加C角和R角"

This is intentionally a small local agent first: it can be scheduled later by
Windows Task Scheduler, a background worker, or an admin API without changing
the RAG internals.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RAG_DIR = BACKEND_DIR / "app" / "rag"
DEFAULT_RAW_DIR = RAG_DIR / "knowledge_base" / "raw"
DEFAULT_EVAL_FILE = RAG_DIR / "evals" / "golden_queries.json"


@dataclass
class EvalHit:
    rank: int
    score: float
    source: str
    case_id: str
    chunk_id: str
    chunk_type: str
    text_preview: str


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND_DIR / ".env")
    except Exception:
        pass


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _file_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "updated_at": (
            datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            if path.exists()
            else None
        ),
    }


def collect_status() -> dict[str, Any]:
    from app.rag.ingest.build_index import INDEX_PATH, META_PATH, get_rebuild_status

    kb_dir = RAG_DIR / "knowledge_base"
    cases_dir = kb_dir / "cases"
    markdown_dir = kb_dir / "markdown"
    chunks_path = kb_dir / "chunks" / "chunks.jsonl"
    registry_path = kb_dir / "index" / "registry.json"

    return {
        "raw_dir": str(DEFAULT_RAW_DIR),
        "standardized_knowledge_base": {
            "case_count": len(list(cases_dir.glob("*.json"))) if cases_dir.exists() else 0,
            "markdown_count": (
                len(list(markdown_dir.glob("*.md"))) if markdown_dir.exists() else 0
            ),
            "chunk_count": _count_jsonl(chunks_path),
            "chunks": _file_status(chunks_path),
            "registry": _file_status(registry_path),
        },
        "vector_store": {
            "raw_faiss": _file_status(INDEX_PATH),
            "raw_meta": _file_status(META_PATH),
            "last_rebuild": get_rebuild_status(),
        },
    }


def print_status() -> None:
    status = collect_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))


def sync_knowledge(input_dir: Path, source_type: str, rebuild_index: bool) -> int:
    _load_env()

    from app.rag.ingest import rebuild_index as rebuild_vector_index
    from app.rag.ingestion.pipeline import ingest_case_directory
    from app.rag.ingestion.registry import Registry

    if not input_dir.exists():
        print(f"[error] input dir does not exist: {input_dir}")
        return 2

    print(f"[sync] ingest input={input_dir} type={source_type}")
    registry = Registry()
    cases = ingest_case_directory(str(input_dir), source_type, registry=registry, verbose=True)
    failed = [entry for entry in registry.all_entries() if entry.status == "failed"]

    print(f"[sync] newly indexed cases: {len(cases)}")
    if failed:
        print(f"[sync] failed entries: {len(failed)}")
        for entry in failed[:10]:
            print(f"  - {entry.source_file}: {entry.error_message}")

    if rebuild_index and cases:
        print("[sync] rebuilding vector indexes...")
        ok = rebuild_vector_index()
        print("[sync] vector index rebuild: ok" if ok else "[sync] vector index rebuild: skipped/failed")
        return 0 if ok else 1

    if rebuild_index:
        print("[sync] no new/changed cases; vector rebuild skipped.")
    else:
        print("[sync] vector rebuild disabled.")
    return 0


def rebuild_indexes() -> int:
    _load_env()

    from app.rag.ingest import rebuild_index

    print("[rebuild] rebuilding vector indexes from all knowledge sources...")
    ok = rebuild_index()
    print("[rebuild] done." if ok else "[rebuild] skipped/failed.")
    return 0 if ok else 1


def watch_knowledge(input_dir: Path, source_type: str, interval: int, rebuild_index: bool) -> int:
    print(f"[watch] monitoring {input_dir} every {interval}s. Press Ctrl+C to stop.")
    try:
        while True:
            sync_knowledge(input_dir, source_type, rebuild_index)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[watch] stopped.")
        return 0


def _load_eval_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("eval file must be a JSON list")
    return data


def _hit_blob(hit: EvalHit) -> str:
    return " ".join(
        [
            hit.source,
            hit.case_id,
            hit.chunk_id,
            hit.chunk_type,
            hit.text_preview,
        ]
    ).lower()


def _matches_expected(hit: EvalHit, spec: dict[str, Any]) -> bool:
    identity_parts: list[str] = []
    for key in ("expected_case_ids", "expected_sources"):
        raw = spec.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        identity_parts.extend(str(item).lower() for item in raw if str(item).strip())

    raw_terms = spec.get("expected_terms") or []
    if isinstance(raw_terms, str):
        raw_terms = [raw_terms]
    expected_terms = [str(item).lower() for item in raw_terms if str(item).strip()]

    if not identity_parts and not expected_terms:
        return False

    blob = _hit_blob(hit)
    if identity_parts:
        return any(part in blob for part in identity_parts)

    # Terms are a fallback for hand-written inspections where no stable source
    # identifier is known. Require all terms to avoid broad template words such
    # as "SCR" creating false positives.
    return all(term in blob for term in expected_terms)


def _retrieve_eval_hits(query: dict[str, Any], top_k: int) -> list[EvalHit]:
    from app.rag.retrieval import retrieve_cases

    hits = retrieve_cases(query, top_k=top_k)
    out: list[EvalHit] = []
    for rank, hit in enumerate(hits, start=1):
        metadata = hit.metadata or {}
        out.append(
            EvalHit(
                rank=rank,
                score=round(float(hit.score), 4),
                source=str(hit.source or metadata.get("source") or ""),
                case_id=str(metadata.get("case_id") or ""),
                chunk_id=str(hit.chunk_id or metadata.get("chunk_id") or ""),
                chunk_type=str(metadata.get("chunk_type") or ""),
                text_preview=str(hit.text or "").replace("\n", " ")[:220],
            )
        )
    return out


def evaluate_rag(eval_file: Path, top_k: int, strict: bool, json_output: Path | None) -> int:
    _load_env()

    cases = _load_eval_cases(eval_file)
    report: list[dict[str, Any]] = []
    evaluable = 0
    hits_at_k = 0

    print(f"[eval] file={eval_file} top_k={top_k}")
    for item in cases:
        name = item.get("name") or item.get("id") or "unnamed"
        query = item.get("query") or {}
        if not isinstance(query, dict):
            raise ValueError(f"eval query must be an object: {name}")

        hits = _retrieve_eval_hits(query, top_k=top_k)
        has_expected = any(
            item.get(key) for key in ("expected_case_ids", "expected_sources", "expected_terms")
        )
        matched_rank = None
        if has_expected:
            evaluable += 1
            for hit in hits:
                if _matches_expected(hit, item):
                    matched_rank = hit.rank
                    hits_at_k += 1
                    break

        print("\n" + "-" * 72)
        print(f"[case] {name}")
        print(f"query: {json.dumps(query, ensure_ascii=False)}")
        if has_expected:
            status = "HIT" if matched_rank is not None else "MISS"
            print(f"expected: {status} rank={matched_rank or '-'}")
        else:
            print("expected: inspect-only")
        for hit in hits:
            marker = "*" if matched_rank == hit.rank else " "
            print(
                f"{marker} #{hit.rank:<2} score={hit.score:<7} "
                f"case={hit.case_id or '-'} type={hit.chunk_type or '-'} source={hit.source}"
            )
            print(f"    {hit.text_preview}")

        report.append(
            {
                "name": name,
                "query": query,
                "matched_rank": matched_rank,
                "hits": [asdict(hit) for hit in hits],
            }
        )

    hit_rate = hits_at_k / evaluable if evaluable else None
    summary = {
        "eval_file": str(eval_file),
        "top_k": top_k,
        "total_cases": len(cases),
        "evaluable_cases": evaluable,
        "hits_at_k": hits_at_k,
        "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
    }
    print("\n" + "=" * 72)
    print("[summary]")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(
            json.dumps({"summary": summary, "cases": report}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[eval] report written: {json_output}")

    return 1 if strict and evaluable and hits_at_k < evaluable else 0


def query_once(args: argparse.Namespace) -> int:
    _load_env()

    query = {
        "customer_project": args.customer_project or "",
        "product_no": args.product_no or "",
        "component_no": args.component_no or "",
        "reason": args.reason or "",
        "current_design": args.current_design or "",
        "change_proposal": args.change_proposal or "",
        "remarks": args.remarks or "",
    }
    hits = _retrieve_eval_hits(query, top_k=args.top_k)
    print(json.dumps({"query": query, "hits": [asdict(hit) for hit in hits]}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PD-ECR RAG maintenance agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="print knowledge base and vector index status")
    sub.add_parser("rebuild", help="rebuild FAISS/LangChain indexes from all knowledge sources")

    sync = sub.add_parser("sync", help="ingest changed files and rebuild indexes if needed")
    sync.add_argument("--input", default=str(DEFAULT_RAW_DIR), help="raw input directory")
    sync.add_argument("--type", default="auto", choices=["auto", "mineru", "excel", "word"])
    sync.add_argument("--no-rebuild-index", action="store_true")

    watch = sub.add_parser("watch", help="run sync repeatedly")
    watch.add_argument("--input", default=str(DEFAULT_RAW_DIR), help="raw input directory")
    watch.add_argument("--type", default="auto", choices=["auto", "mineru", "excel", "word"])
    watch.add_argument("--interval", type=int, default=300, help="polling interval in seconds")
    watch.add_argument("--no-rebuild-index", action="store_true")

    eval_cmd = sub.add_parser("eval", help="evaluate retrieval against golden queries")
    eval_cmd.add_argument("--file", default=str(DEFAULT_EVAL_FILE), help="golden queries JSON")
    eval_cmd.add_argument("--top-k", type=int, default=5)
    eval_cmd.add_argument("--strict", action="store_true", help="return non-zero on misses")
    eval_cmd.add_argument("--json-output", default="", help="write machine-readable report")

    query = sub.add_parser("query", help="run one retrieval query")
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--customer-project", default="")
    query.add_argument("--product-no", default="")
    query.add_argument("--component-no", default="")
    query.add_argument("--reason", default="")
    query.add_argument("--current-design", default="")
    query.add_argument("--change-proposal", default="")
    query.add_argument("--remarks", default="")

    args = parser.parse_args()

    if args.command == "status":
        print_status()
        return 0
    if args.command == "rebuild":
        return rebuild_indexes()
    if args.command == "sync":
        return sync_knowledge(
            Path(args.input),
            args.type,
            rebuild_index=not args.no_rebuild_index,
        )
    if args.command == "watch":
        return watch_knowledge(
            Path(args.input),
            args.type,
            interval=max(10, args.interval),
            rebuild_index=not args.no_rebuild_index,
        )
    if args.command == "eval":
        json_output = Path(args.json_output) if args.json_output else None
        return evaluate_rag(Path(args.file), args.top_k, args.strict, json_output)
    if args.command == "query":
        return query_once(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
