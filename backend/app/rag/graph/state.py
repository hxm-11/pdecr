"""LangGraph 全局状态定义。

一张 PD-ECR 单子从输入到各模块产出，全程共享这一个 state 字典。
每个 node 读需要的字段、写自己负责的字段。
"""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class PdEcrState(TypedDict, total=False):
    # ── 输入 ──
    request: Dict[str, Any]          # 变更请求原始字段（见 pdecr_schema）

    # ── 中间产物 ──
    change_type: str                 # classify 节点判定的变更类型
    retrieved: List[Dict[str, Any]]  # 检索到的历史案例（序列化后的 chunk）
    context: str                     # 拼好的检索上下文文本

    # ── 各模块产出 ──
    impact_analysis: Dict[str, Any]
    affected_documents: Dict[str, Any]
    validation_plan: Dict[str, Any]
    implementation_plan: Dict[str, Any]

    # ── 控制/诊断 ──
    retries: Dict[str, int]          # 每个模块的重试计数
    errors: List[str]
