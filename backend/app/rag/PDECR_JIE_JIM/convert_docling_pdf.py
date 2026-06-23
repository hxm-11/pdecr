from pathlib import Path
import tempfile
import json

# 关键：让 Docling 在 Windows 清理临时文件时报错时不要直接崩
_OriginalTemporaryDirectory = tempfile.TemporaryDirectory


class SafeTemporaryDirectory(_OriginalTemporaryDirectory):
    def __init__(self, *args, **kwargs):
        kwargs["ignore_cleanup_errors"] = True
        super().__init__(*args, **kwargs)


tempfile.TemporaryDirectory = SafeTemporaryDirectory

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


base_dir = Path(__file__).resolve().parent
out_dir = base_dir / "docling_output"
model_dir = Path(r"C:\docling_models")

out_dir.mkdir(parents=True, exist_ok=True)

pipeline_options = PdfPipelineOptions()
pipeline_options.artifacts_path = model_dir

# 使用 RapidOCR 中文模型；模型已放在 C:\docling_models
pipeline_options.do_ocr = True
pipeline_options.ocr_options = RapidOcrOptions(lang=["chinese"])

# 保留表格结构识别
pipeline_options.do_table_structure = True

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options
        )
    }
)

pdf_paths = sorted(base_dir.glob("*.pdf"))

print(f"Found {len(pdf_paths)} PDF files in {base_dir}")

for index, pdf_path in enumerate(pdf_paths, start=1):
    print(f"[{index}/{len(pdf_paths)}] Converting: {pdf_path.name}")
    md_path = out_dir / f"{pdf_path.stem}_docling.md"
    json_path = out_dir / f"{pdf_path.stem}_docling.json"

    try:
        result = converter.convert(pdf_path)
        doc = result.document

        md_path.write_text(doc.export_to_markdown(), encoding="utf-8")

        try:
            json_text = doc.export_to_json()
            json_path.write_text(json_text, encoding="utf-8")
        except Exception:
            json_obj = doc.export_to_dict()
            json_path.write_text(
                json.dumps(json_obj, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        print("Markdown saved to:", md_path)
        print("JSON saved to:", json_path)
    except Exception as e:
        print(f"Failed to convert {pdf_path.name}: {e}")
