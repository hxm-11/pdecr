from pathlib import Path
import os
import sys
import subprocess
import shutil
import traceback

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR / "excel_source"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
MINERU_OUTPUT_DIR = BASE_DIR / "mineru_output"

KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
MINERU_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


KEYWORDS = [
    "DC No",
    "Date",
    "Customer project",
    "Customer project Name",
    "MCR No",
    "Product No",
    "Component No",
    "Initiator",
    "Reason of changes",
    "Reason of change",
    "Current design",
    "Change proposal",
    "Remarks",
    "Impact analysis",
    "Function & Performance",
    "Interface and Appearance",
    "Reliability and robustness",
    "Manufacturing",
    "assembly",
    "testing",
    "supplier part",
    "System",
    "Hardware",
    "Software",
    "Calibration",
    "Quality Assurance",
    "Trial run",
    "Capability",
    "CMK",
    "MSA",
    "MAE release",
    "BOM check",
    "Test report",
    "Implementation",
    "Approval",
    "Development",
    "Purchasing",
    "MFE",
    "Quality",
    "COS",
    "MOEx",
    "LOG",
]


def clean(value):
    if value is None:
        return ""

    text = str(value).strip()
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = " ".join(text.split())
    return text


def row_to_text(row_values):
    values = [clean(v) for v in row_values]
    values = [v for v in values if v]

    if not values:
        return ""

    return " | ".join(values)


def is_relevant_row(text: str) -> bool:
    lower_text = text.lower()

    for kw in KEYWORDS:
        if kw.lower() in lower_text:
            return True

    if "☑" in text or "☐" in text:
        return True

    if " yes " in f" {lower_text} " or " no " in f" {lower_text} ":
        return True

    return False


def filter_markdown_by_keywords(md_text: str) -> str:
    """
    MinerU 输出的 Markdown 可能很长。
    这里保留包含关键词的行，以及其下一行，方便知识库检索。
    """
    lines = md_text.splitlines()
    kept = []

    for i, line in enumerate(lines):
        clean_line = clean(line)

        if not clean_line:
            continue

        if is_relevant_row(clean_line):
            kept.append(clean_line)

            if i + 1 < len(lines):
                next_line = clean(lines[i + 1])
                if next_line:
                    kept.append(next_line)

    # 如果关键词过滤后太少，说明可能关键词没匹配上，保留全文
    if len(kept) < 5:
        return md_text

    return "\n".join(kept)


def extract_pdf_text_with_pypdf(file_path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError("读取 PDF 需要安装 pypdf：python -m pip install pypdf")

    reader = PdfReader(str(file_path))
    pages = []

    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()

        if text:
            pages.append(f"## Page {page_no}\n{text}")

    return "\n\n".join(pages).strip()


def write_pdf_markdown(file_path: Path, parsed_by: str, md_text: str, extra_note: str = ""):
    filtered_text = filter_markdown_by_keywords(md_text)

    if not filtered_text.strip():
        filtered_text = (
            "PDF text extraction returned empty content. "
            "This file may be scanned or image-based; use MinerU/OCR for richer content."
        )

    output = []
    output.append("# Historical PD-ECR Case")
    output.append(f"Source file: {file_path.name}")
    output.append("")
    output.append("## File Type")
    output.append("PDF")
    output.append("")
    output.append("## Parsed By")
    output.append(parsed_by)
    output.append("")
    if extra_note:
        output.append("## Parser Note")
        output.append(extra_note)
        output.append("")
    output.append("## Extracted Content")
    output.append(filtered_text)
    output.append("")

    out_path = KNOWLEDGE_DIR / f"{file_path.stem}.md"
    out_path.write_text("\n".join(output), encoding="utf-8")

    print(f"已转换 PDF：{file_path.name} -> {out_path.name}")


def find_mineru_markdown(output_dir: Path, source_stem: str):
    """
    MinerU 输出目录层级可能因版本不同略有差异。
    所以这里递归查找所有 .md 文件。
    优先找文件名包含原始 PDF stem 的 md。
    """
    md_files = list(output_dir.rglob("*.md"))

    if not md_files:
        return None

    for md in md_files:
        if source_stem.lower() in md.stem.lower():
            return md

    # 如果找不到同名 md，就返回最新生成的 md
    md_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return md_files[0]


def run_mineru(file_path: Path, backend: str = "pipeline"):
    """
    调用 MinerU 转 PDF 为 Markdown。
    backend='pipeline' 更适合没有 GPU 的环境。
    如果你有 GPU，也可以改成 backend=None，使用默认方式。
    """
    if shutil.which("mineru") is None:
        raise RuntimeError(
            "未找到 mineru 命令。请先安装 MinerU：uv pip install -U \"mineru[all]\""
        )

    single_output_dir = MINERU_OUTPUT_DIR / file_path.stem
    single_output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mineru",
        "-p", str(file_path),
        "-o", str(single_output_dir),
    ]

    if backend:
        cmd.extend(["-b", backend])

    print("正在调用 MinerU：")
    print(" ".join(cmd))

    env = os.environ.copy()
    no_proxy_values = [
        value.strip()
        for key in ("NO_PROXY", "no_proxy")
        for value in env.get(key, "").split(",")
        if value.strip()
    ]
    for value in ["127.0.0.1", "localhost"]:
        if value not in no_proxy_values:
            no_proxy_values.append(value)
    env["NO_PROXY"] = ",".join(no_proxy_values)
    env["no_proxy"] = env["NO_PROXY"]
    env.setdefault("MINERU_MODEL_SOURCE", "modelscope")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"MinerU 解析失败：{file_path.name}\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    md_path = find_mineru_markdown(single_output_dir, file_path.stem)

    if md_path is None:
        raise RuntimeError(f"MinerU 已运行，但没有找到 Markdown 输出：{single_output_dir}")

    return md_path


def convert_pdf_with_mineru(file_path: Path):
    mineru_md_path = run_mineru(file_path, backend="pipeline")

    md_text = mineru_md_path.read_text(encoding="utf-8", errors="ignore")
    write_pdf_markdown(file_path, "MinerU", md_text)
    print(f"MinerU 原始输出：{mineru_md_path}")


def convert_pdf(file_path: Path):
    if shutil.which("mineru") is not None:
        convert_pdf_with_mineru(file_path)
        return

    text = extract_pdf_text_with_pypdf(file_path)
    write_pdf_markdown(
        file_path,
        "pypdf",
        text,
        "MinerU command was not found, so pypdf text extraction was used.",
    )


def main():
    pdf_files = list(SOURCE_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"没有找到 PDF 文件，请放到：{SOURCE_DIR}")
        return

    for f in pdf_files:
        if f.name.startswith("~$"):
            continue

        try:
            convert_pdf(f)
        except Exception as e:
            print(f"转换失败：{f.name}")
            print(f"错误：{e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
