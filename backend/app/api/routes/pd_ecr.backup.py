from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "templates"
REPORTS_DIR = BASE_DIR / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/generate-report")
def generate_report(data: PdEcrInput):
    user_input = data.model_dump()
    print("后端收到的数据：", user_input)

    try:
        llm_result = call_llm(user_input)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"调用大模型失败：{str(e)}"
        )

    context = {
        **user_input,
        **llm_result,
        "basic_info": llm_result.get("basic_info", {}),
        "change_request": llm_result.get("change_request", {}),
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False
    )

    template_files = [
        "Example of affected actions.md",
        "impact.md",
        "implementation.md",
        "Revision history.md",
    ]

    report_parts = []

    for tplfile in template_files:
        tpl = env.get_template(tplfile)
        report_parts.append(tpl.render(context))

    report_content = "\n\n---\n\n".join(report_parts)

    dc_no = user_input.get("dc_no") or "unknown"
    filename = f"report_{dc_no}.md"
    report_path = REPORTS_DIR / filename

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return {
        "message": "生成成功",
        "url": f"/static/reports/{filename}"
    }