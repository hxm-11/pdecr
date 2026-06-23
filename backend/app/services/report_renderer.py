import html
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = BASE_DIR / "rag"
GENERATED_DIR = RAG_DIR / "generated_reports"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _list_to_html(items: Any) -> str:
    if not items:
        return "<p>-</p>"

    if isinstance(items, str):
        return f"<p>{_escape(items)}</p>"

    if isinstance(items, list):
        lis = "".join(f"<li>{_escape(item)}</li>" for item in items)
        return f"<ul>{lis}</ul>"

    return f"<p>{_escape(items)}</p>"


def _dict_section_to_table(data: Dict[str, Any]) -> str:
    rows = []

    for key, value in data.items():
        if isinstance(value, (dict, list)):
            value_text = html.escape(str(value))
        else:
            value_text = _escape(value)

        rows.append(
            f"<tr><th>{_escape(key)}</th><td>{value_text}</td></tr>"
        )

    return f"<table>{''.join(rows)}</table>"


def render_nozzle_report_html(report: Dict[str, Any]) -> str:
    meta = report.get("report_meta", {})
    basic = report.get("test_basic_info", {})
    job = report.get("job_problem_explanation", {})
    dept = report.get("responsible_departments", {})
    img = report.get("image_analysis", {})
    inv = report.get("investigation_results", {})
    measured = report.get("measured_values", {})
    conclusion = report.get("conclusion", {})
    parts = report.get("parts", {})
    measures = report.get("measures", {})
    signatures = report.get("signatures", {})

    title = meta.get("report_title") or "Nozzle investigation 油嘴检测报告"

    html_text = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{_escape(title)}</title>
<style>
body {{
    font-family: Arial, "Microsoft YaHei", sans-serif;
    margin: 40px;
    color: #222;
    line-height: 1.6;
}}
h1 {{
    text-align: center;
    font-size: 26px;
    margin-bottom: 24px;
}}
h2 {{
    margin-top: 28px;
    border-bottom: 2px solid #333;
    padding-bottom: 6px;
}}
h3 {{
    margin-top: 18px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
}}
td, th {{
    border: 1px solid #888;
    padding: 8px;
    vertical-align: top;
}}
th {{
    background: #f3f3f3;
    width: 26%;
    text-align: left;
}}
.header-table td {{
    border: 1px solid #888;
}}
.small {{
    color: #666;
    font-size: 13px;
}}
.section {{
    margin-bottom: 20px;
}}
</style>
</head>
<body>

<h1>{_escape(title)}</h1>

<table class="header-table">
<tr>
    <th>Report No.</th>
    <td>{_escape(meta.get("report_no", ""))}</td>
    <th>BM-No.</th>
    <td>{_escape(meta.get("bm_no", ""))}</td>
</tr>
<tr>
    <th>Customer-No.</th>
    <td>{_escape(meta.get("customer_no", ""))}</td>
    <th>Date</th>
    <td>{_escape(meta.get("date", ""))}</td>
</tr>
<tr>
    <th>From</th>
    <td>{_escape(meta.get("department_from", ""))}</td>
    <th>Reference</th>
    <td>{_escape(meta.get("reference_person", ""))}</td>
</tr>
</table>

<h2>Basic Information 基本信息</h2>
{_dict_section_to_table(basic)}

<h2>1. Job-/Problem explanation 任务/问题描述</h2>
<p><b>EN:</b> {_escape(job.get("description_en", ""))}</p>
<p><b>CN:</b> {_escape(job.get("description_cn", ""))}</p>

<h2>2. Responsible departments 责任部门</h2>
<p><b>EN:</b></p>
{_list_to_html(dept.get("departments_en", []))}
<p><b>CN:</b></p>
{_list_to_html(dept.get("departments_cn", []))}

<h2>3. Investigation results 检测结果</h2>

<h3>3.1 Image Analysis 图片分析</h3>
<table>
<tr><th>Image summary</th><td>{_escape(img.get("image_summary", ""))}</td></tr>
<tr><th>Abnormal area</th><td>{_escape(img.get("abnormal_area", ""))}</td></tr>
<tr><th>Visible abnormalities</th><td>{_list_to_html(img.get("visible_abnormalities", []))}</td></tr>
<tr><th>Possible wear / defect features</th><td>{_list_to_html(img.get("possible_wear_features", img.get("possible_defect_types", [])))}</td></tr>
<tr><th>Possible non-defect explanations</th><td>{_list_to_html(img.get("possible_non_wear_explanations", img.get("possible_non_defect_explanations", [])))}</td></tr>
<tr><th>Image quality</th><td>{_escape(img.get("image_quality", ""))}</td></tr>
<tr><th>Need manual check</th><td>{_escape(img.get("need_manual_check", ""))}</td></tr>
</table>

<h3>3.2 Results 结果</h3>
<table>
<tr><th>Result summary EN</th><td>{_escape(inv.get("result_summary_en", ""))}</td></tr>
<tr><th>Result summary CN</th><td>{_escape(inv.get("result_summary_cn", ""))}</td></tr>
<tr><th>Seat wear 座面磨损</th><td>{_escape(inv.get("seat_wear", {}))}</td></tr>
<tr><th>Guidance wear 导向段磨损</th><td>{_escape(inv.get("guidance_wear", {}))}</td></tr>
<tr><th>Coating condition 镀层状态</th><td>{_escape(inv.get("coating_condition", {}))}</td></tr>
<tr><th>Deposit 积炭</th><td>{_escape(inv.get("deposit", {}))}</td></tr>
<tr><th>Cavitation 穴蚀</th><td>{_escape(inv.get("cavitation", {}))}</td></tr>
<tr><th>Corrosion 腐蚀</th><td>{_escape(inv.get("corrosion", {}))}</td></tr>
<tr><th>Mechanical damage 机械破损</th><td>{_escape(inv.get("mechanical_damage", {}))}</td></tr>
</table>

<h3>Measured values 测量结果</h3>
<p>{_escape(measured.get("summary", ""))}</p>
<h4>Abnormal values</h4>
{_list_to_html(measured.get("abnormal_values", []))}

<h2>3.2 Conclusion 结论</h2>
<p><b>EN:</b> {_escape(conclusion.get("conclusion_en", ""))}</p>
<p><b>CN:</b> {_escape(conclusion.get("conclusion_cn", ""))}</p>
<table>
<tr><th>Function influence</th><td>{_escape(conclusion.get("function_influence", ""))}</td></tr>
<tr><th>Risk level</th><td>{_escape(conclusion.get("risk_level", ""))}</td></tr>
<tr><th>Confidence</th><td>{_escape(conclusion.get("confidence", ""))}</td></tr>
</table>

<h2>3.3 Parts 零件</h2>
<table>
<tr><th>Handling</th><td>{_escape(parts.get("handling", ""))}</td></tr>
<tr><th>Return to</th><td>{_escape(parts.get("return_to", ""))}</td></tr>
</table>

<h2>4. Immediate measures 需立即实施的措施</h2>
<p>{_escape(measures.get("immediate_measures", ""))}</p>

<h2>5. Further investigation 进一步分析</h2>
<p>{_escape(measures.get("further_investigation", ""))}</p>

<h2>6. Measures against further problem 问题预防措施</h2>
<p>{_escape(measures.get("measures_against_further_problem", ""))}</p>

<h2>7. Control of the efficiency of measures 措施有效性控制</h2>
<p>{_escape(measures.get("control_of_efficiency", ""))}</p>

<h2>8. Control of preventive measures 预防性措施结果控制</h2>
<p>{_escape(measures.get("control_of_preventive_measures", ""))}</p>

<h2>Signatures 签字</h2>
<table>
<tr><th>Checked by</th><td>{_escape(signatures.get("checked_by", ""))}</td></tr>
<tr><th>Section Manager</th><td>{_escape(signatures.get("section_manager", ""))}</td></tr>
<tr><th>Department Manager</th><td>{_escape(signatures.get("department_manager", ""))}</td></tr>
</table>

<p class="small">Generated at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

</body>
</html>
"""

    return html_text


def save_nozzle_report_html(report: Dict[str, Any], report_id: str) -> str:
    html_text = render_nozzle_report_html(report)

    safe_report_id = report_id.replace("/", "_").replace("\\", "_").replace(" ", "_")
    out_path = GENERATED_DIR / f"{safe_report_id}.html"

    out_path.write_text(html_text, encoding="utf-8")

    return str(out_path)