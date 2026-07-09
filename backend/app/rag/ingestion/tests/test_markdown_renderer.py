from __future__ import annotations

from app.rag.ingestion.markdown_renderer import render_markdown
from app.rag.schemas.pdecr_case_schema import (
    PdecrCase,
    PdecrMetadata,
    PdecrModules,
)

_REQUIRED_SECTIONS = [
    "## 1. Basic Information",
    "## 2. Change Reason",
    "## 3. Current Design",
    "## 4. Change Proposal",
    "## 5. Impact Analysis",
    "## 6. Validation Plan",
    "## 7. Implementation Plan",
    "## 8. Risk Analysis",
    "## 9. Tasks",
    "## 10. Approval Summary",
    "## 11. Attachments",
    "## 12. Extraction Quality",
]


def test_markdown_renderer_outputs_required_sections() -> None:
    case = PdecrCase(
        case_id="PDECR_24_093",
        metadata=PdecrMetadata(dc_no="24_093", customer_project=["JIM-493"]),
        modules=PdecrModules(change_reason="首次样件释放"),
    )
    md = render_markdown(case)

    assert md.startswith("# PDECR_24_093")
    for section in _REQUIRED_SECTIONS:
        assert section in md, f"缺少章节: {section}"
    # 抽不到的模块要有明确占位，而不是空白
    assert "Not extracted" in md
