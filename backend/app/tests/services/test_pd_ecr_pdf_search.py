from pathlib import Path

from app.api.routes import pd_ecr


def test_pdf_history_search_uses_docling_markdown_text(monkeypatch, tmp_path):
    pdf_dir = tmp_path / "PDECR_JIE_JIM"
    docling_dir = pdf_dir / "docling_output"
    docling_dir.mkdir(parents=True)
    (pdf_dir / "PDECR25_084_JIM_493.pdf").write_bytes(b"%PDF-1.4")
    (pdf_dir / "PDECR24_102_JIM_493.pdf").write_bytes(b"%PDF-1.4")
    (docling_dir / "PDECR25_084_JIM_493_docling.md").write_text(
        "历史案例内容：压差支架取消卡夹，D-sample change。",
        encoding="utf-8",
    )
    (docling_dir / "PDECR24_102_JIM_493_docling.md").write_text(
        "历史案例内容：DOC低涂敷测试样件放行。",
        encoding="utf-8",
    )

    monkeypatch.setattr(pd_ecr, "PDECR_JIE_JIM_PDF_DIR", pdf_dir)
    monkeypatch.setattr(pd_ecr, "JIE_JIM_METADATA_DIR", tmp_path / "missing")

    results = pd_ecr.search_pdecr_pdf_case_records(
        {"change_description": "压差支架取消卡夹"},
        top_k=1,
    )

    assert results[0]["case_id"] == "PDECR25_084"
    assert results[0]["score"] > 0
    assert "压差支架取消卡夹" in results[0]["search_text_preview"]


def test_historical_case_modules_are_rendered_from_templates_pre():
    results = pd_ecr.search_pdecr_pdf_case_records({"change_description": "压差支架"}, top_k=1)
    payload = pd_ecr.modules_from_pdf_case_record(results[0], {"change_description": "压差支架"})

    implementation = next(
        module for module in payload if module["id"] == "implementation-plan"
    )

    assert implementation["data"]["template_file"] == "5implementation_plan.md"
    assert "Step 6 Implementation Plan" in implementation["data"]["content"]
    assert implementation["source_cases"]


def test_case_modules_endpoint_resolves_pdf_folder_record(monkeypatch, tmp_path):
    pdf_dir = tmp_path / "PDECR_JIE_JIM"
    docling_dir = pdf_dir / "docling_output"
    docling_dir.mkdir(parents=True)
    (pdf_dir / "PDECR25_084_JIM_493.pdf").write_bytes(b"%PDF-1.4")
    (docling_dir / "PDECR25_084_JIM_493_docling.md").write_text(
        "历史案例内容：压差支架取消卡夹。",
        encoding="utf-8",
    )

    monkeypatch.setattr(pd_ecr, "PDECR_JIE_JIM_PDF_DIR", pdf_dir)
    monkeypatch.setattr(pd_ecr, "JIE_JIM_METADATA_DIR", tmp_path / "missing")

    payload = pd_ecr.get_pd_ecr_case_modules("PDECR25_084_JIM_493.pdf")

    assert payload["source"] == "history"
    assert payload["case"]["case_id"] == "PDECR25_084"
    assert any(module["id"] == "implementation-plan" for module in payload["modules"])
