import html
import json
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.models import PdEcrCase, User
from app.services.pd_ecr_audit_service import write_activity
from app.services.pd_ecr_case_service import list_modules, serialize_case, serialize_module


REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def export_case(
    *,
    session: Session,
    case: PdEcrCase,
    current_user: User,
    export_format: str = "html",
) -> dict[str, Any]:
    modules = [serialize_module(module) for module in list_modules(session=session, case_id=case.id)]
    payload = {
        "case": serialize_case(case),
        "modules": modules,
        "draft_status": "COLLABORATIVE_DRAFT" if case.status != "closed" else "CLOSED",
    }

    export_id = str(uuid.uuid4())
    if export_format == "json":
        filename = f"pd_ecr_{case.case_no}_{export_id}.json"
        path = REPORTS_DIR / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        filename = f"pd_ecr_{case.case_no}_{export_id}.html"
        path = REPORTS_DIR / filename
        path.write_text(render_html(payload), encoding="utf-8")

    write_activity(
        session=session,
        action="case.exported",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="export",
        target_id=export_id,
        metadata={"format": export_format, "filename": filename},
    )
    session.commit()
    return {
        "export_id": export_id,
        "case_id": str(case.id),
        "format": export_format,
        "draft_status": payload["draft_status"],
        "url": f"/static/reports/{filename}",
        "source_files": sorted(
            {
                source_file
                for module in modules
                for source_file in module.get("source_files", [])
            }
        ),
    }


def render_html(payload: dict[str, Any]) -> str:
    case = payload["case"]
    module_sections = []
    for module in payload["modules"]:
        content = module.get("content_md") or json.dumps(
            module.get("content_json") or {}, ensure_ascii=False, indent=2
        )
        module_sections.append(
            f"""
            <section>
              <h2>{html.escape(module.get("title") or module.get("module_id") or "")}</h2>
              <pre>{html.escape(content)}</pre>
              <p><strong>Sources:</strong> {html.escape(", ".join(module.get("source_files") or []))}</p>
            </section>
            """
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(case.get("case_no") or "PD-ECR")}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2933; }}
    h1 {{ margin-bottom: 4px; }}
    section {{ border-top: 1px solid #ddd; padding-top: 16px; margin-top: 20px; }}
    pre {{ white-space: pre-wrap; font-family: inherit; line-height: 1.5; }}
    .meta {{ color: #52606d; }}
  </style>
</head>
<body>
  <h1>{html.escape(case.get("case_no") or "PD-ECR")}</h1>
  <p class="meta">{html.escape(case.get("title") or "")} · {html.escape(case.get("status") or "")}</p>
  {''.join(module_sections)}
</body>
</html>"""
