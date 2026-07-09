"""LLM 工厂：基于 .env 里的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 构造
LangChain ChatOpenAI（走 OpenAI 兼容端点，与现有 Azure 配置一致）。
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=8)
def get_chat_model(temperature: float = 0.0):
    """返回一个 LangChain ChatOpenAI 实例。

    延迟 import，避免未安装 langchain 时整个包无法导入。
    """
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-4.1")

    if not api_key:
        raise RuntimeError("缺少 LLM_API_KEY，请在 .env 中配置")

    kwargs: dict = {"model": model, "api_key": api_key, "temperature": temperature}
    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
