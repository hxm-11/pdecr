from pathlib import Path
from typing import Dict, List, Any


BASE_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = BASE_DIR / "rag"
KNOWLEDGE_DIR = RAG_DIR / "knowledge"


def _read_text_files() -> List[Dict[str, str]]:
    """
    读取 knowledge 下面所有 md / json / txt。
    """
    docs = []

    if not KNOWLEDGE_DIR.exists():
        return docs

    for path in KNOWLEDGE_DIR.rglob("*"):
        if path.suffix.lower() not in [".md", ".json", ".txt"]:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not text.strip():
            continue

        docs.append({
            "path": str(path),
            "text": text,
        })

    return docs


def _score_text(text: str, query_terms: List[str]) -> int:
    lower_text = text.lower()
    score = 0

    for term in query_terms:
        term = term.strip().lower()
        if not term:
            continue

        if term in lower_text:
            score += 3

    # 对你的报告常见关键词加权
    important_terms = [
        "seat wear",
        "guidance wear",
        "coating",
        "delaminated",
        "deposit",
        "cavitation",
        "corrosion",
        "mechanical damage",
        "needle guidance clearance",
        "leakage",
        "磨损",
        "镀层",
        "剥落",
        "积炭",
        "穴蚀",
        "腐蚀",
        "机械破损",
        "导向间隙",
        "泄漏",
    ]

    for term in important_terms:
        if term.lower() in lower_text:
            score += 2

    return score


def retrieve_report_context(
    user_input: Dict[str, Any],
    image_observation: Dict[str, Any],
    top_k: int = 5,
) -> str:
    """
    根据用户输入和图片观察结果检索历史知识库。
    第一版：关键词检索。
    后续你可以替换成 Chroma / FAISS。
    """

    docs = _read_text_files()

    if not docs:
        return "未找到知识库文件，请检查 backend/app/rag/knowledge 目录。"

    query_parts = []

    for key in [
        "customer",
        "project",
        "part_name",
        "injector_no",
        "nozzle_type",
        "runtime",
        "conditions",
        "complaint",
        "problem_description",
    ]:
        value = user_input.get(key, "")
        if value:
            query_parts.append(str(value))

    for key in [
        "image_summary",
        "abnormal_area",
        "function_relevant_area",
    ]:
        value = image_observation.get(key, "")
        if value:
            query_parts.append(str(value))

    for key in [
        "visible_abnormalities",
        "possible_defect_types",
    ]:
        values = image_observation.get(key, [])
        if isinstance(values, list):
            query_parts.extend([str(v) for v in values])

    # 固定加入你的报告相关关键词
    query_parts.extend([
        "nozzle",
        "investigation",
        "seat wear",
        "guidance wear",
        "coating delamination",
        "deposit",
        "cavitation",
        "corrosion",
        "mechanical damage",
        "needle guidance clearance",
        "leakage",
        "油嘴",
        "磨损",
        "积炭",
        "镀层剥落",
        "导向间隙",
    ])

    query_terms = []
    for part in query_parts:
        query_terms.extend(str(part).replace(",", " ").split())

    scored = []

    for doc in docs:
        score = _score_text(doc["text"], query_terms)
        if score > 0:
            scored.append({
                "score": score,
                "path": doc["path"],
                "text": doc["text"],
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        # 没匹配到时返回前几个文件的前部内容，避免空上下文
        fallback = docs[:top_k]
        return "\n\n".join(
            f"[Source: {d['path']}]\n{d['text'][:2000]}"
            for d in fallback
        )

    selected = scored[:top_k]

    chunks = []

    for item in selected:
        text = item["text"]

        # 简单截取前 3000 字。后面可以优化为 chunk 检索。
        chunks.append(
            f"[Source: {item['path']} | score={item['score']}]\n{text[:3000]}"
        )

    return "\n\n---\n\n".join(chunks)