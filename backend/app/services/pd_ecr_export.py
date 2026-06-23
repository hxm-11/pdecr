from __future__ import annotations

import csv
import html
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Literal

from app.services.pd_ecr_case_paths import REPORTS_DIR
from app.services.pd_ecr_generation import get_cached_draft
from app.services.pd_ecr_schema import BasicReportExport, ExportFormat, GeneratedDraft


def export_v1_draft(
    *,
    draft_id: str,
    export_format: Literal["html", "csv"] = "html",
    draft: GeneratedDraft | None = None,
) -> BasicReportExport:
    draft = draft or get_cached_draft(draft_id)
    if draft is None:
        raise ValueError(f"Draft not found: {draft_id}")

    source_files: list[str] = []
    for module in draft.modules:
        for source_file in module.source_files:
            if source_file and source_file not in source_files:
                source_files.append(source_file)

    export = BasicReportExport(
        export_id=f"export-{uuid.uuid4().hex[:12]}",
        draft_id=draft.draft_id,
        format=ExportFormat(export_format),
        input_snapshot=draft.input_snapshot,
        similar_cases=draft.similar_cases,
        modules=draft.modules,
        source_files=source_files,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{export.export_id}.{export_format}"
    path = REPORTS_DIR / filename

    if export_format == "csv":
        content = render_csv(draft)
    else:
        content = render_html(draft)
    path.write_text(content, encoding="utf-8")
    export = export.model_copy(update={"download_url": f"/static/reports/{filename}"})
    return export


def render_html(draft: GeneratedDraft) -> str:
    input_rows = "".join(
        f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in draft.input_snapshot.model_dump(mode="json").items()
    )
    similar_rows = "".join(
        "<tr>"
        f"<td>{item.rank}</td>"
        f"<td>{html.escape(item.case_id)}</td>"
        f"<td>{html.escape(item.source_file)}</td>"
        f"<td>{html.escape(', '.join(item.matched_fields))}</td>"
        f"<td>{item.similarity_score}</td>"
        "</tr>"
        for item in draft.similar_cases
    )
    module_sections = "".join(
        "<section>"
        f"<h2>{html.escape(module.title)}</h2>"
        f"<p><strong>Status:</strong> {'Needs human input' if module.needs_human_input else 'Evidence-backed draft'}</p>"
        f"<p>{html.escape(module.summary)}</p>"
        f"<pre>{html.escape(str(module.content))}</pre>"
        f"<p><strong>Source cases:</strong> {html.escape(', '.join(module.source_cases) or '-')}</p>"
        f"<p><strong>Source files:</strong> {html.escape(', '.join(module.source_files) or '-')}</p>"
        f"<p><strong>Warnings:</strong> {html.escape('; '.join(module.warnings) or '-')}</p>"
        "</section>"
        for module in draft.modules
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>PD-ECR V1 MVP Draft {html.escape(draft.draft_id)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1c1917; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #ddd6ce; padding: 8px; text-align: left; }}
    th {{ background: #f5f5f4; }}
    section {{ border-top: 2px solid #92400e; padding-top: 16px; margin-top: 24px; }}
    pre {{ white-space: pre-wrap; background: #fafaf9; padding: 12px; border: 1px solid #e7e5e4; }}
    .badge {{ display: inline-block; background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 999px; }}
  </style>
</head>
<body>
  <h1>PD-ECR V1 MVP Draft</h1>
  <p class="badge">{html.escape(str(draft.draft_status.value))}</p>
  <p>Draft ID: {html.escape(draft.draft_id)} · Generated at: {html.escape(draft.generated_at)}</p>
  <h2>Submitted Input</h2>
  <table>{input_rows}</table>
  <h2>Similar Historical Cases</h2>
  <table><tr><th>Rank</th><th>Case</th><th>Source file</th><th>Matched fields</th><th>Score</th></tr>{similar_rows}</table>
  <h2>Generated Modules</h2>
  {module_sections}
</body>
</html>"""


def render_csv(draft: GeneratedDraft) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["draft_id", draft.draft_id])
    writer.writerow(["draft_status", draft.draft_status.value])
    writer.writerow([])
    writer.writerow(["module_id", "title", "summary", "content", "source_cases", "source_files", "needs_human_input", "warnings"])
    for module in draft.modules:
        writer.writerow(
            [
                module.module_id.value,
                module.title,
                module.summary,
                module.content,
                "; ".join(module.source_cases),
                "; ".join(module.source_files),
                module.needs_human_input,
                "; ".join(module.warnings),
            ]
        )
    return output.getvalue()
