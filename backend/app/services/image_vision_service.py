import base64
import json
import os
from pathlib import Path
from typing import Any, Dict

import httpx


def _read_image_as_data_url(image_path: str) -> str:
    path = Path(image_path)
    suffix = path.suffix.lower()

    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }

    mime = mime_map.get(suffix, "image/png")

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime};base64,{b64}"


def _extract_json(text: str) -> Dict[str, Any]:
    """
    尽量从大模型输出中提取 JSON。
    防止模型输出 ```json。
    """
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


async def _call_llm_with_image(prompt: str, image_path: str) -> str:
    """
    支持 OpenAI-compatible / Azure OpenAI chat completions。
    使用 httpx.AsyncClient 避免阻塞事件循环。
    """

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

    image_data_url = _read_image_as_data_url(image_path)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional industrial component visual inspection assistant."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        },
                    },
                ],
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
        raise RuntimeError(f"视觉大模型调用失败：{res.status_code} {res.text}")

    data = res.json()

    return data["choices"][0]["message"]["content"]


async def analyze_nozzle_image(image_path: str, user_description: str = "") -> Dict[str, Any]:
    """
    图片分析入口。
    返回结构化 image_observation。
    """

    prompt = f"""
你是一个油嘴/喷油器零件外观检测助手。

请观察用户上传的图片，只做客观描述，不要直接下最终结论。

用户补充描述：
{user_description}

重点观察：
1. 是否存在 seat wear 座面磨损
2. 是否存在 guidance wear 导向段磨损
3. 是否存在 coating delamination 镀层剥落
4. 是否存在 deposit 积炭
5. 是否存在 cavitation 穴蚀
6. 是否存在 corrosion 腐蚀
7. 是否存在 mechanical damage 机械破损
8. 异常区域是否位于功能相关区域
9. 是否可能只是反光、油污、阴影、拍摄角度或加工纹理

判断要保守：
- 如果图片证据不足，不要强行判断为缺陷。
- 如果无法确认，need_manual_check = true。
- 不要编造测量值。

必须只输出 JSON，不要 Markdown。

输出格式：
{{
  "image_summary": "",
  "abnormal_area": "",
  "visible_abnormalities": [],
  "possible_defect_types": [],
  "possible_non_defect_explanations": [],
  "function_relevant_area": "",
  "image_quality": "",
  "need_manual_check": true,
  "confidence": 0.0
}}
"""

    text = await _call_llm_with_image(prompt=prompt, image_path=image_path)
    result = _extract_json(text)

    # 补齐字段，避免后面报错
    default_result = {
        "image_summary": "",
        "abnormal_area": "",
        "visible_abnormalities": [],
        "possible_defect_types": [],
        "possible_non_defect_explanations": [],
        "function_relevant_area": "",
        "image_quality": "",
        "need_manual_check": True,
        "confidence": 0.0,
    }

    default_result.update(result)
    return default_result