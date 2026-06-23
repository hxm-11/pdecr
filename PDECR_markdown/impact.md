# PD-ECR AI Fill Converted Template

用途：这是把 PD-ECR Excel 中“选择框 + 填空项”转换成 AI 可填写的结构化文件。  
使用方式：AI 根据用户输入和历史 PD-ECR 知识库，输出与本文件字段名一致的 JSON；Python 再把 JSON 替换回 Excel 占位符。

## 通用规则

| 类型 | Excel 占位符示例 | AI 输出 |
|---|---|---|
| 普通填空 | `{{dc_no}}` | 文本 |
| yes/no 选择框 | `{{function_performance_yes_box}}` / `{{function_performance_no_box}}` | `☑` 或 `☐` |
| 三选一选择框 | `{{cost_increase_box}}` / `{{cost_decrease_box}}` / `{{cost_no_change_box}}` | 只有一个为 `☑` |
| 检查项目 | `{{trial_run_box}}` + 日期/负责人/备注 | 勾选时填写完整，不勾选时留空 |

选择框统一：
- checked = `☑`
- unchecked = `☐`

---

# Basic Information / 基本信息

| Field | Placeholder | Rule |
|---|---|---|
| Corresponding DC No. / 对应的开发更改编号 | `{{dc_no}}` | 用户输入或知识库明确值 |
| Date / 日期 | `{{date}}` | YYYY-MM-DD |
---

# Step 3.1 Impact Analysis / 影响分析

## Impact yes/no fields
 
| No. | Question | Value field | No box placeholder | Yes box placeholder | Confirmed by placeholder |
|---|---|---|---|---|---|
| 1 | Function & Performance will be influenced? / 产品功能性能影响? | `function_performance_value` | `{{function_performance_no_box}}` | `{{function_performance_yes_box}}` | `{{function_performance_confirmed_by}}` |

| 2 | Interface and Appearance will be influenced? / 接口和外观影响? | `interface_appearance_value` | `{{interface_appearance_no_box}}` | `{{interface_appearance_yes_box}}` | `{{interface_appearance_confirmed_by}}` |
| 3 | Reliability and robustness will be influenced? / 产品可靠性、鲁棒性影响? | `reliability_robustness_value` | `{{reliability_robustness_no_box}}` | `{{reliability_robustness_yes_box}}` | `{{reliability_robustness_confirmed_by}}` |
Description of above points, and concern point analysis / 对上述影响的描述, 以及分析是否存在顾虑点											
`{{impact_description}}`
| 4 | Other components will be influenced? / 其他零部件影响? | `other_components_value` | `{{other_components_no_box}}` | `{{other_components_yes_box}}` | `{{other_components_confirmed_by}}` |
 If yes,  Which components will change in parallel? 如果影响， 哪些零部件也需要同时变更?											
`{{arallel_components_description}}`
| 5 | Manufacturing / assembly / testing will be influenced? / 加工、装配、测试影响? | `manufacturing_assembly_testing_value` | `{{manufacturing_assembly_testing_no_box}}` | `{{manufacturing_assembly_testing_yes_box}}` | `{{manufacturing_assembly_testing_confirmed_by}}` |
| 6 | Influence on supplier part? / 供应商零件影响? Feedback from Supplier/Purchasing？ | `supplier_part_value` | `{{supplier_part_no_box}}` | `{{supplier_part_yes_box}}` | `{{supplier_part_confirmed_by}}` |
| 7 | Influence on System / Hardware / Software / Calibration / Mechanical parts? | `system_hw_sw_calibration_mechanical_value` | `{{system_hw_sw_calibration_mechanical_no_box}}` | `{{system_hw_sw_calibration_mechanical_yes_box}}` | `{{system_hw_sw_calibration_mechanical_confirmed_by}}` |
e.g.: If changes influnce software/calibration, and ME/HW version alignment is required. 
e.g. SW reflashing affected products in stock
e.g. Mechanical change or HW change triggered SW change, inform SW team
e.g. System element change trigger calibration change, inform Calibration team
`{{system_hw_sw_calibration_mechanical_description}}`
| 8 | Influence on cost  / 对成本的影响 | `{{cost_increase_box}}` / `{{cost_decrease_box}}` / `{{cost_no_change_box}}` |
使用方式：Excel 模板里放相同占位符，AI 输出同名 JSON，Python 替换占位符生成新 Excel。

选择框统一：
- checked = `☑`
- unchecked = `☐`

---

# Step 3.1.9 Stock / Delivery Treatment / 库存（发货）处理指示

## Mixed Deliveries Permissible / 改前改后是否可以混合供货

| Field | Placeholder | Expected value |
|---|---|---|
| Selected value | `mixed_deliveries_value` | yes / no |
| YES box | `{{mixed_deliveries_yes_box}}` | ☑ or ☐ |
| NO box | `{{mixed_deliveries_no_box}}` | ☑ or ☐ |
| How to deal with 1st delivery after change? / 改后第一批货物的发货要求 | `{{stock_delivery_treatment_answer}}` | 简短说明库存、发货、切换策略 |
| Answer confirmed by / answer 回答 | `{{stock_delivery_treatment_confirmed_by}}` | 人名或部门 |

规则：
- `mixed_deliveries_value = yes`：`mixed_deliveries_yes_box = "☑"`，`mixed_deliveries_no_box = "☐"`
- `mixed_deliveries_value = no`：`mixed_deliveries_yes_box = "☐"`，`mixed_deliveries_no_box = "☑"`

---

## Raw Materials / 原材料处理

| Option | Placeholder | Expected value |
|---|---|---|
| Selected value | `raw_materials_treatment_value` | not_affect / use_in_other_products / scrap / rework / use_up |
| Not affect | `{{raw_materials_not_affect_box}}` | ☑ or ☐ |
| Use in other products | `{{raw_materials_use_in_other_products_box}}` | ☑ or ☐ |
| Scrap | `{{raw_materials_scrap_box}}` | ☑ or ☐ |
| Rework | `{{raw_materials_rework_box}}` | ☑ or ☐ |
| Use up | `{{raw_materials_use_up_box}}` | ☑ or ☐ |
| Remark | `{{raw_materials_treatment_remark}}` | 可选，说明是否包含在途物料 |

---

## Parts / Subassemble / 零件或半成品处理

| Option | Placeholder | Expected value |
|---|---|---|
| Selected value | `parts_subassemble_treatment_value` | not_affect / use_in_other_products / scrap / rework / use_up |
| Not affect | `{{parts_subassemble_not_affect_box}}` | ☑ or ☐ |
| Use in other products | `{{parts_subassemble_use_in_other_products_box}}` | ☑ or ☐ |
| Scrap | `{{parts_subassemble_scrap_box}}` | ☑ or ☐ |
| Rework | `{{parts_subassemble_rework_box}}` | ☑ or ☐ |
| Use up | `{{parts_subassemble_use_up_box}}` | ☑ or ☐ |
| Remark | `{{parts_subassemble_treatment_remark}}` | 可选 |

---

## Finished Goods Inhouse / 厂内成品处理

| Option | Placeholder | Expected value |
|---|---|---|
| Selected value | `finished_goods_inhouse_treatment_value` | not_affect / scrap / rework / use_up |
| Not affect | `{{finished_goods_inhouse_not_affect_box}}` | ☑ or ☐ |
| Scrap | `{{finished_goods_inhouse_scrap_box}}` | ☑ or ☐ |
| Rework | `{{finished_goods_inhouse_rework_box}}` | ☑ or ☐ |
| Use up | `{{finished_goods_inhouse_use_up_box}}` | ☑ or ☐ |
| Remark | `{{finished_goods_inhouse_treatment_remark}}` | 可选 |

---

## Finished Goods RDC / RDC 外库成品处理

| Option | Placeholder | Expected value |
|---|---|---|
| Selected value | `finished_goods_rdc_treatment_value` | not_affect / scrap / rework / use_up |
| Not affect | `{{finished_goods_rdc_not_affect_box}}` | ☑ or ☐ |
| Scrap | `{{finished_goods_rdc_scrap_box}}` | ☑ or ☐ |
| Rework | `{{finished_goods_rdc_rework_box}}` | ☑ or ☐ |
| Use up | `{{finished_goods_rdc_use_up_box}}` | ☑ or ☐ |
| Remark | `{{finished_goods_rdc_treatment_remark}}` | 可选 |

---

## Finished Goods Customer / 客户处成品处理

| Option | Placeholder | Expected value |
|---|---|---|
| Selected value | `finished_goods_customer_treatment_value` | not_affect / recall / rework |
| Not affect | `{{finished_goods_customer_not_affect_box}}` | ☑ or ☐ |
| Recall | `{{finished_goods_customer_recall_box}}` | ☑ or ☐ |
| Rework | `{{finished_goods_customer_rework_box}}` | ☑ or ☐ |
| Remark | `{{finished_goods_customer_treatment_remark}}` | 可选，说明是否包含在途产品 |

---

# Step 3.2 Quality Assurance Items / 检查项目

| Item | Box placeholder | Value field | Plan finish date | Resp.person | Comments |
|---|---|---|---|---|---|
| Trial run | `{{trial_run_box}}` | `trial_run_value` | `{{trial_run_plan_finish_date}}` | `{{trial_run_resp_person}}` | `{{trial_run_comments}}` |
| Capability Studies_CMK | `{{capability_cmk_box}}` | `capability_cmk_value` | `{{capability_cmk_plan_finish_date}}` | `{{capability_cmk_resp_person}}` | `{{capability_cmk_comments}}` |
| Capability Studies_MSA | `{{capability_msa_box}}` | `capability_msa_value` | `{{capability_msa_plan_finish_date}}` | `{{capability_msa_resp_person}}` | `{{capability_msa_comments}}` |
| MAE release | `{{mae_release_box}}` | `mae_release_value` | `{{mae_release_plan_finish_date}}` | `{{mae_release_resp_person}}` | `{{mae_release_comments}}` |
| Cleanness test | `{{cleanness_test_box}}` | `cleanness_test_value` | `{{cleanness_test_plan_finish_date}}` | `{{cleanness_test_resp_person}}` | `{{cleanness_test_comments}}` |
| QZ test | `{{qz_test_box}}` | `qz_test_value` | `{{qz_test_plan_finish_date}}` | `{{qz_test_resp_person}}` | `{{qz_test_comments}}` |
| 200h PDL | `{{pdl_200h_box}}` | `pdl_200h_value` | `{{pdl_200h_plan_finish_date}}` | `{{pdl_200h_resp_person}}` | `{{pdl_200h_comments}}` |
| BOM check | `{{bom_check_box}}` | `bom_check_value` | `{{bom_check_plan_finish_date}}` | `{{bom_check_resp_person}}` | `{{bom_check_comments}}` |
| Test report | `{{test_report_box}}` | `test_report_value` | `{{test_report_plan_finish_date}}` | `{{test_report_resp_person}}` | `{{test_report_comments}}` |
| PAV release | `{{pav_release_box}}` | `pav_release_value` | `{{pav_release_plan_finish_date}}` | `{{pav_release_resp_person}}` | `{{pav_release_comments}}` |

规则：
- 需要执行：box = `☑`，value = `yes`，填写计划完成日期、负责人和备注。
- 不需要执行：box = `☐`，value = `no`，日期、负责人和备注留空。
- 日期格式统一为 `YYYY-MM-DD`。

---

# Step 3.3 Affected Documents Check / 影响文档检查

| No. | Document item | Value field | No box | Yes box | Resp.person | Due date |
|---|---|---|---|---|---|---|
| 1 | Interface FMEA relevant / IFMEA | `interface_fmea_relevant_value` | `{{interface_fmea_no_box}}` | `{{interface_fmea_yes_box}}` | `{{interface_fmea_resp_person}}` | `{{interface_fmea_due_date}}` |
| 2 | Product FMEA relevant / DFMEA | `product_fmea_relevant_value` | `{{product_fmea_no_box}}` | `{{product_fmea_yes_box}}` | `{{product_fmea_resp_person}}` | `{{product_fmea_due_date}}` |
| 3 | Special Characteristics relevant / PSC | `special_characteristics_relevant_value` | `{{special_characteristics_no_box}}` | `{{special_characteristics_yes_box}}` | `{{special_characteristics_resp_person}}` | `{{special_characteristics_due_date}}` |
| 4 | IMDS relevant | `imds_relevant_value` | `{{imds_no_box}}` | `{{imds_yes_box}}` | `{{imds_resp_person}}` | `{{imds_due_date}}` |
| 5 | Offer drawing relevant | `offer_drawing_relevant_value` | `{{offer_drawing_no_box}}` | `{{offer_drawing_yes_box}}` | `{{offer_drawing_resp_person}}` | `{{offer_drawing_due_date}}` |
| 6 | TCD relevant | `tcd_relevant_value` | `{{tcd_no_box}}` | `{{tcd_yes_box}}` | `{{tcd_resp_person}}` | `{{tcd_due_date}}` |
| 7 | Norm, WB, HF relevant | `norm_wb_hf_relevant_value` | `{{norm_wb_hf_no_box}}` | `{{norm_wb_hf_yes_box}}` | `{{norm_wb_hf_resp_person}}` | `{{norm_wb_hf_due_date}}` |
| 8 | Other affected document | `affected_document_other_value` | `{{affected_document_other_no_box}}` | `{{affected_document_other_yes_box}}` | `{{affected_document_other_resp_person}}` | `{{affected_document_other_due_date}}` |

Other document description:
- Placeholder: `{{affected_document_other_description}}`
- 用途：如果第 8 项是其他文档，请简短描述具体文档名称或类别。

---

# Step 4 Technical Feasibility & Validation Plan Approval / 技术可行性 & 验证计划批准

| Department | Placeholder | Expected value |
|---|---|---|
| Development / 研发 | `{{approval_development}}` | 人名、部门或 Required |
| Purchasing / 采购 | `{{approval_purchasing}}` | 人名、部门或 Required |
| MFE / 工艺 | `{{approval_mfe}}` | 人名、部门或 Required |
| Quality / 质量 | `{{approval_quality}}` | 人名、部门或 Required |
| CPjM / 客户项目 | `{{approval_cpjm}}` | 人名、部门或 Required |
| COS / 样品 | `{{approval_cos}}` | 人名、部门或 Required |
| MOEx / 生产 | `{{approval_moex}}` | 人名、部门或 Required |
| LOG / 物流 | `{{approval_log}}` | 人名、部门或 Required |
| Others / 其他 | `{{approval_others}}` | 如需要其他审批，填写人名或部门 |
| Note | `{{approval_note}}` | 可选，填写审批限制或特殊说明 |

特殊说明：
- 如果涉及 SW reflashing 且地点在 ME plant，最多需要 2 个负责人批准 PD-ECR，例如 MOE DM + EPQ。
- AI 应根据变更影响范围和历史案例判断哪些部门需要审批。

规则：
- value = `yes` 时：yes_box = `☑`，no_box = `☐`
- value = `no` 时：no_box = `☑`，yes_box = `☐`
- 不允许 yes 和 no 同时勾选。

## Additional description fields

| Field | Placeholder | Rule |
|---|---|---|
| If yes, which components will change in parallel? | `{{parallel_components_description}}` | 如果其他零部件同步变更，简短说明 |
| Description of above points and concern point analysis | `{{impact_description}}` | 总结影响范围、风险点、关注点 |


{
  "dc_no": "",
  "date": "",
  "function_performance_value": "yes",
  "function_performance_no_box": "☐",
  "function_performance_yes_box": "☑",
  "function_performance_confirmed_by": "Development",
  "impact_description": "",
  "mixed_deliveries_value": "no",
  "mixed_deliveries_yes_box": "☐",
  "mixed_deliveries_no_box": "☑",
  "trial_run_value": "yes",
  "trial_run_box": "☑",
  "trial_run_plan_finish_date": "",
  "trial_run_resp_person": "",
  "trial_run_comments": ""
}