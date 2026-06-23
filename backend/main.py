import os
import re
import json
from pathlib import Path
from typing import Dict, Any

import markdown
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader

from app.rag.retriever import retrieve_pd_ecr_context


# =========================================================
# 基础配置
# =========================================================

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR.parent / ".env"

load_dotenv(dotenv_path=ENV_PATH)
load_dotenv()

router = APIRouter()

TEMPLATES_DIR = BASE_DIR / "templates"
REPORTS_DIR = BASE_DIR / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# 输入模型
# =========================================================

class PdEcrInput(BaseModel):
    dc_no: str = ""
    date: str = ""
    customer_project: str = ""
    mcr_no: str = ""
    product_no: str = ""
    component_no: str = ""
    initiator: str = ""
    reason: str = ""
    current_design: str = ""
    change_proposal: str = ""
    remarks: str = ""


# =========================================================
# 工具函数
# =========================================================

def safe_filename(text: str) -> str:
    if not text:
        return "unknown"

    text = str(text).strip()
    text = re.sub(r'[\\/:*?"<>|\t\r\n]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text[:80]

    return text or "unknown"


def clean_json_text(content: str) -> str:
    if not content:
        return ""

    content = content.strip()

    if content.startswith("```json"):
        content = content.replace("```json", "", 1).strip()

    if content.startswith("```"):
        content = content.replace("```", "", 1).strip()

    if content.endswith("```"):
        content = content[:-3].strip()

    return content.strip()


def get_llm_client() -> OpenAI:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")

    if not api_key:
        raise RuntimeError("缺少 LLM_API_KEY，请在 .env 中配置")

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)

    return OpenAI(api_key=api_key)


# =========================================================
# 勾选框补齐
# =========================================================

def normalize_yes_no_value(value: Any) -> str:
    value = str(value or "").strip().lower()

    if value in ["yes", "y", "true", "1", "是", "有", "需要", "影响"]:
        return "yes"

    if value in ["no", "n", "false", "0", "否", "无", "不需要", "不影响"]:
        return "no"

    return "no"


def set_yes_no_boxes(result: Dict[str, Any], field: str) -> None:
    value_key = f"{field}_value"
    yes_key = f"{field}_yes_box"
    no_key = f"{field}_no_box"

    value = normalize_yes_no_value(result.get(value_key, ""))

    result[value_key] = value

    if value == "yes":
        result[yes_key] = "☑"
        result[no_key] = "☐"
    else:
        result[yes_key] = "☐"
        result[no_key] = "☑"


def set_required_box(result: Dict[str, Any], value_key: str, box_key: str) -> None:
    value = normalize_yes_no_value(result.get(value_key, ""))

    result[value_key] = value

    if value == "yes":
        result[box_key] = "☑"
    else:
        result[box_key] = "☐"


def clean_box_value(value: Any) -> str:
    value = str(value or "").strip()

    if value == "☑":
        return "☑"

    if value == "☐":
        return "☐"

    return "☐"


def apply_cost_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    increase = clean_box_value(result.get("cost_increase_box"))
    decrease = clean_box_value(result.get("cost_decrease_box"))
    no_change = clean_box_value(result.get("cost_no_change_box"))

    checked_count = [increase, decrease, no_change].count("☑")

    if checked_count != 1:
        result["cost_increase_box"] = "☐"
        result["cost_decrease_box"] = "☐"
        result["cost_no_change_box"] = "☑"
    else:
        result["cost_increase_box"] = increase
        result["cost_decrease_box"] = decrease
        result["cost_no_change_box"] = no_change

    return result


def apply_treatment_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    groups = [
        [
            "raw_materials_not_affect_box",
            "raw_materials_use_in_other_products_box",
            "raw_materials_scrap_box",
            "raw_materials_rework_box",
            "raw_materials_use_up_box",
        ],
        [
            "parts_subassemble_not_affect_box",
            "parts_subassemble_use_in_other_products_box",
            "parts_subassemble_scrap_box",
            "parts_subassemble_rework_box",
            "parts_subassemble_use_up_box",
        ],
        [
            "finished_goods_inhouse_not_affect_box",
            "finished_goods_inhouse_scrap_box",
            "finished_goods_inhouse_rework_box",
            "finished_goods_inhouse_use_up_box",
        ],
        [
            "finished_goods_rdc_not_affect_box",
            "finished_goods_rdc_scrap_box",
            "finished_goods_rdc_rework_box",
            "finished_goods_rdc_use_up_box",
        ],
        [
            "finished_goods_customer_not_affect_box",
            "finished_goods_customer_recall_box",
            "finished_goods_customer_rework_box",
        ],
    ]

    for group in groups:
        values = [clean_box_value(result.get(k)) for k in group]

        if values.count("☑") != 1:
            for i, key in enumerate(group):
                result[key] = "☑" if i == 0 else "☐"
        else:
            for key, value in zip(group, values):
                result[key] = value

    return result


def apply_document_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    document_fields = [
        "interface_fmea",
        "product_fmea",
        "special_characteristics",
        "imds",
        "offer_drawing",
        "tcd",
        "norm_wb_hf",
        "affected_document_other",
    ]

    for field in document_fields:
        yes_key = f"{field}_yes_box"
        no_key = f"{field}_no_box"

        yes_value = clean_box_value(result.get(yes_key))
        no_value = clean_box_value(result.get(no_key))

        if yes_value == "☑" and no_value == "☐":
            result[yes_key] = "☑"
            result[no_key] = "☐"
        elif yes_value == "☐" and no_value == "☑":
            result[yes_key] = "☐"
            result[no_key] = "☑"
        else:
            result[yes_key] = "☐"
            result[no_key] = "☑"

    return result


def apply_required_item_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    items = [
        ("trial_run_value", "trial_run_box"),
        ("capability_cmk_value", "capability_cmk_box"),
        ("capability_msa_value", "capability_msa_box"),
        ("mae_release_value", "mae_release_box"),
        ("cleanness_test_value", "cleanness_test_box"),
        ("qz_test_value", "qz_test_box"),
        ("pdl_200h_value", "pdl_200h_box"),
        ("bom_check_value", "bom_check_box"),
        ("test_report_value", "test_report_box"),
        ("pav_release_value", "pav_release_box"),
    ]

    for value_key, box_key in items:
        set_required_box(result, value_key, box_key)

    return result


def apply_yes_no_boxes(result: Dict[str, Any]) -> Dict[str, Any]:
    yes_no_fields = [
        "function_performance",
        "interface_appearance",
        "reliability_robustness",
        "other_components",
        "manufacturing_assembly_testing",
        "supplier_part",
        "system_hw_sw_calibration_mechanical",
        "mixed_deliveries",
    ]

    for field in yes_no_fields:
        set_yes_no_boxes(result, field)

    result = apply_required_item_boxes(result)
    result = apply_cost_boxes(result)
    result = apply_treatment_boxes(result)
    result = apply_document_boxes(result)

    return result


# =========================================================
# 基本信息 RAG 补全
# =========================================================

BASIC_INFO_FIELDS = [
    "dc_no",
    "date",
    "customer_project",
    "mcr_no",
    "product_no",
    "component_no",
    "initiator",
]


def normalize_basic_info_from_rag(
    user_input: Dict[str, Any],
    llm_result: Dict[str, Any],
    rag_context: str,
) -> Dict[str, Any]:
    """
    如果用户没有填写基本信息字段，优先用 LLM 从 RAG 推理的结果，其次直接从 RAG 文本中提取。

    优先级：
    1. 用户已填写的值 — 保持不变
    2. LLM 从 RAG 上下文推理出的值
    3. 直接从 RAG 文本中正则提取的值
    """
    if not isinstance(llm_result, dict):
        return user_input

    result = dict(user_input)

    basic_info_from_llm = llm_result.get("basic_info", {})
    if not isinstance(basic_info_from_llm, dict):
        basic_info_from_llm = {}

    # 从 RAG 文本中直接提取的模式
    rag_patterns = {
        "dc_no": [
            r"DC\s*(?:No[.：:]?|Number[.：:]?|#?)\s*([A-Z0-9_-]{4,})",
            r"(?:dc_no|dc number)[.：:]\s*([A-Z0-9_-]+)",
        ],
        "customer_project": [
            r"(?:Customer|Project|客户|项目)[.：:]\s*([^\n\r|]{2,60})",
            r"(?:customer_project|customer project)[.：:]\s*([^\n\r]+)",
        ],
        "mcr_no": [
            r"MCR\s*(?:No[.：:]?|Number[.：:]?|#?)\s*([A-Z0-9_-]{4,})",
            r"(?:mcr_no|mcr number)[.：:]\s*([A-Z0-9_-]+)",
        ],
        "product_no": [
            r"(?:Product|产品)\s*(?:No[.：:]?|Number[.：:]?|#?)\s*([A-Z0-9._-]{4,})",
            r"(?:product_no|product number)[.：:]\s*([A-Z0-9._-]+)",
        ],
        "component_no": [
            r"(?:Component|零件|部件)\s*(?:No[.：:]?|Number[.：:]?|#?)\s*([A-Z0-9._-]{4,})",
            r"(?:component_no|component number)[.：:]\s*([A-Z0-9._-]+)",
        ],
        "initiator": [
            r"(?:Initiator|发起人|申请人|Editor|编辑)[.：:]\s*([^\n\r|]{2,40})",
            r"(?:initiator|editor)[.：:]\s*([^\n\r]+)",
        ],
    }

    for field in BASIC_INFO_FIELDS:
        user_value = str(user_input.get(field, "")).strip()

        # 1. 用户已填写 — 保持不动
        if user_value:
            continue

        # 2. 尝试 LLM 推理的结果
        llm_value = str(basic_info_from_llm.get(field, "")).strip()
        llm_value = llm_value.replace("未提供", "").replace("无法判断", "").replace("AI", "").strip()
        if llm_value and llm_value != user_value:
            result[field] = llm_value
            continue

        # 3. 直接从 RAG 文本正则提取
        if rag_context:
            for pattern in rag_patterns.get(field, []):
                m = re.search(pattern, rag_context, re.IGNORECASE)
                if m:
                    extracted = m.group(1).strip()
                    # 过滤掉明显不是实际值的占位文本
                    if extracted and len(extracted) >= 2 and "暂无" not in extracted:
                        result[field] = extracted
                        break

    return result


def normalize_change_request_from_rag(
    user_input: Dict[str, Any],
    llm_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    同理处理 change_request 字段的补全。
    """
    if not isinstance(llm_result, dict):
        return user_input

    result = dict(user_input)
    change_from_llm = llm_result.get("change_request", {})
    if not isinstance(change_from_llm, dict):
        change_from_llm = {}

    for field in ["reason", "current_design", "change_proposal", "remarks"]:
        user_value = str(user_input.get(field, "")).strip()
        if user_value:
            continue

        llm_value = str(change_from_llm.get(field, "")).strip()
        llm_value = llm_value.replace("未提供", "").replace("无法判断", "").replace("AI", "").strip()
        if llm_value:
            result[field] = llm_value

    return result


# =========================================================
# Prompt
# =========================================================

def build_prompt(data: Dict[str, Any], rag_context: str = "") -> str:
    return f"""
你是一个专业的 PD-ECR 工程变更报告分析助手。

请根据用户输入的信息，生成一份结构化的 PD-ECR 工程变更报告 JSON。

【总要求】
1. 必须只输出一个完整 JSON 对象。
2. 不要输出 Markdown。
3. 不要输出 ```json。
4. 不要输出解释文字。
5. 不要把 JSON 放进字符串里。
6. 不要转义双引号。
7. 用户已经填写的字段必须保留，不要随意改写。
8. 用户没有填写的分析类内容，请根据 PD-ECR 工程变更报告的常见逻辑合理补全。
9. 不要输出"未提供""无法判断""AI"。
10. 如果无法确定具体人名，可以填写责任部门，例如 Development、MFE、Quality、Purchasing、LOG、COS、MOEx。
11. 日期格式统一使用 YYYY-MM-DD；无法确定日期时输出空字符串 ""。
12. 输出内容要适合后续填充 HTML / Word / PDF 模板。

【基本信息补全规则 — 重要】
1. basic_info 中的字段如果用户已填写（非空字符串），必须原样保留，不得修改。
2. 如果用户没有填写（空字符串），请根据历史知识库检索内容进行推断补全：
   - 从历史案例中查找是否有该产品或组件关联的项目名、客户名、产品号等信息
   - 如果 RAG 上下文中有相似的 DC No.、MCR No.、Product No.、Component No.、Customer/Project、Initiator，可以合理推断填入
   - 不要直接复制历史案例中的具体 DC No. 和日期（这两个字段如果用户没填就保持空）
   - customer_project、product_no、component_no 可以从历史案例中推断相似值
   - initiator 可以从历史案例的责任人/确认人中推断
3. 如果历史案例中也没有相关信息，则保持空字符串 ""。
4. change_request 中的字段同理：用户已填的原样保留，未填的从历史案例推断。

【勾选框规则】
1. yes/no 判断字段必须同步输出对应勾选框字段。
2. 如果 value = "yes"，则 yes_box = "☑"，no_box = "☐"。
3. 如果 value = "no"，则 yes_box = "☐"，no_box = "☑"。
4. 所有 box 字段只能输出 "☑" 或 "☐"，不能输出 "☑/☐"。
5. 三选一字段只能有一个为 "☑"，其他必须为 "☐"。
6. Required 类检查项需要执行时，box = "☑"；不需要执行时，box = "☐"。
7. Y/N 字段只能输出 "Y" 或 "N"。

【工程判断规则】
1. 如果涉及功能、结构、材料、尺寸、性能、客户要求，则 Function & Performance 通常为 yes。
2. 如果涉及外观、接口、安装边界、连接方式，则 Interface and Appearance 通常为 yes。
3. 如果涉及耐久、寿命、稳定性、鲁棒性、质量风险，则 Reliability and robustness 通常为 yes。
4. 如果涉及关联零件、同步变更、系统匹配，则 Other components 通常为 yes。
5. 如果涉及加工、装配、测试、工装、设备、产线、工艺文件，则 Manufacturing / assembly / testing 通常为 yes。
6. 如果涉及采购件、供应商零件、外协件、来料检验，则 Supplier part 通常为 yes。
7. 如果涉及 System / HW / SW / Calibration / Mechanical alignment，则对应影响项通常为 yes。
8. 如果涉及图纸、BOM、FMEA、TCD、Offer drawing、Norm、WB、HF、IMDS，应在 affected documents 和 implementation checklist 中体现。
9. 如果涉及 SW version update、reflashing、barcode traceability、label/type error、calibration alignment，应补充 SW affected action。
10. 如果涉及库存、发货、切换、旧件处理、第一批交付，应补充 Stock / Delivery Treatment 和 COS / LOG 相关导入项。
11. 如果涉及质量验证、可靠性测试、测试报告、Trial run、CMK、MSA、MAE release，应补充 Quality Assurance Items。

【历史知识库检索内容】
{rag_context if rag_context else "暂无历史案例。"}

【用户输入信息】
{json.dumps(data, ensure_ascii=False, indent=2)}

请严格输出如下 JSON 结构，字段名必须完整保留：

{{
  "basic_info": {{
    "dc_no": "{data.get("dc_no", "")}",
    "date": "{data.get("date", "")}",
    "customer_project": "{data.get("customer_project", "")}",
    "mcr_no": "{data.get("mcr_no", "")}",
    "product_no": "{data.get("product_no", "")}",
    "component_no": "{data.get("component_no", "")}",
    "initiator": "{data.get("initiator", "")}"
  }},
  "change_request": {{
    "reason": "{data.get("reason", "")}",
    "current_design": "{data.get("current_design", "")}",
    "change_proposal": "{data.get("change_proposal", "")}",
    "remarks": "{data.get("remarks", "")}"
  }},

  "engineering_analysis": "",
  "impact_analysis": "",
  "impact_description": "",
  "risk_analysis": "",
  "verification_plan": "",
  "implementation_plan": "",
  "affected_documents": "",
  "suggested_approvers": [],

  "function_performance_value": "yes",
  "function_performance_no_box": "☐",
  "function_performance_yes_box": "☑",
  "function_performance_confirmed_by": "Development",

  "interface_appearance_value": "no",
  "interface_appearance_no_box": "☑",
  "interface_appearance_yes_box": "☐",
  "interface_appearance_confirmed_by": "Development",

  "reliability_robustness_value": "yes",
  "reliability_robustness_no_box": "☐",
  "reliability_robustness_yes_box": "☑",
  "reliability_robustness_confirmed_by": "Quality",

  "other_components_value": "no",
  "other_components_no_box": "☑",
  "other_components_yes_box": "☐",
  "other_components_confirmed_by": "Development",
  "parallel_components_description": "",

  "manufacturing_assembly_testing_value": "yes",
  "manufacturing_assembly_testing_no_box": "☐",
  "manufacturing_assembly_testing_yes_box": "☑",
  "manufacturing_assembly_testing_confirmed_by": "MFE / Manufacturing",

  "supplier_part_value": "no",
  "supplier_part_no_box": "☑",
  "supplier_part_yes_box": "☐",
  "supplier_part_confirmed_by": "Purchasing / Quality",

  "system_hw_sw_calibration_mechanical_value": "no",
  "system_hw_sw_calibration_mechanical_no_box": "☑",
  "system_hw_sw_calibration_mechanical_yes_box": "☐",
  "system_hw_sw_calibration_mechanical_confirmed_by": "Development",
  "system_hw_sw_calibration_mechanical_description": "",

  "cost_increase_box": "☐",
  "cost_decrease_box": "☐",
  "cost_no_change_box": "☑",
  "cost_impact_description": "",

  "mixed_deliveries_value": "no",
  "mixed_deliveries_yes_box": "☐",
  "mixed_deliveries_no_box": "☑",
  "stock_delivery_treatment_answer": "",
  "stock_delivery_treatment_confirmed_by": "LOG / COS",

  "raw_materials_not_affect_box": "☑",
  "raw_materials_use_in_other_products_box": "☐",
  "raw_materials_scrap_box": "☐",
  "raw_materials_rework_box": "☐",
  "raw_materials_use_up_box": "☐",
  "raw_materials_treatment_remark": "",

  "parts_subassemble_not_affect_box": "☑",
  "parts_subassemble_use_in_other_products_box": "☐",
  "parts_subassemble_scrap_box": "☐",
  "parts_subassemble_rework_box": "☐",
  "parts_subassemble_use_up_box": "☐",
  "parts_subassemble_treatment_remark": "",

  "finished_goods_inhouse_not_affect_box": "☑",
  "finished_goods_inhouse_scrap_box": "☐",
  "finished_goods_inhouse_rework_box": "☐",
  "finished_goods_inhouse_use_up_box": "☐",
  "finished_goods_inhouse_treatment_remark": "",

  "finished_goods_rdc_not_affect_box": "☑",
  "finished_goods_rdc_scrap_box": "☐",
  "finished_goods_rdc_rework_box": "☐",
  "finished_goods_rdc_use_up_box": "☐",
  "finished_goods_rdc_treatment_remark": "",

  "finished_goods_customer_not_affect_box": "☑",
  "finished_goods_customer_recall_box": "☐",
  "finished_goods_customer_rework_box": "☐",
  "finished_goods_customer_treatment_remark": "",

  "trial_run_value": "yes",
  "trial_run_box": "☑",
  "trial_run_plan_finish_date": "",
  "trial_run_resp_person": "MFE / Manufacturing",
  "trial_run_comments": "",

  "capability_cmk_value": "no",
  "capability_cmk_box": "☐",
  "capability_cmk_plan_finish_date": "",
  "capability_cmk_resp_person": "Quality",
  "capability_cmk_comments": "",

  "capability_msa_value": "no",
  "capability_msa_box": "☐",
  "capability_msa_plan_finish_date": "",
  "capability_msa_resp_person": "Quality",
  "capability_msa_comments": "",

  "mae_release_value": "no",
  "mae_release_box": "☐",
  "mae_release_plan_finish_date": "",
  "mae_release_resp_person": "MFE",
  "mae_release_comments": "",

  "cleanness_test_value": "no",
  "cleanness_test_box": "☐",
  "cleanness_test_plan_finish_date": "",
  "cleanness_test_resp_person": "Quality",
  "cleanness_test_comments": "",

  "qz_test_value": "no",
  "qz_test_box": "☐",
  "qz_test_plan_finish_date": "",
  "qz_test_resp_person": "Quality",
  "qz_test_comments": "",

  "pdl_200h_value": "no",
  "pdl_200h_box": "☐",
  "pdl_200h_plan_finish_date": "",
  "pdl_200h_resp_person": "Quality / Development",
  "pdl_200h_comments": "",

  "bom_check_value": "yes",
  "bom_check_box": "☑",
  "bom_check_plan_finish_date": "",
  "bom_check_resp_person": "Development",
  "bom_check_comments": "",

  "test_report_value": "yes",
  "test_report_box": "☑",
  "test_report_plan_finish_date": "",
  "test_report_resp_person": "Quality / Development",
  "test_report_comments": "",

  "pav_release_value": "no",
  "pav_release_box": "☐",
  "pav_release_plan_finish_date": "",
  "pav_release_resp_person": "Quality",
  "pav_release_comments": "",

  "interface_fmea_no_box": "☑",
  "interface_fmea_yes_box": "☐",
  "interface_fmea_resp_person": "Development",
  "interface_fmea_due_date": "",

  "product_fmea_no_box": "☐",
  "product_fmea_yes_box": "☑",
  "product_fmea_resp_person": "Development",
  "product_fmea_due_date": "",

  "special_characteristics_no_box": "☑",
  "special_characteristics_yes_box": "☐",
  "special_characteristics_resp_person": "Quality",
  "special_characteristics_due_date": "",

  "imds_no_box": "☑",
  "imds_yes_box": "☐",
  "imds_resp_person": "Development / Purchasing",
  "imds_due_date": "",

  "offer_drawing_no_box": "☐",
  "offer_drawing_yes_box": "☑",
  "offer_drawing_resp_person": "Development",
  "offer_drawing_due_date": "",

  "tcd_no_box": "☐",
  "tcd_yes_box": "☑",
  "tcd_resp_person": "Development",
  "tcd_due_date": "",

  "norm_wb_hf_no_box": "☑",
  "norm_wb_hf_yes_box": "☐",
  "norm_wb_hf_resp_person": "Development",
  "norm_wb_hf_due_date": "",

  "affected_document_other_no_box": "☑",
  "affected_document_other_yes_box": "☐",
  "affected_document_other_resp_person": "",
  "affected_document_other_due_date": "",
  "affected_document_other_description": "",

  "development_confirmation": "Development",

  "dev_bom_yn": "Y",
  "dev_bom_responsible": "Development",
  "dev_bom_due_date": "",
  "dev_doc_update_yn": "Y",
  "dev_doc_update_responsible": "Development",
  "dev_doc_update_due_date": "",
  "dev_offer_drawing_tcd_dfmea_yn": "Y",
  "dev_offer_drawing_tcd_dfmea_responsible": "Development",
  "dev_offer_drawing_tcd_dfmea_due_date": "",
  "dev_norm_wb_hf_yn": "N",
  "dev_norm_wb_hf_responsible": "",
  "dev_norm_wb_hf_due_date": "",
  "dev_moc_imds_yn": "N",
  "dev_moc_imds_responsible": "",
  "dev_moc_imds_due_date": "",

  "mfg_equipment_ready_yn": "Y",
  "mfg_equipment_ready_responsible": "MFE / Manufacturing",
  "mfg_equipment_ready_due_date": "",
  "mfg_program_ready_yn": "Y",
  "mfg_program_ready_responsible": "Manufacturing",
  "mfg_program_ready_due_date": "",
  "mfg_tooling_fixture_ready_yn": "Y",
  "mfg_tooling_fixture_ready_responsible": "MFE",
  "mfg_tooling_fixture_ready_due_date": "",
  "mfg_old_tooling_disposal_yn": "N",
  "mfg_old_tooling_disposal_responsible": "",
  "mfg_old_tooling_disposal_due_date": "",
  "mfg_old_materials_disposal_yn": "N",
  "mfg_old_materials_disposal_responsible": "",
  "mfg_old_materials_disposal_due_date": "",
  "mfg_planning_sheet_update_yn": "Y",
  "mfg_planning_sheet_update_responsible": "Manufacturing / Planner",
  "mfg_planning_sheet_update_due_date": "",
  "mfg_fmea_update_yn": "Y",
  "mfg_fmea_update_responsible": "MFE / Quality",
  "mfg_fmea_update_due_date": "",
  "mfg_cpfc_update_yn": "Y",
  "mfg_cpfc_update_responsible": "MFE / Quality",
  "mfg_cpfc_update_due_date": "",
  "mfg_wi_pds_update_yn": "Y",
  "mfg_wi_pds_update_responsible": "MFE / Manufacturing",
  "mfg_wi_pds_update_due_date": "",
  "mfg_first_batch_mark_inside_package_yn": "N",
  "mfg_first_batch_mark_inside_package_responsible": "",
  "mfg_first_batch_mark_inside_package_due_date": "",
  "mfg_first_batch_mark_outside_package_yn": "N",
  "mfg_first_batch_mark_outside_package_responsible": "",
  "mfg_first_batch_mark_outside_package_due_date": "",
  "mfg_training_yn": "Y",
  "mfg_training_responsible": "Manufacturing / MFE",
  "mfg_training_due_date": "",

  "cos_storage_old_parts_new_rm_intro_yn": "Y",
  "cos_storage_old_parts_new_rm_intro_responsible": "COS / LOG",
  "cos_storage_old_parts_new_rm_intro_due_date": "",
  "cos_delivery_old_parts_first_new_fg_yn": "Y",
  "cos_delivery_old_parts_first_new_fg_responsible": "COS / LOG",
  "cos_delivery_old_parts_first_new_fg_due_date": "",
  "cos_ckd_material_order_sample_orders_yn": "N",
  "cos_ckd_material_order_sample_orders_responsible": "",
  "cos_ckd_material_order_sample_orders_due_date": "",
  "cos_production_scheduling_alignment_yn": "Y",
  "cos_production_scheduling_alignment_responsible": "COS / MOEx / MFE",
  "cos_production_scheduling_alignment_due_date": "",
  "cos_old_stock_inventory_handling_yn": "Y",
  "cos_old_stock_inventory_handling_responsible": "COS / LOG",
  "cos_old_stock_inventory_handling_due_date": "",
  "cos_first_delivery_to_pmo_yn": "Y",
  "cos_first_delivery_to_pmo_responsible": "COS",
  "cos_first_delivery_to_pmo_due_date": "",
  "cos_ckd_purchasing_parts_sample_orders_yn": "N",
  "cos_ckd_purchasing_parts_sample_orders_responsible": "",
  "cos_ckd_purchasing_parts_sample_orders_due_date": "",

  "purchasing_internal_departments_requirements_yn": "N",
  "purchasing_internal_departments_requirements_responsible": "Purchasing",
  "purchasing_internal_departments_requirements_due_date": "",

  "quality_incoming_inspection_plan_update_yn": "Y",
  "quality_incoming_inspection_plan_update_responsible": "Quality",
  "quality_incoming_inspection_plan_update_due_date": "",
  "quality_testing_program_update_yn": "Y",
  "quality_testing_program_update_responsible": "Quality / Manufacturing",
  "quality_testing_program_update_due_date": "",
  "quality_ckd_inspection_plan_update_yn": "N",
  "quality_ckd_inspection_plan_update_responsible": "Quality",
  "quality_ckd_inspection_plan_update_due_date": "",

  "cpjm_offer_drawing_tcd_customer_yn": "N",
  "cpjm_offer_drawing_tcd_customer_responsible": "CPjM",
  "cpjm_offer_drawing_tcd_customer_due_date": "",
  "lop_10_digit_material_order_check_yn": "N",
  "lop_10_digit_material_order_check_responsible": "LOP",
  "lop_10_digit_material_order_check_due_date": "",
  "pmo_customer_order_sample_orders_yn": "N",
  "pmo_customer_order_sample_orders_responsible": "PMO",
  "pmo_customer_order_sample_orders_due_date": "",
  "pmo_customer_first_delivery_information_yn": "N",
  "pmo_customer_first_delivery_information_responsible": "PMO",
  "pmo_customer_first_delivery_information_due_date": "",

  "other_hw_sw_actions_1_yn": "N",
  "other_hw_sw_actions_1_description": "",
  "other_hw_sw_actions_1_responsible": "",
  "other_hw_sw_actions_1_due_date": "",
  "other_hw_sw_actions_2_yn": "N",
  "other_hw_sw_actions_2_description": "",
  "other_hw_sw_actions_2_responsible": "",
  "other_hw_sw_actions_2_due_date": "",

  "planned_implementation_date": "",

  "approval_development": "Required",
  "approval_purchasing": "",
  "approval_mfe": "Required",
  "approval_quality": "Required",
  "approval_cpjm": "",
  "approval_cos": "",
  "approval_moex": "",
  "approval_log": "",
  "approval_others": "",
  "approval_other": "",
  "approval_note": "",

  "revision_1_nr": "1",
  "revision_1_change_content": "",
  "revision_1_version": "V1.0",
  "revision_1_date": "{data.get("date", "")}",
  "revision_1_editor": "{data.get("initiator", "")}",
  "revision_2_nr": "2",
  "revision_2_change_content": "",
  "revision_2_version": "",
  "revision_2_date": "",
  "revision_2_editor": "",
  "revision_description": "",

  "affected_action_me_check_point": "",
  "affected_action_me_specific_analysis_points": "",
  "affected_action_me_discussion_result": "",
  "affected_action_hw_check_point": "",
  "affected_action_hw_specific_analysis_points": "",
  "affected_action_hw_discussion_result": "",
  "affected_action_sw_impact_check_point": "",
  "affected_action_sw_impact_specific_analysis_points": "",
  "affected_action_sw_impact_discussion_result": "",
  "affected_action_sw_implementation_check_point": "",
  "affected_action_sw_implementation_specific_analysis_points": "",
  "affected_action_sw_implementation_discussion_result": "",
  "affected_action_sw_label_traceability_check_point": "",
  "affected_action_sw_label_traceability_specific_analysis_points": "",
  "affected_action_sw_label_traceability_discussion_result": "",
  "affected_action_summary": ""
}}

只输出 JSON，不要输出其他任何内容。
"""


# =========================================================
# LLM 调用
# =========================================================

def call_llm(data: Dict[str, Any], rag_context: str = "") -> Dict[str, Any]:
    client = get_llm_client()
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是一个严谨的工程变更报告生成助手，只输出合法 JSON。",
            },
            {
                "role": "user",
                "content": build_prompt(data, rag_context),
            },
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content

    if not content:
        raise HTTPException(status_code=500, detail="大模型返回内容为空")

    content = clean_json_text(content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "大模型返回的不是合法 JSON",
                "raw_output": content,
            },
        )


# =========================================================
# Markdown 转 HTML
# =========================================================

def render_markdown_to_html_page(markdown_content: str, title: str) -> str:
    body_html = markdown.markdown(
        markdown_content,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{
      font-family: "Microsoft YaHei", Arial, sans-serif;
      background: #f3f5f7;
      margin: 0;
      padding: 0;
      color: #111827;
    }}

    .topbar {{
      background: #ffffff;
      border-bottom: 1px solid #ddd;
      padding: 18px 42px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 10;
    }}

    .bosch {{
      color: #d40000;
      font-weight: bold;
      font-size: 26px;
      letter-spacing: 1px;
    }}

    .title {{
      font-size: 22px;
      font-weight: bold;
      margin-top: 4px;
    }}

    .actions button {{
      margin-left: 10px;
      padding: 8px 18px;
      cursor: pointer;
      border: 1px solid #bbb;
      background: white;
      border-radius: 4px;
    }}

    .actions button:hover {{
      background: #f2f2f2;
    }}

    .report {{
      width: 92%;
      max-width: 1280px;
      margin: 32px auto;
      background: #ffffff;
      padding: 42px 56px;
      border: 1px solid #ddd;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }}

    h1 {{
      font-size: 28px;
      border-bottom: 3px solid #d40000;
      padding-bottom: 10px;
      margin-top: 10px;
      color: #111;
    }}

    h2 {{
      font-size: 22px;
      margin-top: 32px;
      padding-left: 12px;
      border-left: 5px solid #d40000;
      color: #222;
    }}

    h3 {{
      font-size: 18px;
      margin-top: 24px;
      color: #333;
    }}

    p {{
      font-size: 15px;
      line-height: 1.8;
      margin: 10px 0;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0 26px 0;
      font-size: 14px;
      background: white;
    }}

    th {{
      background: #eef2f7;
      font-weight: bold;
      text-align: left;
    }}

    th, td {{
      border: 1px solid #b8b8b8;
      padding: 9px 10px;
      vertical-align: top;
      line-height: 1.6;
    }}

    tr:nth-child(even) td {{
      background: #fafafa;
    }}

    code {{
      background: transparent;
      padding: 0;
      font-family: "Microsoft YaHei", Arial, sans-serif;
    }}

    pre {{
      background: #f7f7f7;
      border: 1px solid #ddd;
      padding: 14px;
      overflow-x: auto;
      border-radius: 4px;
    }}

    hr {{
      border: none;
      border-top: 1px solid #ddd;
      margin: 34px 0;
    }}

    ul {{
      line-height: 1.8;
    }}

    @media print {{
      .topbar {{
        display: none;
      }}

      body {{
        background: white;
      }}

      .report {{
        width: 100%;
        max-width: none;
        margin: 0;
        padding: 20px;
        border: none;
        box-shadow: none;
      }}
    }}
  </style>
</head>

<body>
  <div class="topbar">
    <div>
      <div class="bosch">BOSCH</div>
      <div class="title">{title}</div>
    </div>
    <div class="actions">
      <button onclick="window.print()">打印 / 保存 PDF</button>
      <button onclick="window.history.back()">返回</button>
    </div>
  </div>

  <div class="report">
    {body_html}
  </div>
</body>
</html>
"""


# =========================================================
# 路由接口
# =========================================================

@router.post("/generate-report")
def generate_report(data: PdEcrInput):
    user_input = data.model_dump()
    print("后端收到的数据：", user_input)

    # =========================
    # 1. RAG 知识库检索
    # =========================
    rag_context = ""
    try:
        rag_context = retrieve_pd_ecr_context(user_input, top_k=10)
        print("========== RAG 检索内容 START ==========")
        print(rag_context[:3000])
        print("========== RAG 检索内容 END ==========")
    except Exception as e:
        print(f"RAG 检索失败，将不使用历史知识库：{e}")
        rag_context = ""

    try:
        llm_result = call_llm(user_input, rag_context)

        # =========================
        # 2. 基本信息与变更说明 RAG 补全
        # =========================
        enriched_input = normalize_basic_info_from_rag(user_input, llm_result, rag_context)
        enriched_input = normalize_change_request_from_rag(enriched_input, llm_result)

        llm_result = apply_yes_no_boxes(llm_result)

        print("补齐勾选框后的大模型结果：")
        print(json.dumps(llm_result, ensure_ascii=False, indent=2))

        print("RAG 补全后的基本信息：")
        print(json.dumps({
            k: enriched_input.get(k, "") for k in BASIC_INFO_FIELDS
        }, ensure_ascii=False, indent=2))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"调用大模型失败：{str(e)}",
        )

    # =========================
    # 3. 组装模板上下文（优先使用 enriched_input，确保用户填写值不丢失）
    # =========================
    basic_info_from_llm = llm_result.get("basic_info", {})
    if not isinstance(basic_info_from_llm, dict):
        basic_info_from_llm = {}

    change_request_from_llm = llm_result.get("change_request", {})
    if not isinstance(change_request_from_llm, dict):
        change_request_from_llm = {}

    context = {
        **llm_result,
        **enriched_input,

        "basic_info": {
            "dc_no": enriched_input.get("dc_no", ""),
            "date": enriched_input.get("date", ""),
            "customer_project": enriched_input.get("customer_project", ""),
            "mcr_no": enriched_input.get("mcr_no", ""),
            "product_no": enriched_input.get("product_no", ""),
            "component_no": enriched_input.get("component_no", ""),
            "initiator": enriched_input.get("initiator", ""),
        },
        "change_request": {
            "reason": enriched_input.get("reason", ""),
            "current_design": enriched_input.get("current_design", ""),
            "change_proposal": enriched_input.get("change_proposal", ""),
            "remarks": enriched_input.get("remarks", ""),
        },

        "engineering_analysis": llm_result.get("engineering_analysis", ""),
        "impact_analysis": llm_result.get("impact_analysis", ""),
        "impact_description": llm_result.get("impact_description", ""),
        "risk_analysis": llm_result.get("risk_analysis", ""),
        "verification_plan": llm_result.get("verification_plan", ""),
        "implementation_plan": llm_result.get("implementation_plan", ""),
        "affected_documents": llm_result.get("affected_documents", ""),
        "suggested_approvers": llm_result.get("suggested_approvers", []),
    }

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )

    template_files = [
        "Revision history.md",
        "impact.md",
        "implementation.md",
        "Example of affected actions.md",
    ]

    report_parts = []

    for template_file in template_files:
        try:
            template = env.get_template(template_file)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"模板文件读取失败：{template_file}，错误：{str(e)}",
            )

        report_parts.append(template.render(context))

    report_markdown = "\n\n---\n\n".join(report_parts)

    dc_no = safe_filename(user_input.get("dc_no", ""))
    filename = f"report_{dc_no}.html"
    report_path = REPORTS_DIR / filename

    html_content = render_markdown_to_html_page(
        markdown_content=report_markdown,
        title=f"PD-ECR 工程变更报告 - {dc_no}",
    )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "message": "生成成功",
        "url": f"/static/reports/{filename}",
    }