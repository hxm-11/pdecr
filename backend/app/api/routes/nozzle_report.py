from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from html.parser import HTMLParser
import html
import json
import re
import time
import shutil
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from typing import List, Any
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
router = APIRouter(prefix="/nozzle-report", tags=["nozzle-report"])


# ============================================================
# 路径配置
# 当前文件：
# backend/app/api/routes/nozzle_report.py
# ============================================================

APP_DIR = Path(__file__).resolve().parents[2]       # backend/app
BACKEND_DIR = Path(__file__).resolve().parents[3]   # backend
PROJECT_DIR = Path(__file__).resolve().parents[4]   # full-stack-fastapi-template-master

# 必须和 main.py 里的 /static/reports 挂载目录一致
REPORTS_DIR = APP_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# 图片上传目录：backend/app/uploads/nozzle
UPLOAD_DIR = APP_DIR / "uploads" / "nozzle"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# 自动寻找 rag 目录
RAG_CANDIDATES = [
    BACKEND_DIR / "rag",
    APP_DIR / "rag",
    PROJECT_DIR / "rag",
]

RAG_DIR = next((p for p in RAG_CANDIDATES if p.exists()), None)

if RAG_DIR:
    print("Nozzle RAG 目录：", RAG_DIR)
else:
    print("警告：没有找到 rag 目录，请检查 rag 是否在 backend/rag、backend/app/rag 或项目根目录/rag 下")


# ============================================================
# API
# ============================================================

@router.post("/generate-from-images")
async def generate_from_images(
    images: List[UploadFile] = File(...),

    customer: str = Form(""),
    project: str = Form(""),
    type_of_test: str = Form(""),
    conditions: str = Form(""),
    fuel: str = Form(""),
    runtime: str = Form(""),
    injector_no: str = Form(""),
    nozzle_type: str = Form(""),
    seat_geometry: str = Form(""),
    complaint: str = Form(""),
    problem_description: str = Form(""),
    report_no: str = Form(""),
    bm_no: str = Form(""),
    customer_no: str = Form(""),
):
    print("收到图片数量：", len(images))
    print("REPORTS_DIR:", REPORTS_DIR)
    print("UPLOAD_DIR:", UPLOAD_DIR)

    # 1. 保存上传图片
    saved_files = save_uploaded_images(images)

    # 2. 组织检索查询
    query_info = {
        "customer": customer,
        "project": project,
        "type_of_test": type_of_test,
        "conditions": conditions,
        "fuel": fuel,
        "runtime": runtime,
        "injector_no": injector_no,
        "nozzle_type": nozzle_type,
        "seat_geometry": seat_geometry,
        "complaint": complaint,
        "problem_description": problem_description,
        "report_no": report_no,
        "bm_no": bm_no,
        "customer_no": customer_no,
    }

    # 3. 从 RAG 历史文件检索
    rag_result = retrieve_nozzle_rag(query_info)
    rag_fields = rag_result.get("fields", {})
    rag_context_preview = rag_result.get("context_preview", "")
    matched_files = rag_result.get("matched_files", [])

    # 4. 从命中的 MD/TXT 历史文件中提取图片
    rag_images = collect_rag_images(matched_files)

    print("RAG 检索字段：", rag_fields.keys())
    print("RAG 命中文件：", matched_files)
    print("RAG 图片数量：", len(rag_images))

    # 5. 前端输入优先；前端为空时用 RAG 填充
    final_basic_info = {
        "customer": prefer_input(customer, rag_fields.get("customer")),
        "project": prefer_input(project, rag_fields.get("project")),
        "type_of_test": prefer_input(type_of_test, rag_fields.get("type_of_test")),
        "conditions": prefer_input(conditions, rag_fields.get("conditions")),
        "fuel": prefer_input(fuel, rag_fields.get("fuel")),
        "runtime": prefer_input(runtime, rag_fields.get("runtime")),
        "injector_no": prefer_input(injector_no, rag_fields.get("injector_no")),
        "nozzle_type": prefer_input(nozzle_type, rag_fields.get("nozzle_type")),
        "seat_geometry": prefer_input(seat_geometry, rag_fields.get("seat_geometry")),
        "complaint": prefer_input(complaint, rag_fields.get("complaint")),
        "problem_description": prefer_input(
            problem_description,
            rag_fields.get("problem_description"),
        ),
        "report_no": prefer_input(report_no, rag_fields.get("report_no")),
        "bm_no": prefer_input(bm_no, rag_fields.get("bm_no")),
        "customer_no": prefer_input(customer_no, rag_fields.get("customer_no")),
    }

    # 6. 上传图片分析结果，目前仍是占位，后面可以替换为真实视觉模型
    image_analysis = [
    {
        "file": item["filename"],
        "file_path": item["file_path"],
        "url": item["url"],
        "result": "OK",
        "observation": "图片已接收。当前版本已接入 RAG 历史信息检索，图像视觉分析仍为占位逻辑。",
    }
    for item in saved_files
    ]

    merged_image_observation = {
        "image_count": len(saved_files),
        "uploaded_images": [item["filename"] for item in saved_files],
        "uploaded_image_urls": [item["url"] for item in saved_files],
        "summary_en": "Images uploaded successfully. Historical RAG context has been retrieved.",
        "summary_cn": "图片上传成功，已检索历史 RAG 知识库内容。",
        "rag_matched_files": matched_files,
    }

    # 7. 生成最终报告 JSON
    report_json = {
        "report_meta": {
            "report_title": f"Nozzle Report for {final_basic_info.get('project') or 'Unknown Project'}",
            "generated_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "front_input + rag_history",
        },
        "test_basic_info": final_basic_info,
        "job_problem_explanation": {
            "description_en": rag_fields.get("job_problem_explanation_en")
            or final_basic_info.get("problem_description")
            or "No problem description provided.",
            "description_cn": rag_fields.get("job_problem_explanation_cn")
            or final_basic_info.get("problem_description")
            or "未提供问题描述。",
        },
        "responsible_departments": {
            "departments_en": rag_fields.get("responsible_departments_en")
            or ["Engineering", "Quality"],
            "departments_cn": rag_fields.get("responsible_departments_cn")
            or ["工程部", "质量部"],
        },
        "image_analysis": image_analysis,
        "report_images": {
            "uploaded_images": image_analysis,
            "rag_images": rag_images,
        },
        "investigation_results": rag_fields.get("investigation_results")
        or {
            "result_en": "Historical RAG context has been retrieved. Please verify the generated report content.",
            "result_cn": "已检索历史 RAG 内容，请结合图片和工程背景确认报告结论。",
        },
        "measured_values": rag_fields.get("measured_values")
        or {
            "note": "未从历史知识库中提取到明确测量值。",
        },
        "conclusion": rag_fields.get("conclusion")
        or {
            "conclusion_en": "Further inspection is recommended based on uploaded images and historical cases.",
            "conclusion_cn": "建议结合上传图片、历史案例、显微检测和尺寸测量进一步确认。",
        },
        "parts": rag_fields.get("parts")
        or {
            "part_name": "Nozzle",
            "injector_no": final_basic_info.get("injector_no", ""),
        },
        "measures": rag_fields.get("measures")
        or {
            "recommended_action_en": "Re-inspection and detailed seat/guide area check are recommended.",
            "recommended_action_cn": "建议复检，并重点检查座面、导向段、喷孔和积炭区域。",
        },
        "signatures": rag_fields.get("signatures")
        or {
            "prepared_by": "",
            "checked_by": "",
            "approved_by": "",
        },
    }

    # 8. 生成 HTML 报告
    safe_project = sanitize_filename(final_basic_info.get("project") or "unknown_project")
    timestamp = time.strftime("%Y%m%d_%H%M%S")

    pdf_filename = f"nozzle_report_{safe_project}_{timestamp}.pdf"
    pdf_path = REPORTS_DIR / pdf_filename
    build_report_pdf(report_json, merged_image_observation, pdf_path)

    # 再生成 HTML，把真实 PDF 文件名传进去
    html_content = build_report_html(
        report_json=report_json,
        merged_image_observation=merged_image_observation,
        rag_context_preview=rag_context_preview,
        pdf_url=f"/static/reports/{pdf_filename}",
    )
    html_filename = f"nozzle_report_{safe_project}_{timestamp}.html"
    html_path = REPORTS_DIR / html_filename
    html_path.write_text(html_content, encoding="utf-8")
    
    print("生成 HTML 文件：", html_path)
    print("HTML 文件是否存在：", html_path.exists())
    print("生成 PDF 文件：", pdf_path)
    print("PDF 文件是否存在：", pdf_path.exists())

    pdf_filename = html_filename.replace(".html", ".pdf")
    pdf_filename = html_filename.replace(".html", ".pdf")
    pdf_path = REPORTS_DIR / pdf_filename

    build_report_pdf(
        report_json=report_json,
        merged_image_observation=merged_image_observation,
        pdf_path=pdf_path,
    )

    print("生成 PDF 文件：", pdf_path)
    print("PDF 文件是否存在：", pdf_path.exists())  

    return JSONResponse(
        {
            "message": "生成成功",
            "report_json": report_json,
            "image_observations": image_analysis,
            "merged_image_observation": merged_image_observation,
            "html_path": f"/static/reports/{html_filename}",
            "pdf_path": f"/static/reports/{pdf_filename}",
            "pdf_download_url": f"/static/reports/{pdf_filename}",
            "rag_context_preview": rag_context_preview,
        }
    )

@router.get("/download-pdf/{pdf_filename}")
async def download_pdf(pdf_filename: str):
    safe_name = Path(pdf_filename).name

    if not safe_name.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"detail": "只能下载 PDF 文件"},
        )

    pdf_path = REPORTS_DIR / safe_name

    if not pdf_path.exists():
        return JSONResponse(
            status_code=404,
            content={
                "detail": "PDF 文件不存在",
                "expected_path": str(pdf_path),
            },
        )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=safe_name,
    )

# ============================================================
# 文件保存与路径工具
# ============================================================

def save_uploaded_images(images: List[UploadFile]) -> list[dict]:
    saved_files = []

    for img in images:
        safe_name = sanitize_filename(Path(img.filename or "uploaded_image").name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        final_name = f"{timestamp}_{safe_name}"

        file_path = UPLOAD_DIR / final_name

        with file_path.open("wb") as f:
            shutil.copyfileobj(img.file, f)

        saved_files.append(
            {
                "filename": final_name,
                "file_path": str(file_path),
                "url": f"/static/uploads/nozzle/{final_name}",
            }
        )

    return saved_files


def collect_rag_images(matched_files: list[str], max_images: int = 20) -> list[dict]:
    """
    从命中的 Markdown/TXT 文件里提取图片引用。
    支持：
    ![](images/xxx.jpg)
    <img src="images/xxx.jpg"/>
    """
    result = []
    seen = set()

    for file_str in matched_files:
        md_path = Path(file_str)

        if not md_path.exists() or md_path.suffix.lower() not in [".md", ".txt"]:
            continue

        text = read_text_file(md_path)
        image_refs = []

        image_refs.extend(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text))
        image_refs.extend(
            re.findall(
                r"<img\s+[^>]*src=[\"']([^\"']+)[\"']",
                text,
                flags=re.IGNORECASE,
            )
        )

        for ref in image_refs:
            ref = ref.strip()

            if not ref:
                continue

            if ref.startswith("http://") or ref.startswith("https://"):
                continue

            image_path = (md_path.parent / ref).resolve()

            if not image_path.exists():
                continue

            if image_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                continue

            key = str(image_path)
            if key in seen:
                continue

            seen.add(key)

            asset_dir = UPLOAD_DIR / "rag_assets"
            asset_dir.mkdir(parents=True, exist_ok=True)

            final_name = f"rag_{len(result) + 1}_{sanitize_filename(image_path.name)}"
            target_path = asset_dir / final_name

            if not target_path.exists():
                shutil.copyfile(image_path, target_path)

            result.append(
                {
                     "filename": final_name,
                    "source": str(image_path),
                    "file_path": str(target_path),
                    "url": f"/static/uploads/nozzle/rag_assets/{final_name}",
                }
            )

            if len(result) >= max_images:
                return result

    return result


def prefer_input(input_value: str, rag_value: Any) -> str:
    if input_value and str(input_value).strip():
        return str(input_value).strip()

    if rag_value is None:
        return ""

    if isinstance(rag_value, (dict, list)):
        return json.dumps(rag_value, ensure_ascii=False)

    return str(rag_value).strip()


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", "_", name)
    return name or "unknown"


# ============================================================
# RAG 检索
# ============================================================

def retrieve_nozzle_rag(query_info: dict) -> dict:
    if not RAG_DIR:
        return {
            "fields": {},
            "context_preview": "未找到 rag 目录。",
            "matched_files": [],
        }

    search_dirs = [
        RAG_DIR / "eg_knowledge",
        RAG_DIR / "structured",
        RAG_DIR / "raw_md",
        RAG_DIR / "defect_rules",
    ]

    query_terms = build_query_terms(query_info)
    candidates = []

    for folder in search_dirs:
        if not folder.exists():
            continue

        for path in folder.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.lower() not in [".json", ".md", ".txt"]:
                continue

            text = read_text_file(path)
            if not text:
                continue

            score = score_text(text, path.name, query_terms)

            if score > 0:
                candidates.append(
                    {
                        "path": path,
                        "score": score,
                        "text": text,
                    }
                )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = candidates[:5]

    matched_files = [str(item["path"]) for item in top_candidates]

    combined_text = "\n\n".join(
        [
            f"===== SOURCE: {item['path']} | SCORE: {item['score']} =====\n{item['text'][:6000]}"
            for item in top_candidates
        ]
    )

    fields = {}

    # 先从结构化 JSON 提取
    for item in top_candidates:
        if item["path"].suffix.lower() == ".json":
            obj = try_load_json(item["text"])
            if obj:
                fields.update(flatten_known_fields(obj))

    # 再从 MD/TXT 提取
    text_fields = extract_fields_from_text(combined_text)
    for key, value in text_fields.items():
        fields.setdefault(key, value)

    return {
        "fields": fields,
        "context_preview": combined_text[:10000],
        "matched_files": matched_files,
    }


def build_query_terms(query_info: dict) -> list[str]:
    important_keys = [
        "customer",
        "project",
        "type_of_test",
        "conditions",
        "fuel",
        "runtime",
        "injector_no",
        "nozzle_type",
        "seat_geometry",
        "complaint",
        "problem_description",
    ]

    terms = []

    for key in important_keys:
        value = query_info.get(key)
        if value and str(value).strip():
            terms.append(str(value).strip())

    terms.extend(
        [
            "Nozzle",
            "nozzle",
            "Nozzle investigation",
            "injector",
            "Investigation",
            "oil nozzle",
            "喷嘴",
            "油嘴",
            "油嘴检测报告",
            "喷油器",
            "检测",
            "失效",
            "磨损",
            "积炭",
            "座面",
            "导向段",
        ]
    )

    result = []
    for term in terms:
        if term not in result:
            result.append(term)

    return result


def score_text(text: str, filename: str, query_terms: list[str]) -> int:
    lower_text = text.lower()
    lower_filename = filename.lower()

    score = 0

    for term in query_terms:
        if not term:
            continue

        t = term.lower().strip()
        if not t:
            continue

        if t in lower_filename:
            score += 50

        count = lower_text.count(t)
        if count:
            score += min(count * 10, 100)

    important_keywords = [
        "nozzle investigation",
        "油嘴检测报告",
        "customer 客户",
        "project 项目",
        "nozzle type 油嘴类型",
        "seat geometry 座面",
        "complaint 抱怨",
        "measured values",
        "conclusion 结论",
    ]

    for kw in important_keywords:
        if kw.lower() in lower_text:
            score += 20

    return score


def read_text_file(path: Path) -> str:
    for encoding in ["utf-8", "utf-8-sig", "gbk", "latin1"]:
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except Exception:
            continue

    return ""


def try_load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return None


def flatten_known_fields(obj: Any) -> dict:
    fields = {}

    if not isinstance(obj, dict):
        return fields

    possible_basic = (
        obj.get("test_basic_info")
        or obj.get("basic_info")
        or obj.get("Basic Information")
        or obj.get("basic_information")
        or {}
    )

    if isinstance(possible_basic, dict):
        mapping = {
            "customer": ["customer", "Customer", "客户"],
            "project": ["project", "Project", "项目"],
            "type_of_test": ["type_of_test", "Type of test", "test_type", "试验类型"],
            "conditions": ["conditions", "Conditions", "工况"],
            "fuel": ["fuel", "Fuel", "燃油"],
            "runtime": ["runtime", "Runtime", "运行时间"],
            "injector_no": ["injector_no", "Injector No.", "Injector No", "喷油器号"],
            "nozzle_type": ["nozzle_type", "Nozzle type", "Nozzle Type", "油嘴类型"],
            "seat_geometry": ["seat_geometry", "Seat geometry", "Seat Geometry", "座面"],
            "complaint": ["complaint", "Complaint", "抱怨"],
            "problem_description": [
                "problem_description",
                "Problem description",
                "Problem Description",
                "问题描述",
            ],
            "report_no": ["report_no", "Report No.", "Report No", "报告编号"],
            "bm_no": ["bm_no", "BM-No.", "BM-No", "BM No"],
            "customer_no": ["customer_no", "Customer-No.", "Customer No", "客户编号"],
        }

        for target_key, source_keys in mapping.items():
            for source_key in source_keys:
                if source_key in possible_basic and possible_basic[source_key]:
                    fields[target_key] = possible_basic[source_key]
                    break

    for key in [
        "investigation_results",
        "measured_values",
        "conclusion",
        "parts",
        "measures",
        "signatures",
    ]:
        if key in obj and obj[key]:
            fields[key] = obj[key]

    job = obj.get("job_problem_explanation") or obj.get("job_problem") or {}
    if isinstance(job, dict):
        if job.get("description_en"):
            fields["job_problem_explanation_en"] = job.get("description_en")
        if job.get("description_cn"):
            fields["job_problem_explanation_cn"] = job.get("description_cn")

    departments = obj.get("responsible_departments") or {}
    if isinstance(departments, dict):
        if departments.get("departments_en"):
            fields["responsible_departments_en"] = departments.get("departments_en")
        if departments.get("departments_cn"):
            fields["responsible_departments_cn"] = departments.get("departments_cn")

    return fields


# ============================================================
# Markdown / HTML 表格解析
# ============================================================

class SimpleTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "table":
            self.current_table = []

        elif tag == "tr" and self.current_table is not None:
            self.current_row = []

        elif tag in ["td", "th"] and self.current_row is not None:
            self.current_cell = []
            self.in_cell = True

    def handle_data(self, data):
        if self.in_cell and self.current_cell is not None:
            text = data.strip()
            if text:
                self.current_cell.append(text)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in ["td", "th"] and self.in_cell:
            cell_text = " ".join(self.current_cell or [])
            cell_text = clean_plain_text(cell_text)
            self.current_row.append(cell_text)
            self.current_cell = None
            self.in_cell = False

        elif tag == "tr" and self.current_table is not None and self.current_row is not None:
            if any(cell for cell in self.current_row):
                self.current_table.append(self.current_row)
            self.current_row = None

        elif tag == "table" and self.current_table is not None:
            if self.current_table:
                self.tables.append(self.current_table)
            self.current_table = None


def extract_html_tables(text: str) -> list[list[list[str]]]:
    parser = SimpleTableParser()
    parser.feed(text)
    return parser.tables


def remove_html_tables(text: str) -> str:
    return re.sub(r"<table[\s\S]*?</table>", "", text, flags=re.IGNORECASE)


def clean_plain_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"<img[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"!\[\]\([^)]+\)", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_extracted_value(value: str) -> str:
    value = value.strip()
    value = value.strip("|")
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def split_visual_and_measured_tables(section_text: str) -> dict:
    tables = extract_html_tables(section_text)
    plain_text = clean_plain_text(remove_html_tables(section_text))

    visual_tables = []
    measured_tables = []

    for table in tables:
        flat = " ".join([" ".join(row) for row in table]).lower()

        if (
            "visual inspection" in flat
            or "目测" in flat
            or "seat area" in flat
            or "guidance area" in flat
            or "deposit" in flat
            or "cavitation" in flat
            or "corrosion" in flat
        ):
            visual_tables.append(table)

        elif (
            "injectorno" in flat
            or "injector no" in flat
            or "nozzleno" in flat
            or "nozzle no" in flat
            or "leakage" in flat
            or "needle" in flat
            or "clearance" in flat
            or "average" in flat
            or "平均" in flat
        ):
            measured_tables.append(table)

    return {
        "plain_text": plain_text,
        "visual_tables": visual_tables,
        "measured_tables": measured_tables,
    }


def extract_fields_from_text(text: str) -> dict:
    fields = {}

    basic_patterns = {
        "customer": [
            r"Customer\s*客户\s*[:：]\s*(.+)",
            r"Customer\s*[:：]\s*(.+)",
        ],
        "type_of_test": [
            r"Type of test\s*试验类型\s*[:：]\s*(.+)",
            r"Type of test\s*[:：]\s*(.+)",
        ],
        "conditions": [
            r"Conditions\s*工况\s*[:：]\s*(.+)",
            r"Conditions\s*[:：]\s*(.+)",
        ],
        "project": [
            r"Project\s*项目\s*[:：]\s*(.+)",
            r"Project\s*[:：]\s*(.+)",
        ],
        "fuel": [
            r"Fuel\s*燃油\s*[:：]\s*(.+)",
            r"Fuel\s*[:：]\s*(.+)",
        ],
        "runtime": [
            r"Runtime\s*运行时间\s*[:：]\s*(.+)",
            r"Runtime\s*[:：]\s*(.+)",
        ],
        "injector_no": [
            r"Injector No\.?\s*喷油器号\s*[:：]\s*(.+)",
            r"Injector No\.?\s*[:：]\s*(.+)",
        ],
        "nozzle_type": [
            r"Nozzle type\s*油嘴类型\s*[:：]\s*(.+)",
            r"Nozzle type\s*[:：]\s*(.+)",
        ],
        "seat_geometry": [
            r"Seat geometry\s*座面\s*[:：]\s*(.+)",
            r"Seat geometry\s*[:：]\s*(.+)",
        ],
        "complaint": [
            r"Complaint\s*抱怨\s*[:：]\s*(.+)",
            r"Complaint\s*[:：]\s*(.+)",
        ],
    }

    for field, patterns in basic_patterns.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
            if matches:
                value = clean_extracted_value(matches[-1].group(1))
                if value:
                    fields[field] = value
                    break

    report_no_match = re.search(r"RBCD/EIS4No\.?\s*[:：]?\s*([A-Za-z0-9/_-]+)", text)
    if report_no_match:
        fields["report_no"] = clean_extracted_value(report_no_match.group(1))

    bm_no_match = re.search(r"BM-No\.?\s*[:：]?\s*([A-Za-z0-9/_-]+)", text)
    if bm_no_match:
        fields["bm_no"] = clean_extracted_value(bm_no_match.group(1))

    customer_no_match = re.search(r"Customer-No\.?\s*[:：]?\s*([A-Za-z0-9/_-]+)", text)
    if customer_no_match:
        fields["customer_no"] = clean_extracted_value(customer_no_match.group(1))

    job_problem = clean_plain_text(
        extract_section(
            text,
            ["1. Job-/Problem explanation", "Job-/Problem explanation", "任务/问题描述"],
            ["## 2.", "Responsible departments"],
        )
    )
    if job_problem:
        fields["job_problem_explanation_en"] = job_problem
        fields["job_problem_explanation_cn"] = job_problem
        fields["problem_description"] = job_problem

    responsible = clean_plain_text(
        extract_section(
            text,
            ["2. Responsible departments", "Responsible departments", "责任部门"],
            ["## 3.", "Investigation results"],
        )
    )
    if responsible:
        fields["responsible_departments_en"] = [responsible]
        fields["responsible_departments_cn"] = [responsible]

    results_section = extract_section(
        text,
        ["3.1 Results", "Results 结果"],
        ["Measured values", "测量结果", "## 3.2", "Conclusion"],
    )
    results_clean = split_visual_and_measured_tables(results_section)

    if results_clean["plain_text"] or results_clean["visual_tables"]:
        fields["investigation_results"] = {
            "summary_text": clean_plain_text(results_clean["plain_text"]),
            "visual_inspection_tables": results_clean["visual_tables"],
        }

    measured_section = extract_section(
        text,
        ["Measured values", "Measured values (attachment 1)", "测量结果", "以下测量值需要注意"],
        ["## 3.2", "Conclusion"],
    )
    measured_clean = split_visual_and_measured_tables(measured_section)

    if measured_clean["plain_text"] or measured_clean["measured_tables"]:
        fields["measured_values"] = {
            "summary_text": clean_plain_text(measured_clean["plain_text"]),
            "measured_tables": measured_clean["measured_tables"],
        }

    conclusion = clean_plain_text(
        extract_section(
            text,
            ["3.2 Conclusion", "Conclusion 结论"],
            ["## 3.3", "Parts 零件"],
        )
    )
    if conclusion:
        fields["conclusion"] = {
            "conclusion_text": conclusion,
        }

    parts = clean_plain_text(
        extract_section(
            text,
            ["3.3 Parts", "Parts 零件"],
            ["## 4.", "Immediate measures"],
        )
    )
    if parts:
        fields["parts"] = {
            "parts_text": parts,
        }

    immediate_measures = clean_plain_text(
        extract_section(
            text,
            ["4. Immediate measures", "需立即实施的措施"],
            ["## 5.", "Further investigation"],
        )
    )

    further_investigation = clean_plain_text(
        extract_section(
            text,
            ["5. Further investigation", "进一步分析"],
            ["## 6.", "Measures against further problem"],
        )
    )

    prevention = clean_plain_text(
        extract_section(
            text,
            ["6. Measures against further problem", "问题预防措施"],
            ["## 7.", "Control of the efficiency"],
        )
    )

    efficiency = clean_plain_text(
        extract_section(
            text,
            ["7. Control of the efficiency of measures", "措施有效性控制"],
            ["## 8.", "Control of the measures"],
        )
    )

    control = clean_plain_text(
        extract_section(
            text,
            ["8. Control of the measures", "预防性措施结果控制"],
            ["BOSCH", "![]", "Customer 客户:"],
        )
    )

    if any([immediate_measures, further_investigation, prevention, efficiency, control]):
        fields["measures"] = {
            "immediate_measures": immediate_measures or "No measures initiated 无",
            "further_investigation": further_investigation or "No measures initiated 无",
            "measures_against_further_problem": prevention or "No measures initiated 无",
            "efficiency_control": efficiency or "No measures initiated 无",
            "result_control": control or "No measures initiated 无",
        }

    return fields


def extract_section(
    text: str,
    start_titles: list[str],
    stop_titles: list[str] | None = None,
) -> str:
    if stop_titles is None:
        stop_titles = []

    lines = text.splitlines()
    start_index = None

    for i, line in enumerate(lines):
        clean = line.strip().strip("#").strip()

        for title in start_titles:
            if title.lower() in clean.lower():
                start_index = i + 1
                break

        if start_index is not None:
            break

    if start_index is None:
        return ""

    collected = []

    default_stop_markers = [
        "===== SOURCE:",
        "## 1.",
        "## 2.",
        "## 3.",
        "## 3.1",
        "## 3.2",
        "## 3.3",
        "## 4.",
        "## 5.",
        "## 6.",
        "## 7.",
        "## 8.",
        "Customer 客户:",
        "Type of test",
        "Project 项目:",
        "Nozzle type",
        "Seat geometry",
        "Complaint",
    ]

    all_stop_markers = default_stop_markers + stop_titles

    for line in lines[start_index:]:
        stripped = line.strip()

        if collected:
            for marker in all_stop_markers:
                if stripped.lower().startswith(marker.lower()):
                    return "\n".join(collected).strip()

        if collected and stripped.startswith("## "):
            return "\n".join(collected).strip()

        collected.append(line)

        if len("\n".join(collected)) > 5000:
            break

    return "\n".join(collected).strip()


# ============================================================
# HTML 渲染
# ============================================================

def render_simple_table(data: dict) -> str:
    if not isinstance(data, dict):
        data = {"value": data}

    rows = []

    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value_text = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            value_text = str(value or "")

        rows.append(
            f"""
            <tr>
                <th>{html.escape(str(key))}</th>
                <td>{html.escape(value_text)}</td>
            </tr>
            """
        )

    return f"""
    <table class="info-table">
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """


def render_matrix_table(table: list[list[str]], title: str = "") -> str:
    if not table:
        return ""

    rows_html = []
    max_cols = max(len(row) for row in table) if table else 0

    for row_index, row in enumerate(table):
        cells = []

        for cell in row:
            tag = "th" if row_index == 0 else "td"
            cells.append(f"<{tag}>{html.escape(str(cell))}</{tag}>")

        while len(cells) < max_cols:
            cells.append("<td></td>")

        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    title_html = f"<h4>{html.escape(title)}</h4>" if title else ""

    return f"""
    {title_html}
    <div class="table-scroll">
        <table class="matrix-table">
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    </div>
    """


def render_text_block(text: str) -> str:
    text = clean_plain_text(text)

    if not text:
        return "<p class='empty'>-</p>"

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)


def render_investigation_results(data: dict) -> str:
    if not isinstance(data, dict):
        return render_text_block(str(data))

    html_parts = []

    summary = data.get("summary_text") or data.get("result_text") or ""

    if summary:
        html_parts.append("<h4>Summary 结果描述</h4>")
        html_parts.append(render_text_block(summary))

    visual_tables = data.get("visual_inspection_tables") or []

    for i, table in enumerate(visual_tables, start=1):
        html_parts.append(
            render_matrix_table(table, f"Visual Inspection 目测检查表 {i}")
        )

    if not html_parts:
        html_parts.append("<p class='empty'>-</p>")

    return "\n".join(html_parts)


def render_measured_values(data: dict) -> str:
    if not isinstance(data, dict):
        return render_text_block(str(data))

    html_parts = []

    summary = data.get("summary_text") or data.get("measured_text") or ""

    if summary:
        html_parts.append("<h4>Summary 测量说明</h4>")
        html_parts.append(render_text_block(summary))

    measured_tables = data.get("measured_tables") or []

    for i, table in enumerate(measured_tables, start=1):
        html_parts.append(
            render_matrix_table(table, f"Measured Table 测量表 {i}")
        )

    if not html_parts:
        html_parts.append(
            "<p class='empty'>未从历史知识库中提取到明确测量值。</p>"
        )

    return "\n".join(html_parts)


def render_image_gallery(images: list[dict], title: str) -> str:
    if not images:
        return "<p class='empty'>No images available. 未检索到图片。</p>"

    cards = []

    for index, item in enumerate(images, start=1):
        url = item.get("url", "")
        filename = item.get("filename", f"image_{index}")

        if not url:
            continue

        cards.append(
            f"""
            <div class="image-card">
                <img src="{html.escape(url)}" alt="{html.escape(filename)}" />
                <div class="image-caption">
                    <b>{html.escape(title)} {index}</b><br />
                    {html.escape(filename)}
                </div>
            </div>
            """
        )

    if not cards:
        return "<p class='empty'>No images available. 未检索到图片。</p>"

    return f"""
    <div class="image-grid">
        {''.join(cards)}
    </div>
    """


def build_report_html(
    report_json: dict,
    merged_image_observation: dict,
    rag_context_preview: str,
    pdf_url: str = "",
) -> str:
    title = report_json.get("report_meta", {}).get(
        "report_title",
        "Nozzle Investigation Report",
    )

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <title>{html.escape(title)}</title>
    <style>
        body {{
            margin: 0;
            padding: 40px;
            background: #eef3f8;
            font-family: Arial, "Microsoft YaHei", sans-serif;
            color: #172033;
        }}

        .container {{
            max-width: 1120px;
            margin: 0 auto;
            background: #ffffff;
            padding: 36px;
            border-radius: 18px;
            box-shadow: 0 12px 35px rgba(15, 23, 42, 0.10);
        }}

        .print-bar {{
            position: sticky;
            top: 0;
            z-index: 20;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-bottom: 18px;
        }}

        .print-btn {{
            border: none;
            background: #2563eb;
            color: white;
            padding: 10px 18px;
            border-radius: 10px;
            font-weight: 700;
            cursor: pointer;
        }}

        h1 {{
            margin: 0;
            font-size: 30px;
            padding-bottom: 16px;
            border-bottom: 3px solid #2563eb;
        }}

        h2 {{
            margin-top: 36px;
            font-size: 22px;
            border-left: 5px solid #2563eb;
            padding-left: 12px;
        }}

        h4 {{
            margin: 18px 0 10px;
            color: #1e3a8a;
        }}

        p {{
            line-height: 1.7;
            margin: 8px 0;
        }}

        .note {{
            margin-top: 18px;
            padding: 14px 18px;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 12px;
            color: #1e3a8a;
        }}

        .info-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 14px;
            overflow: hidden;
            border-radius: 12px;
        }}

        .info-table th {{
            width: 240px;
            text-align: left;
            background: #f8fafc;
            color: #334155;
            font-weight: 700;
        }}

        .info-table th,
        .info-table td {{
            border: 1px solid #dbe3ec;
            padding: 12px 14px;
            vertical-align: top;
            font-size: 14px;
        }}

        .table-scroll {{
            width: 100%;
            overflow-x: auto;
            margin-top: 12px;
            border: 1px solid #dbe3ec;
            border-radius: 12px;
        }}

        .matrix-table {{
            width: 100%;
            min-width: 900px;
            border-collapse: collapse;
            background: #ffffff;
        }}

        .matrix-table th {{
            background: #eaf2ff;
            color: #1e3a8a;
            font-weight: 700;
        }}

        .matrix-table th,
        .matrix-table td {{
            border: 1px solid #dbe3ec;
            padding: 10px 12px;
            vertical-align: top;
            font-size: 13px;
            line-height: 1.5;
        }}

        .matrix-table tr:nth-child(even) td {{
            background: #f8fafc;
        }}

        .image-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 18px;
            margin-top: 16px;
        }}

        .image-card {{
            border: 1px solid #dbe3ec;
            border-radius: 14px;
            overflow: hidden;
            background: #ffffff;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
        }}

        .image-card img {{
            width: 100%;
            height: 210px;
            object-fit: contain;
            background: #f8fafc;
            display: block;
        }}

        .image-caption {{
            padding: 10px 12px;
            font-size: 12px;
            color: #475569;
            border-top: 1px solid #e2e8ec;
        }}

        .empty {{
            color: #64748b;
            font-style: italic;
        }}

        details {{
            margin-top: 30px;
        }}

        summary {{
            cursor: pointer;
            color: #2563eb;
            font-weight: 700;
        }}

        pre {{
            white-space: pre-wrap;
            word-break: break-word;
            background: #0f172a;
            color: #e5e7eb;
            padding: 16px;
            border-radius: 12px;
            font-size: 12px;
            line-height: 1.6;
            overflow: auto;
        }}

        @media print {{
            body {{
                background: white;
                padding: 0;
            }}

            .container {{
                box-shadow: none;
                border-radius: 0;
                max-width: none;
            }}

            .print-bar {{
                display: none;
            }}

            details {{
                display: none;
            }}

            .image-card {{
                break-inside: avoid;
                page-break-inside: avoid;
            }}

            .table-scroll {{
                overflow: visible;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">
        <div class="print-bar">
            <a class="print-btn" href="{html.escape(pdf_url)}" target="_blank" rel="noreferrer">
                下载 PDF 报告
            </a>
        </div>

        <h1>{html.escape(title)}</h1>

        <div class="note">
            This report was generated automatically by Engineering Report System.
            <br />
            本报告由工程报告系统自动生成，字段内容来自前端输入和 RAG 历史知识库。
        </div>

        <h2>Basic Information 基本信息</h2>
        {render_simple_table(report_json.get("test_basic_info", {}))}

        <h2>Image Observation 图片综合分析</h2>
        {render_simple_table(merged_image_observation)}

        <h2>Uploaded Images 上传图片</h2>
        {render_image_gallery(report_json.get("report_images", {}).get("uploaded_images", []), "Uploaded Image")}

        <h2>Historical RAG Images 历史报告图片</h2>
        {render_image_gallery(report_json.get("report_images", {}).get("rag_images", []), "RAG Image")}

        <h2>Job-/Problem Explanation 任务/问题描述</h2>
        {render_simple_table(report_json.get("job_problem_explanation", {}))}

        <h2>Responsible Departments 责任部门</h2>
        {render_simple_table(report_json.get("responsible_departments", {}))}

        <h2>Investigation Results 检测结果</h2>
        {render_investigation_results(report_json.get("investigation_results", {}))}

        <h2>Measured Values 测量结果</h2>
        {render_measured_values(report_json.get("measured_values", {}))}

        <h2>Conclusion 结论</h2>
        {render_simple_table(report_json.get("conclusion", {}))}

        <h2>Parts 零件</h2>
        {render_simple_table(report_json.get("parts", {}))}

        <h2>Measures 措施</h2>
        {render_simple_table(report_json.get("measures", {}))}

        <details>
            <summary>RAG Context Preview 知识库检索片段</summary>
            <pre>{html.escape(rag_context_preview or "未检索到历史知识库内容。")}</pre>
        </details>

        <details>
            <summary>Full JSON 完整结构化数据</summary>
            <pre>{html.escape(json.dumps(report_json, ensure_ascii=False, indent=2))}</pre>
        </details>
    </div>
</body>
</html>
"""

def register_pdf_fonts():
    """
    注册中文字体。
    STSong-Light 是 ReportLab 内置 CID 字体，不需要额外字体文件。
    """
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    except Exception:
        pass


def make_pdf_styles():
    register_pdf_fonts()

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "PdfTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    h2_style = ParagraphStyle(
        "PdfHeading2",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=12,
        spaceAfter=8,
    )

    h3_style = ParagraphStyle(
        "PdfHeading3",
        parent=styles["Heading3"],
        fontName="STSong-Light",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceBefore=8,
        spaceAfter=6,
    )

    normal_style = ParagraphStyle(
        "PdfNormal",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=9,
        leading=13,
        alignment=TA_LEFT,
    )

    small_style = ParagraphStyle(
        "PdfSmall",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=7,
        leading=10,
    )

    return {
        "title": title_style,
        "h2": h2_style,
        "h3": h3_style,
        "normal": normal_style,
        "small": small_style,
    }


def pdf_escape_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value)

    text = clean_plain_text(text)
    text = html.escape(text)
    text = text.replace("\n", "<br/>")
    return text


def make_key_value_table(data: Any, styles: dict, col1_width: float, col2_width: float) -> Table:
    if not isinstance(data, dict):
        data = {"value": data}

    table_data = []

    for key, value in data.items():
        table_data.append(
            [
                Paragraph(pdf_escape_text(key), styles["normal"]),
                Paragraph(pdf_escape_text(value), styles["normal"]),
            ]
        )

    if not table_data:
        table_data = [[Paragraph("-", styles["normal"]), Paragraph("-", styles["normal"])]]

    table = Table(table_data, colWidths=[col1_width, col2_width], repeatRows=0)

    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    return table


def make_matrix_table(matrix: list[list[str]], styles: dict, doc_width: float) -> Table | None:
    if not matrix:
        return None

    max_cols = max(len(row) for row in matrix)
    if max_cols <= 0:
        return None

    # 限制列宽，列太多时会很窄，但不会爆版
    col_width = doc_width / max_cols
    col_widths = [col_width] * max_cols

    table_data = []

    for row in matrix:
        new_row = []
        for cell in row:
            new_row.append(Paragraph(pdf_escape_text(cell), styles["small"]))

        while len(new_row) < max_cols:
            new_row.append(Paragraph("", styles["small"]))

        table_data.append(new_row)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    return table


def make_pdf_image(image_path: str, max_width: float, max_height: float):
    path = Path(image_path)

    if not path.exists():
        return None

    try:
        reader = ImageReader(str(path))
        img_width, img_height = reader.getSize()

        if img_width <= 0 or img_height <= 0:
            return None

        scale = min(max_width / img_width, max_height / img_height)
        final_width = img_width * scale
        final_height = img_height * scale

        return Image(str(path), width=final_width, height=final_height)
    except Exception as e:
        print("PDF 图片读取失败：", image_path, e)
        return None


def add_pdf_section_title(story: list, title: str, styles: dict):
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(title, styles["h2"]))
    story.append(Spacer(1, 2 * mm))


def add_pdf_text(story: list, text: str, styles: dict):
    text = clean_plain_text(text)

    if not text:
        story.append(Paragraph("-", styles["normal"]))
        return

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    for p in paragraphs:
        story.append(Paragraph(pdf_escape_text(p), styles["normal"]))
        story.append(Spacer(1, 1.5 * mm))


def add_pdf_images(story: list, images: list[dict], title: str, styles: dict, doc_width: float):
    add_pdf_section_title(story, title, styles)

    if not images:
        story.append(Paragraph("No images available. 未检索到图片。", styles["normal"]))
        return

    for index, item in enumerate(images, start=1):
        file_path = item.get("file_path") or item.get("source")
        filename = item.get("filename", f"image_{index}")

        if not file_path:
            continue

        story.append(Paragraph(f"{title} {index}: {pdf_escape_text(filename)}", styles["h3"]))

        pdf_img = make_pdf_image(
            image_path=file_path,
            max_width=doc_width,
            max_height=95 * mm,
        )

        if pdf_img:
            story.append(pdf_img)
            story.append(Spacer(1, 5 * mm))
        else:
            story.append(Paragraph(f"Image not found: {pdf_escape_text(file_path)}", styles["normal"]))

    story.append(Spacer(1, 4 * mm))


def add_investigation_results_pdf(story: list, data: dict, styles: dict, doc_width: float):
    add_pdf_section_title(story, "Investigation Results 检测结果", styles)

    if not isinstance(data, dict):
        add_pdf_text(story, str(data), styles)
        return

    summary = data.get("summary_text") or data.get("result_text") or ""

    if summary:
        story.append(Paragraph("Summary 结果描述", styles["h3"]))
        add_pdf_text(story, summary, styles)

    visual_tables = data.get("visual_inspection_tables") or []

    for i, matrix in enumerate(visual_tables, start=1):
        story.append(Paragraph(f"Visual Inspection 目测检查表 {i}", styles["h3"]))

        table = make_matrix_table(matrix, styles, doc_width)
        if table:
            story.append(table)
            story.append(Spacer(1, 4 * mm))

    if not summary and not visual_tables:
        story.append(Paragraph("-", styles["normal"]))


def add_measured_values_pdf(story: list, data: dict, styles: dict, doc_width: float):
    add_pdf_section_title(story, "Measured Values 测量结果", styles)

    if not isinstance(data, dict):
        add_pdf_text(story, str(data), styles)
        return

    summary = data.get("summary_text") or data.get("measured_text") or data.get("note") or ""

    if summary:
        story.append(Paragraph("Summary 测量说明", styles["h3"]))
        add_pdf_text(story, summary, styles)

    measured_tables = data.get("measured_tables") or []

    for i, matrix in enumerate(measured_tables, start=1):
        story.append(Paragraph(f"Measured Table 测量表 {i}", styles["h3"]))

        table = make_matrix_table(matrix, styles, doc_width)
        if table:
            story.append(table)
            story.append(Spacer(1, 4 * mm))

    if not summary and not measured_tables:
        story.append(Paragraph("未从历史知识库中提取到明确测量值。", styles["normal"]))


def build_report_pdf(
    report_json: dict,
    merged_image_observation: dict,
    pdf_path: Path,
):
    register_pdf_fonts()
    styles = make_pdf_styles()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    story = []
    doc_width = doc.width

    title = report_json.get("report_meta", {}).get(
        "report_title",
        "Nozzle Investigation Report",
    )

    story.append(Paragraph(pdf_escape_text(title), styles["title"]))
    story.append(
        Paragraph(
            "This report was generated automatically by Engineering Report System.<br/>"
            "本报告由工程报告系统自动生成，字段内容来自前端输入和 RAG 历史知识库。",
            styles["normal"],
        )
    )
    story.append(Spacer(1, 6 * mm))

    add_pdf_section_title(story, "Basic Information 基本信息", styles)
    story.append(
        make_key_value_table(
            report_json.get("test_basic_info", {}),
            styles,
            col1_width=45 * mm,
            col2_width=doc_width - 45 * mm,
        )
    )

    add_pdf_section_title(story, "Image Observation 图片综合分析", styles)
    story.append(
        make_key_value_table(
            merged_image_observation,
            styles,
            col1_width=45 * mm,
            col2_width=doc_width - 45 * mm,
        )
    )

    report_images = report_json.get("report_images", {})
    uploaded_images = report_images.get("uploaded_images", [])
    rag_images = report_images.get("rag_images", [])

    add_pdf_images(
        story=story,
        images=uploaded_images,
        title="Uploaded Images 上传图片",
        styles=styles,
        doc_width=doc_width,
    )

    add_pdf_images(
        story=story,
        images=rag_images,
        title="Historical RAG Images 历史报告图片",
        styles=styles,
        doc_width=doc_width,
    )

    add_pdf_section_title(story, "Job-/Problem Explanation 任务/问题描述", styles)
    story.append(
        make_key_value_table(
            report_json.get("job_problem_explanation", {}),
            styles,
            col1_width=45 * mm,
            col2_width=doc_width - 45 * mm,
        )
    )

    add_pdf_section_title(story, "Responsible Departments 责任部门", styles)
    story.append(
        make_key_value_table(
            report_json.get("responsible_departments", {}),
            styles,
            col1_width=45 * mm,
            col2_width=doc_width - 45 * mm,
        )
    )

    add_investigation_results_pdf(
        story,
        report_json.get("investigation_results", {}),
        styles,
        doc_width,
    )

    add_measured_values_pdf(
        story,
        report_json.get("measured_values", {}),
        styles,
        doc_width,
    )

    add_pdf_section_title(story, "Conclusion 结论", styles)
    story.append(
        make_key_value_table(
            report_json.get("conclusion", {}),
            styles,
            col1_width=45 * mm,
            col2_width=doc_width - 45 * mm,
        )
    )

    add_pdf_section_title(story, "Parts 零件", styles)
    story.append(
        make_key_value_table(
            report_json.get("parts", {}),
            styles,
            col1_width=45 * mm,
            col2_width=doc_width - 45 * mm,
        )
    )

    add_pdf_section_title(story, "Measures 措施", styles)
    story.append(
        make_key_value_table(
            report_json.get("measures", {}),
            styles,
            col1_width=55 * mm,
            col2_width=doc_width - 55 * mm,
        )
    )

    doc.build(story)