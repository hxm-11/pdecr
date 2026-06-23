import fitz
from pathlib import Path


RAW_PDF_DIR = Path("../raw_files/pdf")
OUT_MD_DIR = Path("../markdown_files")
OUT_MD_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n\n".join(lines)


def pdf_to_markdown(pdf_path: Path):
    doc = fitz.open(pdf_path)
    all_text = []

    for page_index, page in enumerate(doc, start=1):
        text = page.get_text("text")
        text = clean_text(text)

        if text:
            all_text.append(f"## 第 {page_index} 页\n\n{text}")

    content = f"""# 报告名称：{pdf_path.stem}

## 报告元信息
- 原始文件名：{pdf_path.name}
- 文件类型：PDF
- 报告类型：待补充
- 项目名称：待补充
- 报告日期：待补充
- 关键词：待补充

## 报告正文

{chr(10).join(all_text)}
"""

    out_path = OUT_MD_DIR / f"{pdf_path.stem}.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"已转换：{pdf_path.name} -> {out_path.name}")


if __name__ == "__main__":
    for pdf_file in RAW_PDF_DIR.glob("*.pdf"):
        pdf_to_markdown(pdf_file)