"""探测 Azure OpenAI 端点是否开了 embedding 部署（一次性脚本，用后可删）。

做两件只读的事：
  1) 列出该端点可见的模型/部署（client.models.list）
  2) 尝试用几个常见 embedding 部署名做一次极小的 embedding 调用

不打印密钥。用法（backend/ 目录）：
    python probe_embedding.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL")

if not api_key or not base_url:
    raise SystemExit("缺少 LLM_API_KEY / LLM_BASE_URL")

print(f"Endpoint: {base_url}")
client = OpenAI(api_key=api_key, base_url=base_url)

# 1) 列出可见模型/部署
print("\n=== 1. 该端点可见的模型/部署 ===")
try:
    models = client.models.list()
    names = [m.id for m in models.data]
    for n in sorted(names):
        print("  -", n)
    embed_like = [n for n in names if "embed" in n.lower()]
    print(f"\n  含 'embed' 的部署：{embed_like or '（无）'}")
except Exception as exc:
    print(f"  models.list 失败：{exc}")

# 2) 逐个试常见 embedding 部署名
print("\n=== 2. 尝试 embedding 调用 ===")
candidates = [
    "text-embedding-3-small",
    "text-embedding-3-large",
    "text-embedding-ada-002",
    "text-embedding-3-small-1",
    "embedding",
]
for name in candidates:
    try:
        resp = client.embeddings.create(model=name, input="测试文本 hello")
        dim = len(resp.data[0].embedding)
        print(f"  [OK]   {name}  -> 维度 {dim}")
    except Exception as exc:
        msg = str(exc).splitlines()[0][:120]
        print(f"  [FAIL] {name}  -> {msg}")
