from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import pickle
import uuid
from zipfile import ZIP_DEFLATED, ZipFile


def _write_minimal_checkbox_xlsx(path: Path) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Impact analysis&amp;QAC" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetData>
    <row r="49">
      <c r="B49" t="inlineStr"><is><t>Function Performance will be influenced?</t></is></c>
      <c r="D49" t="inlineStr"><is><t>no/否</t></is></c>
      <c r="E49" t="inlineStr"><is><t>yes/是</t></is></c>
    </row>
  </sheetData>
  <legacyDrawing r:id="rId1"/>
</worksheet>""",
        )
        zf.writestr(
            "xl/worksheets/_rels/sheet1.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
    Target="../drawings/vmlDrawing1.vml"/>
</Relationships>""",
        )
        zf.writestr(
            "xl/drawings/vmlDrawing1.vml",
            """<xml xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel">
 <v:shape id="_x0000_s1">
  <v:textbox><div><font>no/否</font></div></v:textbox>
  <x:ClientData ObjectType="Checkbox">
   <x:Anchor>3, 0, 48, 0, 3, 50, 49, 0</x:Anchor>
  </x:ClientData>
 </v:shape>
 <v:shape id="_x0000_s2">
  <v:textbox><div><font>yes/是</font></div></v:textbox>
  <x:ClientData ObjectType="Checkbox">
   <x:Anchor>4, 0, 48, 0, 4, 50, 49, 0</x:Anchor>
   <x:Checked>1</x:Checked>
  </x:ClientData>
 </v:shape>
</xml>""",
        )


def test_extracts_checkbox_controls_from_xlsx_xml_without_excel(tmp_path: Path) -> None:
    from app.rag.xlsx_controls import extract_xlsx_controls

    workbook = tmp_path / "controls.xlsx"
    _write_minimal_checkbox_xlsx(workbook)

    controls = extract_xlsx_controls(workbook)

    assert len(controls) == 2
    yes_control = next(item for item in controls if item["caption"] == "yes/是")
    no_control = next(item for item in controls if item["caption"] == "no/否")

    assert yes_control == {
        "type": "checkbox",
        "sheet": "Impact analysis&QAC",
        "cell": "E49",
        "caption": "yes/是",
        "checked": True,
        "value": "yes",
        "nearby_label": "Function Performance will be influenced?",
        "source": "xlsx_xml",
    }
    assert no_control["cell"] == "D49"
    assert no_control["checked"] is False
    assert no_control["value"] == "no"


def test_stage_parse_file_attaches_controls_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.services import pd_ecr_stage_service as stage_service

    workbook = tmp_path / "controls.xlsx"
    _write_minimal_checkbox_xlsx(workbook)
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "controls.md").write_text(
        "# Parsed workbook\n\nFunction Performance will be influenced?",
        encoding="utf-8",
    )

    monkeypatch.setattr(stage_service, "KNOWLEDGE_DIR", knowledge_dir)
    monkeypatch.setattr(stage_service.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        "app.rag.excel_to_markdown.convert_excel",
        lambda file_path: None,
    )
    monkeypatch.setattr(
        "app.rag.pdecr_llm_extractor.extract_with_llm_fallback",
        lambda cleaned, rule_based_extractor=None: {},
    )

    parsed = stage_service._parse_file(workbook, ".xlsx")

    controls = parsed["metadata"]["controls_json"]
    assert len(controls) == 2
    assert {
        "sheet": "Impact analysis&QAC",
        "cell": "E49",
        "caption": "yes/是",
        "checked": True,
        "value": "yes",
    }.items() <= controls[1].items()


def test_build_vector_chunks_includes_controls_and_table_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.services.pd_ecr_stage_service import _build_vector_chunks

    vector_dir = tmp_path / "vector"
    monkeypatch.setattr("app.rag.build_index.VECTOR_DIR", vector_dir)
    monkeypatch.setattr(
        "app.rag.pdecr_structured_extractor.extract_structured",
        lambda parsed: {},
    )
    monkeypatch.setattr(
        "app.rag.pdecr_structured_extractor.build_row_chunks",
        lambda structured, source_file, file_id: [],
    )

    doc_id = uuid.uuid4()
    doc = SimpleNamespace(
        id=doc_id,
        parsed_text="",
        original_filename="controls.xlsx",
        file_type="excel",
        metadata_json={
            "dc_no": "RBCE-PDECR2026006",
            "customer_project": "JP360",
            "product_no": "F03Z20046V-01",
            "controls_json": [
                {
                    "type": "checkbox",
                    "sheet": "Impact analysis&QAC",
                    "cell": "E49",
                    "caption": "yes/是",
                    "checked": True,
                    "value": "yes",
                    "nearby_label": "Function Performance will be influenced?",
                    "source": "xlsx_xml",
                }
            ],
        },
        sections_json=[],
        tables_json=[
            {
                "index": 0,
                "caption": "Step 6.1 Implementation check list",
                "headers": ["Department", "Y/N", "Description"],
                "rows": [["Development", "Y", "Change BOMs"]],
                "page_no": 1,
            }
        ],
    )
    case = SimpleNamespace(case_no="PD-ECR-JSON-001")

    count = _build_vector_chunks(doc, case)

    assert count == 2
    chunks_path = vector_dir / f"chunks_{doc_id.hex}.pkl"
    chunks = pickle.loads(chunks_path.read_bytes())

    control_chunk = next(
        chunk for chunk in chunks if chunk["document_type"] == "staged_excel_control"
    )
    assert control_chunk["metadata"]["value"] == "yes"
    assert control_chunk["metadata"]["checked"] is True
    assert control_chunk["metadata"]["cell"] == "E49"
    assert "Function Performance will be influenced?" in control_chunk["text"]

    table_chunk = next(
        chunk for chunk in chunks if chunk["document_type"] == "staged_excel_table_row"
    )
    assert table_chunk["metadata"]["table_caption"] == "Step 6.1 Implementation check list"
    assert table_chunk["metadata"]["row_index"] == 0
    assert "Development | Y | Change BOMs" in table_chunk["text"]


def test_source_extracted_metadata_preserves_tables_and_controls() -> None:
    from app.services.pd_ecr_stage_service import _build_source_extracted_metadata

    doc = SimpleNamespace(
        sections_json=[{"heading": "Impact analysis", "content": "content"}],
        tables_json=[{"caption": "Checklist", "rows": [["Development", "Y"]]}],
    )
    metadata = {
        "dc_no": "RBCE-PDECR2026006",
        "controls_json": [{"caption": "yes/是", "checked": True}],
    }

    extracted = _build_source_extracted_metadata(metadata, doc)

    assert extracted["dc_no"] == "RBCE-PDECR2026006"
    assert extracted["controls_json"] == [{"caption": "yes/是", "checked": True}]
    assert extracted["tables_json"] == [{"caption": "Checklist", "rows": [["Development", "Y"]]}]
    assert extracted["sections_json"] == [{"heading": "Impact analysis", "content": "content"}]
