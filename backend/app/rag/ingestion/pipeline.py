"""入库编排 pipeline：源文件 -> 标准 PdecrCase -> markdown + chunks + 索引。

单个 case 的完整流程：
  1. parse   —— 源文件 -> ParsedDocument
  2. extract —— ParsedDocument -> PdecrCase（抽不到留空）
  3. normalize + validate —— 清洗、生成稳定 case_id、写 quality_control
  4. save    —— case JSON  -> knowledge_base/cases/{case_id}.json
  5. render  —— markdown   -> knowledge_base/markdown/{case_id}.md
  6. chunk   —— 按业务模块切 chunk
  7. index   —— chunks     -> knowledge_base/chunks/chunks.jsonl
  8. return PdecrCase

对外入口：ingest_mineru_case / ingest_excel_case / ingest_word_case /
ingest_case_directory。
批处理单文件失败不会中断整批（错误记进 registry 与返回值）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.rag.schemas.pdecr_case_schema import PdecrCase

from .extractors import get_extractor
from .indexer import index_case
from .loaders import ParsedDocument, compute_checksum, detect_source_type
from .markdown_renderer import render_markdown
from .normalizer import normalize_case
from .parsers import ExcelParser, MineruParser, WordParser
from .registry import STATUS_FAILED, STATUS_INDEXED, Registry

_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
CASES_DIR = _KB_DIR / "cases"
MARKDOWN_DIR = _KB_DIR / "markdown"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finalize(parsed: ParsedDocument) -> PdecrCase:
    """extract -> normalize -> save json -> render md -> chunk -> index。"""
    extractor = get_extractor()
    case = extractor.extract(parsed)
    case = normalize_case(case)

    CASES_DIR.mkdir(parents=True, exist_ok=True)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

    case.save(str(CASES_DIR / f"{case.case_id}.json"))
    markdown = render_markdown(case)
    (MARKDOWN_DIR / f"{case.case_id}.md").write_text(markdown, encoding="utf-8")
    index_case(case, markdown)
    return case


# ── 单文件入口 ────────────────────────────────────────────
def ingest_mineru_case(
    raw_json_path: str | None,
    raw_markdown_path: str | None,
    source_file: str,
) -> PdecrCase:
    parsed = MineruParser().parse(raw_json_path, raw_markdown_path, source_file)
    return _finalize(parsed)


def ingest_excel_case(excel_path: str) -> PdecrCase:
    parsed = ExcelParser().parse(excel_path)
    return _finalize(parsed)


def ingest_word_case(word_path: str) -> PdecrCase:
    parsed = WordParser().parse(word_path)
    return _finalize(parsed)


# ── 目录批处理 ────────────────────────────────────────────
def ingest_case_directory(
    input_dir: str,
    source_type: str = "auto",
    *,
    registry: Registry | None = None,
    verbose: bool = False,
) -> list[PdecrCase]:
    """批量入库一个目录。source_type: auto / mineru / excel / word。

    - excel：遍历 *.xlsx/*.xls/*.xlsm。
    - word：遍历 *.docx/*.doc（.doc 会给出明确失败原因）。
    - mineru：遍历 *.md，若存在同名 *.json 则配对。
    单文件失败记入 registry(status=failed) 并继续，不中断整批。
    """
    root = Path(input_dir)
    if not root.exists():
        raise FileNotFoundError(input_dir)

    reg = registry or Registry()
    jobs = _discover_jobs(root, source_type)
    cases: list[PdecrCase] = []

    for job in jobs:
        key = job["key"]
        checksum = job.get("checksum")
        if not reg.should_ingest(key, checksum):
            if verbose:
                _emit(f"[skip] 已入库且未变化: {key}")
            continue
        try:
            if job["type"] == "excel":
                case = ingest_excel_case(job["excel_path"])
            elif job["type"] == "word":
                case = ingest_word_case(job["word_path"])
            else:
                case = ingest_mineru_case(
                    job.get("raw_json_path"),
                    job.get("raw_markdown_path"),
                    job["source_file"],
                )
            reg.mark(
                key,
                status=STATUS_INDEXED,
                checksum=checksum,
                case_id=case.case_id,
                indexed_at=_now(),
            )
            cases.append(case)
            if verbose:
                _emit(
                    f"[ok] {key} -> {case.case_id} "
                    f"(status={case.quality_control.extraction_status})"
                )
        except Exception as exc:  # noqa: BLE001 - 单文件失败不影响整批
            reg.mark(
                key, status=STATUS_FAILED, checksum=checksum, error_message=str(exc)
            )
            if verbose:
                _emit(f"[fail] {key}: {exc}")
    return cases


def _discover_jobs(root: Path, source_type: str) -> list[dict]:
    jobs: list[dict] = []

    def want(t: str) -> bool:
        return source_type in ("auto", t)

    # Excel
    if want("excel"):
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
                jobs.append(
                    {
                        "type": "excel",
                        "key": str(path),
                        "excel_path": str(path),
                        "checksum": compute_checksum(path),
                    }
                )

    # MinerU：*.md（可配同名 json）
    if want("mineru"):
        for md_path in sorted(root.rglob("*.md")):
            stem = md_path.stem
            json_path = None
            for cand in (
                md_path.with_suffix(".json"),
                md_path.parent / f"{stem}_content_list.json",
                md_path.parent / f"{stem}.content_list.json",
            ):
                if cand.exists():
                    json_path = str(cand)
                    break
            jobs.append(
                {
                    "type": "mineru",
                    "key": str(md_path),
                    "raw_markdown_path": str(md_path),
                    "raw_json_path": json_path,
                    "source_file": md_path.name,
                    "checksum": compute_checksum(md_path),
                }
            )

    # Word
    if want("word"):
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() in {".docx", ".doc"}:
                jobs.append(
                    {
                        "type": "word",
                        "key": str(path),
                        "word_path": str(path),
                        "checksum": compute_checksum(path),
                    }
                )

    # auto 兜底：明确类型时若上面没覆盖，按扩展名再扫一遍
    if source_type not in ("auto", "excel", "mineru", "word"):
        for path in sorted(root.rglob("*")):
            detected = detect_source_type(path)
            if path.is_file() and detected == "excel":
                jobs.append(
                    {
                        "type": "excel",
                        "key": str(path),
                        "excel_path": str(path),
                        "checksum": compute_checksum(path),
                    }
                )
            elif path.is_file() and detected == "word":
                jobs.append(
                    {
                        "type": "word",
                        "key": str(path),
                        "word_path": str(path),
                        "checksum": compute_checksum(path),
                    }
                )
    return jobs


def _emit(msg: str) -> None:
    # 独立函数便于测试时静音；运行时打印
    print(msg)  # noqa: T201
