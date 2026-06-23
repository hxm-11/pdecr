"""
批量补全 parsed/json/*.json 的 modules 字段。

从对应的原始 MD 文件中按 Step 标题提取各模块真实内容，
同时补充 business_fields（签字人、负责部门等）。
"""
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PARSED_DIR = BASE_DIR / "parsed" / "json"


# ============================================================
# HTML 清洗 & 模块提取（与 pd_ecr.py 中 _extract_historical_module_contents 一致）
# ============================================================

_MODULE_SECTION_MAP: dict[str, list[str]] = {
    "change_request_description": [
        "Step 1", "Step 2", "Change request", "Change proposal",
        "Basic information", "变更请求", "更改理由", "变更描述",
    ],
    "impact_analysis": [
        "Step 3.1", "Impact analysis", "影响分析",
        "Step 3.3", "Affected documents", "影响文档",
    ],
    "validation_trial_run_plan": [
        "Step 3.2", "Quality Assurance", "验证计划",
        "Step 4", "Technical feasibility", "技术可行性", "Validation plan",
    ],
    "validation_trial_run_result": [
        "Step 5", "Documents release", "文档发布",
        "Trial run result", "Validation result", "验证结果",
    ],
    "implementation_task_plan": [
        "Step 6.1", "Implementation check list", "导入清单",
        "Implementation task plan",
    ],
    "implementation_task_result": [
        "Step 6.2", "Implementation date", "执行日期",
        "Step 7", "Implementation Approval", "Approval", "签字",
    ],
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_module_contents(source_text: str) -> dict[str, str]:
    """从原始 MD/HTML 中按 Step 标题切分，返回模块名 → 文本 的映射。"""
    clean = _strip_html(source_text)

    step_pattern = re.compile(
        r"(Step\s*\d+(?:\.\d+)?[:\s]*[^\n]{0,80})",
        re.IGNORECASE,
    )
    matches = list(step_pattern.finditer(clean))

    if not matches:
        return {"change_request_description": clean[:5000]}

    sections: dict[str, list[str]] = {key: [] for key in _MODULE_SECTION_MAP}

    for i, match in enumerate(matches):
        header = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(clean)
        body = clean[start:end].strip()

        header_lower = header.lower()
        matched = False
        for module_key, keywords in _MODULE_SECTION_MAP.items():
            if any(kw.lower() in header_lower for kw in keywords):
                sections[module_key].append(body)
                matched = True
                break

        if not matched:
            sections["change_request_description"].append(body)

    result: dict[str, str] = {}
    for module_key, parts in sections.items():
        merged = "\n\n".join(parts).strip()
        result[module_key] = merged[:6000] if merged else ""

    return result


# ============================================================
# 签字人 / 负责人提取
# ============================================================

def extract_person(text: str, keywords: list[str]) -> str:
    """从文本中提取关键词后的姓名。"""
    for kw in keywords:
        # 匹配 "Initiator/发起人： XXX" 或 "发起人: XXX"
        pat = rf"{re.escape(kw)}\s*[：:]\s*([^\n\r<|]+?)(?:\s*[|\)]|\s*$)"
        m = re.search(pat, text, re.I)
        if m:
            value = m.group(1).strip()
            # 去掉括号里的部门名，保留纯姓名
            value = re.sub(r"\s*\([^)]*\)", "", value).strip()
            if value and len(value) < 30 and value.lower() not in ("n/a", "na", "none", "-"):
                return value
    return ""


def extract_department(text: str) -> str:
    """从发起人字段中提取部门名（括号内的部门代号）。"""
    pat = r"Initiator\s*[／/]?\s*发起人\s*[：:]\s*(?:[^(]*)\s*\(([^)]+)\)"
    m = re.search(pat, text, re.I)
    if m:
        dept = m.group(1).strip()
        # 过滤噪音
        if dept and len(dept) < 30 and not dept.startswith("F03Z"):
            return dept
    return ""


def extract_approval_persons(text: str) -> list[str]:
    """从文本中提取签字人姓名列表。"""
    # 噪声词汇黑名单
    noise = {
        "pn no", "na", "step", "no", "yes", "due date", "resp",
        "导入清单", "执行日期", "执行结果", "变更计划", "变更描述",
        "研发", "采购", "工艺", "样品", "质量", "生产", "物流", "客户项目",
        "development", "purchasing", "quality", "manufacturing", "mfe",
        "cos", "cpjm", "moex", "log", "tef", "设计", "测试", "验证",
        "fmea", "检查", "评估", "确认", "分析", "说明", "备注",
        "更改理由", "影响分析", "验证计划", "加工", "装配",
        "油环", "轴套", "螺栓", "冷却器", "文档", "报告",
    }

    persons = []
    # 尝试从 Step 7 / Implementation Approval 区域提取
    approval_section = ""
    m = re.search(
        r"(?:Step\s*7|Implementation\s*Approval|Step\s*6)",
        text, re.I,
    )
    if m:
        start = m.start()
        approval_section = text[start:start + 4000]

    # 匹配英文姓名格式：FENG Ying, TANG Liang, HE Yonggang 等
    name_pattern = re.findall(
        r"\b([A-Z]{2,}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        approval_section or text,
    )
    seen = set()
    for name in name_pattern:
        name = name.strip()
        low = name.lower()
        if low not in noise and name not in seen:
            persons.append(name)
            seen.add(name)

    # 中文姓名（2-3字）
    cn_pattern = re.findall(
        r"(?<![a-zA-Z0-9])[一-鿿]{2,3}(?![a-zA-Z0-9])",
        approval_section or text,
    )
    for name in cn_pattern:
        if name not in seen and name not in noise:
            persons.append(name)
            seen.add(name)

    return persons[:20]


# ============================================================
# 主处理逻辑
# ============================================================

def find_md_file(case_id: str) -> Path | None:
    """根据 case_id 找到对应的 MD 文件（优先选最长的，避免匹配到片段）。"""
    candidates = []
    for path in BASE_DIR.glob("*.md"):
        if "_signature_structured" in path.stem:
            continue
        if path.stem.upper().startswith(case_id.upper()):
            candidates.append(path)

    if not candidates:
        return None

    # 优先选文件体积大的（更可能是完整 PD-ECR 而不是片段）
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def enrich_one_json(json_path: Path) -> bool:
    """补全单个 parsed JSON 文件。"""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return False

    case_id = data.get("case_id", "")
    if not case_id:
        case_id = json_path.stem.split("-")[0].split()[0]
        data["case_id"] = case_id

    print(f"\n📋 {case_id} ({json_path.name})")

    # 1. 找对应 MD
    md_path = find_md_file(case_id)
    if not md_path:
        print(f"  ⚠️  未找到对应 MD 文件")
        return False

    print(f"  📄 MD: {md_path.name}")
    source_text = md_path.read_text(encoding="utf-8", errors="ignore")

    # 2. 提取模块内容
    extracted = extract_module_contents(source_text)
    modules = data.get("modules", {})
    filled = 0
    for key in _MODULE_SECTION_MAP:
        content = extracted.get(key, "")
        old = modules.get(key, "")
        if content and (old in ("", "...", ".", None)):
            modules[key] = content
            filled += 1
            print(f"  ✅ {key}: {len(content)} 字符")
        elif content:
            print(f"  ⏭️  {key}: 已有内容 ({len(old)} 字符)，跳过")
        else:
            modules[key] = old if old and old != "..." else ""
            print(f"  ⚠️  {key}: 未提取到内容")

    data["modules"] = modules

    # 3. 更新 business_fields
    biz = data.get("business_fields", {}) or {}

    initiator = extract_person(source_text, ["Initiator", "发起人"])
    if initiator and not biz.get("responsible_person"):
        biz["responsible_person"] = initiator
        print(f"  👤 发起人: {initiator}")

    dept = extract_department(source_text)
    if dept and not biz.get("responsible_department"):
        biz["responsible_department"] = dept
        print(f"  🏢 部门: {dept}")

    if not biz.get("approval_persons"):
        persons = extract_approval_persons(source_text)
        if persons:
            biz["approval_persons"] = persons
            print(f"  ✍️  签字人: {', '.join(persons[:8])}")

    data["business_fields"] = biz

    # 4. 写回
    try:
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  💾 已保存 ({filled} 个模块补全)")
        return True
    except Exception as e:
        print(f"  ❌ 写入失败: {e}")
        return False


def main():
    json_files = sorted(PARSED_DIR.glob("*.json"))
    if not json_files:
        print("没有找到 parsed JSON 文件")
        return

    print(f"找到 {len(json_files)} 个 parsed JSON 文件")
    print(f"MD 文件目录: {BASE_DIR}")
    print(f"共 {len(list(BASE_DIR.glob('*.md')))} 个 MD 文件")

    success = 0
    for json_path in json_files:
        if enrich_one_json(json_path):
            success += 1

    print(f"\n{'='*50}")
    print(f"完成: {success}/{len(json_files)} 个 JSON 文件补全")


if __name__ == "__main__":
    main()
