from __future__ import annotations

from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data" / "pd_ecr_cases"
CURATED_CASES_PATH = DATA_DIR / "pd_ecr_cases.json"
RAG_DIR = APP_DIR / "rag"
KNOWLEDGE_DIR = RAG_DIR / "knowledge"
PDECR_KNOWLEDGE_DIR = RAG_DIR / "pdecr_knowledge"
CLEAN_TEXT_DIR = RAG_DIR / "clean_text"
STRUCTURED_CASES_DIR = RAG_DIR / "structured_cases"
PDECR_JIE_JIM_PDF_DIR = RAG_DIR / "PDECR_JIE_JIM"
JIE_JIM_KNOWLEDGE_PDF_DIR = RAG_DIR / "jie_jim_knowledge_pdf"
REPORTS_DIR = APP_DIR / "reports"

TEXT_SUFFIXES = {".md", ".txt", ".json"}
BINARY_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".docx"}


def iter_existing_files(*roots: Path, suffixes: set[str] | None = None) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for root in roots:
        if not root.exists():
            continue

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if suffixes and path.suffix.lower() not in suffixes:
                continue
            if "copy" in path.stem.lower() or "副本" in path.stem:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)

    return files


def iter_case_text_files() -> list[Path]:
    return iter_existing_files(
        STRUCTURED_CASES_DIR,
        KNOWLEDGE_DIR,
        PDECR_KNOWLEDGE_DIR,
        CLEAN_TEXT_DIR,
        suffixes=TEXT_SUFFIXES,
    )


def iter_safe_text_files() -> list[Path]:
    return iter_existing_files(
        DATA_DIR,
        STRUCTURED_CASES_DIR,
        KNOWLEDGE_DIR,
        PDECR_KNOWLEDGE_DIR,
        CLEAN_TEXT_DIR,
        JIE_JIM_KNOWLEDGE_PDF_DIR,
        suffixes=TEXT_SUFFIXES,
    )


def iter_pdf_files() -> list[Path]:
    if not PDECR_JIE_JIM_PDF_DIR.exists():
        return []
    return sorted(PDECR_JIE_JIM_PDF_DIR.glob("*.pdf"), key=lambda item: item.name.lower())
