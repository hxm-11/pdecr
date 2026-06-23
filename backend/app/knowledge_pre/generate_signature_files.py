"""
从 parsed JSON 和原始 MD 生成 _signature_structured.md 文件。

这些文件被后端 find_structured_signature_md() 使用，
用于提取签字人和审批周期数据。
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PARSED_DIR = BASE_DIR / "parsed" / "json"


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_structured_sections(source_text: str) -> str:
    """从 MD/HTML 中提取 ## structured_fields_* 区块。"""
    # 先检查是否已有嵌入的 structured_fields（来自之前的 enrich）
    structured_blocks = re.findall(
        r"##\s*structured_fields_\w+.*?(?=##\s*(?:structured_fields_|Sheet:|\Z))",
        source_text,
        re.S | re.I,
    )
    if structured_blocks:
        return "\n\n".join(b.strip() for b in structured_blocks)

    # 否则从原始 MD 构建
    clean = _strip_html(source_text)

    lines = [
        "# Structured Signature Fields",
        "",
    ]

    # 提取日期
    date_patterns = [
        r"Date\s*[／/]?\s*日期\s*[:：]\s*(\d{8}|\d{4}[.-]\d{1,2}[.-]\d{1,2})",
        r"\bdate\s*[:：]\s*(\d{4}-\d{2}-\d{2})",
    ]
    for pat in date_patterns:
        m = re.search(pat, clean, re.I)
        if m:
            lines.append(f"date: {m.group(1)}")
            break

    # 提取 DC No
    m = re.search(r"DC\s*No\.?\s*[／/]?\s*(?:开发更改编号)?\s*[:：]\s*([A-Za-z0-9_-]+)", clean, re.I)
    if m:
        lines.append(f"dc_no: {m.group(1)}")

    # 提取发起人
    m = re.search(r"Initiator\s*[／/]?\s*发起人\s*[:：]\s*([^|\n<]+)", clean, re.I)
    if m:
        lines.append(f"initiator: {m.group(1).strip()}")

    lines.append("")
    lines.append("## structured_fields_actual_approval")

    # 提取签字人
    approval_fields = [
        ("approval_development_person", ["Development", "研发"]),
        ("approval_purchasing_person", ["Purchasing", "采购"]),
        ("approval_mfe_person", ["MFE", "TEF", "工艺"]),
        ("approval_cos_person", ["COS", "样品"]),
        ("approval_quality_person", ["Quality", "质量"]),
        ("approval_cpjm_person", ["CPjM", "CPJM", "客户项目"]),
        ("approval_moex_person", ["MOEx", "MOEX", "生产"]),
        ("approval_log_person", ["LOG", "物流"]),
        ("approval_other_person", ["Other", "其他"]),
    ]

    # 尝试从 Step 7 表格提取签字人
    for field, keywords in approval_fields:
        found = ""
        for kw in keywords:
            # 匹配 "Development | FENG Ying" 或 "研发: FENG Ying"
            pat = rf"{re.escape(kw)}\s*[/|:：]?\s*([A-Z][a-zA-Z\s]+?)(?:\s*[/|]|\s*$|\n)"
            m = re.search(pat, clean, re.I)
            if m:
                candidate = m.group(1).strip()
                # 验证是否像人名
                if re.match(r"[A-Z][a-z]+\s+[A-Z][a-z]+", candidate) or \
                   re.match(r"[A-Z]{2,}\s+[A-Z][a-z]+", candidate) or \
                   re.match(r"[一-鿿]{2,3}", candidate):
                    found = candidate
                    break
        lines.append(f"{field}: {found}")

    # 提取 Step 3.3 受影响的文档
    lines.append("")
    lines.append("## structured_fields_step_3_3_affected_documents")
    doc_fields = [
        "interface_fmea_value",
        "product_fmea_value",
        "special_characteristics_value",
        "imds_value",
        "offer_drawing_value",
        "tcd_value",
        "norm_wb_hf_value",
        "affected_document_other_value",
    ]
    for field in doc_fields:
        # 从文本中查找 yes/no
        name_map = {
            "interface_fmea_value": ["interface fmea", "ifmea", "接口 fmea"],
            "product_fmea_value": ["product fmea", "dfmea", "产品 fmea"],
            "special_characteristics_value": ["special char", "psc", "特殊特性"],
            "imds_value": ["imds", "材料数据"],
            "offer_drawing_value": ["offer drawing", "报价图"],
            "tcd_value": ["tcd"],
            "norm_wb_hf_value": ["norm", "wb", "hf"],
            "affected_document_other_value": ["wi check", "其他"],
        }
        value = ""
        aliases = name_map.get(field, [field])
        for alias in aliases:
            m = re.search(
                rf"{re.escape(alias)}.*?(yes|no|是|否)",
                clean, re.I,
            )
            if m:
                v = m.group(1).lower()
                value = "yes" if v in ("yes", "是") else "no"
                break
        lines.append(f"{field}: {value}")

    return "\n".join(lines)


def generate_signature_files():
    created = 0
    for json_path in sorted(PARSED_DIR.glob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        case_id = data.get("case_id", "")
        if not case_id:
            continue

        # 查找对应的 MD 文件
        md_path = None
        for p in BASE_DIR.glob("*.md"):
            if "_signature_structured" in p.stem:
                continue
            if p.stem.upper().startswith(case_id.upper()):
                md_path = p
                break

        if not md_path:
            continue

        source_text = md_path.read_text(encoding="utf-8", errors="ignore")

        # 优先检查 source_text 中是否已有 structured_fields
        structured = extract_structured_sections(source_text)

        # 生成文件名
        stem = md_path.stem.split(" copy")[0]  # 去掉 " copy" 后缀
        sig_path = BASE_DIR / f"{stem}_signature_structured.md"

        sig_path.write_text(structured, encoding="utf-8")
        print(f"✅ {sig_path.name}")

        # 同时写一份不带 stem 后缀的（兼容 find_structured_signature_md 的匹配逻辑）
        short_stem = re.sub(r"[-_]\s*PD[-_]\s*ECR.*", "", stem)
        if short_stem != stem:
            alt_path = BASE_DIR / f"{short_stem}_signature_structured.md"
            # 只在不冲突时写
            if not alt_path.exists():
                alt_path.write_text(structured, encoding="utf-8")
                print(f"   also → {alt_path.name}")

        created += 1

    print(f"\n生成 {created} 个 _signature_structured.md 文件")


if __name__ == "__main__":
    generate_signature_files()
