import json
import os
from pathlib import Path
from typing import Any, Dict

import httpx


BASE_DIR = Path(__file__).resolve().parents[1]
RAG_DIR = BASE_DIR / "rag"
TEMPLATE_PATH = RAG_DIR / "knowledge" / "report_templates" / "nozzle_investigation_template.json"


def _extract_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        return json.loads(text)
    except Exception:
        return {
            "raw_output": text,
            "parse_error": True,
        }


def get_default_nozzle_report_template() -> Dict[str, Any]:
    """
    默认模板。
    如果 knowledge/report_templates/nozzle_investigation_template.json 存在，
    就优先读取你的模板。
    """

    default_template = {
        "report_meta": {
            "report_title": "Nozzle investigation 油嘴检测报告",
            "report_no": "",
            "bm_no": "",
            "customer_no": "",
            "date": "",
            "department_from": "",
            "reference_person": "",
            "telephone": "",
            "fax": "",
            "to": [],
            "cc": []
        },
        "test_basic_info": {
            "customer": "",
            "project": "",
            "type_of_test": "",
            "conditions": "",
            "fuel": "",
            "runtime": "",
            "injector_no": "",
            "nozzle_type": "",
            "seat_geometry": "",
            "complaint": ""
        },
        "job_problem_explanation": {
            "description_en": "",
            "description_cn": ""
        },
        "responsible_departments": {
            "departments_en": [],
            "departments_cn": []
        },
        "image_analysis": {
            "uploaded_image_path": "",
            "image_summary": "",
            "abnormal_area": "",
            "visible_abnormalities": [],
            "possible_wear_features": [],
            "possible_non_wear_explanations": [],
            "image_quality": "",
            "need_manual_check": True
        },
        "investigation_results": {
            "result_summary_en": "",
            "result_summary_cn": "",
            "seat_wear": {
                "judgement": "",
                "severity": "",
                "description": ""
            },
            "guidance_wear": {
                "judgement": "",
                "severity": "",
                "description": ""
            },
            "coating_condition": {
                "judgement": "",
                "description": ""
            },
            "deposit": {
                "judgement": "",
                "description": ""
            },
            "cavitation": {
                "judgement": "",
                "description": ""
            },
            "corrosion": {
                "judgement": "",
                "description": ""
            },
            "mechanical_damage": {
                "judgement": "",
                "description": ""
            }
        },
        "measured_values": {
            "summary": "",
            "abnormal_values": [],
            "table": []
        },
        "conclusion": {
            "conclusion_en": "",
            "conclusion_cn": "",
            "function_influence": "",
            "risk_level": "",
            "confidence": 0.0
        },
        "parts": {
            "handling": "",
            "return_to": ""
        },
        "measures": {
            "immediate_measures": "",
            "further_investigation": "",
            "measures_against_further_problem": "",
            "control_of_efficiency": "",
            "control_of_preventive_measures": ""
        },
        "attachments": {
            "image_paths": [],
            "related_case_ids": []
        },
        "signatures": {
            "checked_by": "",
            "section_manager": "",
            "department_manager": ""
        }
    }

    if TEMPLATE_PATH.exists():
        try:
            return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return default_template

    return default_template


async def _call_llm(prompt: str) -> str:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    model = os.getenv("LLM_MODEL", "gpt-4o")

    if not api_key:
        raise RuntimeError("缺少 LLM_API_KEY，请在 .env 中配置")

    if not base_url:
        raise RuntimeError("缺少 LLM_BASE_URL，请在 .env 中配置")

    if "chat/completions" in base_url:
        url = base_url
    else:
        url = base_url.rstrip("/") + "/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional nozzle investigation report generation assistant."
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "api-key": api_key,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.post(url, headers=headers, json=payload)

    if res.status_code >= 400:
        raise RuntimeError(f"大模型生成报告失败：{res.status_code} {res.text}")

    data = res.json()
    return data["choices"][0]["message"]["content"]


async def generate_nozzle_report_json(
    user_input: Dict[str, Any],
    image_observation: Dict[str, Any],
    rag_context: str,
) -> Dict[str, Any]:
    “””
    生成 Nozzle investigation 测试报告 JSON。
    “””

    template = get_default_nozzle_report_template()

    prompt = f”””
你是一个 Nozzle investigation 油嘴检测报告生成助手。

请根据以下信息生成测试报告 JSON。

【用户输入信息】
{json.dumps(user_input, ensure_ascii=False, indent=2)}

【图片观察结果】
{json.dumps(image_observation, ensure_ascii=False, indent=2)}

【知识库检索内容】
{rag_context}

【报告模板】
{json.dumps(template, ensure_ascii=False, indent=2)}

报告结构要求：
1. 必须参考历史报告结构，包括：
   - Job-/Problem explanation 任务/问题描述
   - Responsible departments 责任部门
   - Investigation results 检测结果
   - Results 结果
   - Measured values 测量结果
   - Conclusion 结论
   - Parts 零件
   - Immediate measures 需立即实施的措施
   - Further investigation 进一步分析
   - Measures against further problem 问题预防措施
   - Control of the efficiency of measures 措施有效性控制

2. 检测项目应重点覆盖：
   - seat wear 座面磨损
   - guidance wear 导向段磨损
   - coating delamination 镀层剥落
   - deposit 积炭
   - cavitation 穴蚀
   - corrosion 腐蚀
   - mechanical damage 机械破损
   - needle guidance clearance 针阀导向间隙
   - leakage 导向泄漏

3. 判断原则：
   - 如果图片证据不足，不要直接判定失效，应写”疑似”或”需要进一步验证”。
   - 如果异常位于非功能相关区域，应说明可能对功能无影响。
   - 如果没有测量数据，不要编造数值，写”待测量”或”not measured”。
   - 结论必须保守。
   - 中英文尽量同时输出。
   - 用户输入的信息必须保留，不要随意改写。

4. 必须只输出合法 JSON。
5. 不要输出 Markdown。
6. 不要输出解释文字。
7. 字段结构必须尽量与模板一致。
“””

    text = await _call_llm(prompt)
    result = _extract_json(text)

    if not result:
        raise RuntimeError(“大模型没有返回有效 JSON”)

    return result