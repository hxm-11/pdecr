# Step 3.1 Impact Analysis / 影响分析

## 1. Basic Information / 基本信息

| Field / 字段 | Content / 内容 |
|---|---|
| Corresponding DC No. / 对应开发更改编号 | {{ basic_info.dc_no }} |
| Date / 日期 | {{ basic_info.date }} |
| Customer Project / 客户项目 | {{ basic_info.customer_project }} |
| MCR No. | {{ basic_info.mcr_no }} |
| Product No. / 产品号 | {{ basic_info.product_no }} |
| Component No. / 部件号 | {{ basic_info.component_no }} |
| Initiator / 发起人 | {{ basic_info.initiator }} |

---


## 2. Impact Yes / No Check / 影响项判断

| No. | Check Item / 检查项 | No / 否 | Yes / 是 | Confirmed by / 确认人 |
|---|---|---|---|---|
| 1 | Function & Performance will be influenced? / 产品功能性能是否受影响 | {{ function_performance_no_box | default("☐") }} | {{ function_performance_yes_box | default("☐") }} | {{ function_performance_confirmed_by | default("") }} |
| 2 | Interface and Appearance will be influenced? / 接口和外观是否受影响 | {{ interface_appearance_no_box | default("☐") }} | {{ interface_appearance_yes_box | default("☐") }} | {{ interface_appearance_confirmed_by | default("") }} |
| 3 | Reliability and robustness will be influenced? / 产品可靠性、鲁棒性是否受影响 | {{ reliability_robustness_no_box | default("☐") }} | {{ reliability_robustness_yes_box | default("☐") }} | {{ reliability_robustness_confirmed_by | default("") }} |
| 4 | Other components will be influenced? / 其他零部件是否受影响 | {{ other_components_no_box | default("☐") }} | {{ other_components_yes_box | default("☐") }} | {{ other_components_confirmed_by | default("") }} |
| 5 | Manufacturing / assembly / testing will be influenced? / 加工、装配、测试是否受影响 | {{ manufacturing_assembly_testing_no_box | default("☐") }} | {{ manufacturing_assembly_testing_yes_box | default("☐") }} | {{ manufacturing_assembly_testing_confirmed_by | default("") }} |
| 6 | Influence on supplier part? / 供应商零件是否受影响 | {{ supplier_part_no_box | default("☐") }} | {{ supplier_part_yes_box | default("☐") }} | {{ supplier_part_confirmed_by | default("") }} |
| 7 | Influence on System / Hardware / Software / Calibration / Mechanical parts? / 系统、硬件、软件、标定、机械件是否受影响 | {{ system_hw_sw_calibration_mechanical_no_box | default("☐") }} | {{ system_hw_sw_calibration_mechanical_yes_box | default("☐") }} | {{ system_hw_sw_calibration_mechanical_confirmed_by | default("") }} |

### 8. Influence on cost / 对成本的影响

| Cost Increase / 成本增加 | Cost Decrease / 成本降低 | No Change / 无变化 |
|---|---|---|
| {{ cost_increase_box | default("☐") }} | {{ cost_decrease_box | default("☐") }} | {{ cost_no_change_box | default("☐") }} |

## 9. Stock / Delivery Treatment / 库存（发货）处理指示

### Mixed Deliveries Permissible / 改前改后是否可以混合供货

| Item / 项目 | YES / 是 | NO / 否 | Comment / 说明 |
|---|---|---|---|
| Mixed Deliveries Permissible? / 改前改后是否可以混合供货？ | {{ mixed_deliveries_yes_box | default("☐") }} | {{ mixed_deliveries_no_box | default("☐") }} | {{ mixed_deliveries_comment | default("") }} |

### How to deal with 1st delivery after change / 改后第一批货物的发货要求

| Answer / 答案 | Remark / 备注 |
|---|---|
| {{ stock_delivery_treatment_answer | default("") }} | {{ stock_delivery_treatment_remark | default("") }} |

### Stock Treatment / 库存处理

| Stock Type / 库存类型 | Not Affect / 不影响 | Use in Other Products / 用于其他产品 | Scrap / 报废 | Rework / 返工 | Use Up / 消耗完 | Recall / 召回 | Remark / 备注 |
|---|---|---|---|---|---|---|---|
| Raw materials / 原材料 | {{ raw_materials_not_affect_box | default("☐") }} | {{ raw_materials_use_in_other_products_box | default("☐") }} | {{ raw_materials_scrap_box | default("☐") }} | {{ raw_materials_rework_box | default("☐") }} | {{ raw_materials_use_up_box | default("☐") }} |  | {{ raw_materials_treatment_remark | default("") }} |
| Parts / Subassemble / 零件或半成品 | {{ parts_subassemble_not_affect_box | default("☐") }} | {{ parts_subassemble_use_in_other_products_box | default("☐") }} | {{ parts_subassemble_scrap_box | default("☐") }} | {{ parts_subassemble_rework_box | default("☐") }} | {{ parts_subassemble_use_up_box | default("☐") }} |  | {{ parts_subassemble_treatment_remark | default("") }} |
| Finished goods (inhouse) / 厂内成品 | {{ finished_goods_inhouse_not_affect_box | default("☐") }} |  | {{ finished_goods_inhouse_scrap_box | default("☐") }} | {{ finished_goods_inhouse_rework_box | default("☐") }} | {{ finished_goods_inhouse_use_up_box | default("☐") }} |  | {{ finished_goods_inhouse_treatment_remark | default("") }} |
| Finished goods (RDC 外库) | {{ finished_goods_rdc_not_affect_box | default("☐") }} |  | {{ finished_goods_rdc_scrap_box | default("☐") }} | {{ finished_goods_rdc_rework_box | default("☐") }} | {{ finished_goods_rdc_use_up_box | default("☐") }} |  | {{ finished_goods_rdc_treatment_remark | default("") }} |
| Finished goods (customer) / 客户处成品 | {{ finished_goods_customer_not_affect_box | default("☐") }} |  |  | {{ finished_goods_customer_rework_box | default("☐") }} |  | {{ finished_goods_customer_recall_box | default("☐") }} | {{ finished_goods_customer_treatment_remark | default("") }} |


### Impact Check Comments / 影响项说明

{% if function_performance_comment %}
**1. Function & Performance:**  
{{ function_performance_comment }}
{% endif %}

{% if interface_appearance_comment %}
**2. Interface and Appearance:**  
{{ interface_appearance_comment }}
{% endif %}

{% if reliability_robustness_comment %}
**3. Reliability and robustness:**  
{{ reliability_robustness_comment }}
{% endif %}

{% if other_components_comment %}
**4. Other components:**  
{{ other_components_comment }}
{% endif %}

{% if manufacturing_assembly_testing_comment %}
**5. Manufacturing / assembly / testing:**  
{{ manufacturing_assembly_testing_comment }}
{% endif %}

{% if supplier_part_comment %}
**6. Supplier part:**  
{{ supplier_part_comment }}
{% endif %}

{% if system_hw_sw_calibration_mechanical_comment %}
**7. System / HW / SW / Calibration / Mechanical:**  
{{ system_hw_sw_calibration_mechanical_comment }}
{% endif %}

{% if cost_impact_description %}
**8. Influence on cost / 对成本的影响：**  
{{ cost_impact_description }}
{% endif %}
---

# Step 3.2 Quality Assurance Items / 质量保证检查项

| Item / 项目 | Required / 是否需要 | Plan Finish Date / 计划完成日期 | Responsible / 负责人 | Comments / 备注 |
|---|---|---|---|---|
| Trial run | {{ trial_run_yes_box | default("☐") }} | {{ trial_run_plan_finish_date | default("") }} | {{ trial_run_resp_person | default("") }} | {{ trial_run_comments | default("") }} |
| Capability Studies - CMK | {{ capability_cmk_yes_box | default("☐") }} | {{ capability_cmk_plan_finish_date | default("") }} | {{ capability_cmk_resp_person | default("") }} | {{ capability_cmk_comments | default("") }} |
| Capability Studies - MSA | {{ capability_msa_yes_box | default("☐") }} | {{ capability_msa_plan_finish_date | default("") }} | {{ capability_msa_resp_person | default("") }} | {{ capability_msa_comments | default("") }} |
| MAE release | {{ mae_release_yes_box | default("☐") }} | {{ mae_release_plan_finish_date | default("") }} | {{ mae_release_resp_person | default("") }} | {{ mae_release_comments | default("") }} |
| Cleanness test | {{ cleanness_test_yes_box | default("☐") }} | {{ cleanness_test_plan_finish_date | default("") }} | {{ cleanness_test_resp_person | default("") }} | {{ cleanness_test_comments | default("") }} |
| QZ test | {{ qz_test_yes_box | default("☐") }} | {{ qz_test_plan_finish_date | default("") }} | {{ qz_test_resp_person | default("") }} | {{ qz_test_comments | default("") }} |
| 200h PDL | {{ pdl_200h_yes_box | default("☐") }} | {{ pdl_200h_plan_finish_date | default("") }} | {{ pdl_200h_resp_person | default("") }} | {{ pdl_200h_comments | default("") }} |
| BOM check | {{ bom_check_yes_box | default("☐") }} | {{ bom_check_plan_finish_date | default("") }} | {{ bom_check_resp_person | default("") }} | {{ bom_check_comments | default("") }} |
| Test report | {{ test_report_yes_box | default("☐") }} | {{ test_report_plan_finish_date | default("") }} | {{ test_report_resp_person | default("") }} | {{ test_report_comments | default("") }} |
| PAV release | {{ pav_release_yes_box | default("☐") }} | {{ pav_release_plan_finish_date | default("") }} | {{ pav_release_resp_person | default("") }} | {{ pav_release_comments | default("") }} |

---

# Step 3.3 Affected Documents Check / 影响文档检查

| No. | Document Item / 文档项目 | No | Yes | Responsible / 负责人 | Due Date / 截止日期 |
|---|---|---|---|---|---|
| 1 | Interface FMEA relevant / IFMEA | {{ interface_fmea_no_box | default("☐") }} | {{ interface_fmea_yes_box | default("☐") }} | {{ interface_fmea_resp_person | default("Development") }} | {{ interface_fmea_due_date | default("") }} |
| 2 | Product FMEA relevant / DFMEA | {{ product_fmea_no_box | default("☐") }} | {{ product_fmea_yes_box | default("☐") }} | {{ product_fmea_resp_person | default("Development") }} | {{ product_fmea_due_date | default("") }} |
| 3 | Special Characteristics relevant / PSC | {{ special_characteristics_no_box | default("☐") }} | {{ special_characteristics_yes_box | default("☐") }} | {{ special_characteristics_resp_person | default("Quality") }} | {{ special_characteristics_due_date | default("") }} |
| 4 | IMDS relevant | {{ imds_no_box | default("☐") }} | {{ imds_yes_box | default("☐") }} | {{ imds_resp_person | default("Development / Purchasing") }} | {{ imds_due_date | default("") }} |
| 5 | Offer drawing relevant | {{ offer_drawing_no_box | default("☐") }} | {{ offer_drawing_yes_box | default("☐") }} | {{ offer_drawing_resp_person | default("Development") }} | {{ offer_drawing_due_date | default("") }} |
| 6 | TCD relevant | {{ tcd_no_box | default("☐") }} | {{ tcd_yes_box | default("☐") }} | {{ tcd_resp_person | default("Development") }} | {{ tcd_due_date | default("") }} |
| 7 | Norm, WB, HF relevant | {{ norm_wb_hf_no_box | default("☐") }} | {{ norm_wb_hf_yes_box | default("☐") }} | {{ norm_wb_hf_resp_person | default("Development") }} | {{ norm_wb_hf_due_date | default("") }} |
| 8 | WI Check | {{ affected_document_other_no_box | default("☐") }} | {{ affected_document_other_yes_box | default("☐") }} | {{ affected_document_other_resp_person | default("") }} | {{ affected_document_other_due_date | default("") }} |

{% if affected_document_other_description %}
Other document description / 其他文档说明：

{{ affected_document_other_description }}
{% endif %}

---

