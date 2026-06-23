# PD-ECR Implementation Page Converted Markdown Template 
AI 根据用户输入和历史 PD-ECR 知识库输出 JSON；Python 再把 JSON 替换回 Excel 中相同字段名的占位符。

## 通用规则

| 类型 | Excel 占位符示例 | AI 输出规则 |
|---|---|---|
| 普通填空 | `{{dc_no}}` | 短文本或日期 |
| Y/N 字段 | `{{dev_bom_yn}}` | 只能输出 `Y` 或 `N` |
| Responsible | `{{dev_bom_responsible}}` | 人名或部门，如 Development / Manufacturing / MFE / Quality / Purchasing / LOG / PMO |
| Due date | `{{dev_bom_due_date}}` | 日期格式 `YYYY-MM-DD`，无法判断则留空 |
| Approval | `{{approval_quality}}` | 人名、部门、Required 或空字符串 |

规则：

- 字段名必须使用小写英文和下划线。
- 不要使用 `AI`、`未提供`、`无法判断` 作为最终填充值。
- 如果知识库有明确历史负责人，优先使用历史负责人；如果没有明确人名，则使用责任部门。
- 如果某项 Y/N 为 `N`，对应 Responsible 和 Due date 可留空，除非模板或业务明确要求填写。
- Due date 应结合 planned implementation date 和历史案例周期合理推断。

---

# Header / 表头信息

| Field | Placeholder | Expected value |
|---|---|---|
| Corresponding DC No. / 对应的开发更改编号 | `{{dc_no}}` | 用户输入或知识库明确值 |
| Date / 日期 | `{{date}}` | `YYYY-MM-DD` |
| Development confirmation / 研发确认 | `{{development_confirmation}}` | 人名或部门 |

---

# Step 6.1 Implementation Checklist / 导入清单

| Department | Description | Y/N placeholder | Responsible placeholder | Due date placeholder |
|---|---|---|---|---|
| Development | Change BOMs & Drawings & Documents in POE system | `{{dev_bom_yn}}` | `{{dev_bom_responsible}}` | `{{dev_bom_due_date}}` |
| Development | Inform documents update (check work-on can meet requirements) | `{{dev_doc_update_yn}}` | `{{dev_doc_update_responsible}}` | `{{dev_doc_update_due_date}}` |
| Development | Update Offer drawing, TCD, D-FMEA | `{{dev_offer_drawing_tcd_dfmea_yn}}` | `{{dev_offer_drawing_tcd_dfmea_responsible}}` | `{{dev_offer_drawing_tcd_dfmea_due_date}}` |
| Development | Norm, WB, HF... | `{{dev_norm_wb_hf_yn}}` | `{{dev_norm_wb_hf_responsible}}` | `{{dev_norm_wb_hf_due_date}}` |
| Development | MoC, IMDS. | `{{dev_moc_imds_yn}}` | `{{dev_moc_imds_responsible}}` | `{{dev_moc_imds_due_date}}` |
| Manufacturing | Related Production/Testing equipment be ready on site | `{{mfg_equipment_ready_yn}}` | `{{mfg_equipment_ready_responsible}}` | `{{mfg_equipment_ready_due_date}}` |
| Manufacturing | Related Production/Testing program be ready. If related to lettering, labeling or marking change, provide change evidence in Remark column. | `{{mfg_program_ready_yn}}` | `{{mfg_program_ready_responsible}}` | `{{mfg_program_ready_due_date}}` |
| Manufacturing | Related Production/Testing tooling / cutting / fixture etc. be ready | `{{mfg_tooling_fixture_ready_yn}}` | `{{mfg_tooling_fixture_ready_responsible}}` | `{{mfg_tooling_fixture_ready_due_date}}` |
| Manufacturing | Old tooling / cutting / fixture disposal | `{{mfg_old_tooling_disposal_yn}}` | `{{mfg_old_tooling_disposal_responsible}}` | `{{mfg_old_tooling_disposal_due_date}}` |
| Manufacturing | Old materials disposal | `{{mfg_old_materials_disposal_yn}}` | `{{mfg_old_materials_disposal_responsible}}` | `{{mfg_old_materials_disposal_due_date}}` |
| Manufacturing | Planner update the planning sheet | `{{mfg_planning_sheet_update_yn}}` | `{{mfg_planning_sheet_update_responsible}}` | `{{mfg_planning_sheet_update_due_date}}` |
| Manufacturing | Update FMEA | `{{mfg_fmea_update_yn}}` | `{{mfg_fmea_update_responsible}}` | `{{mfg_fmea_update_due_date}}` |
| Manufacturing | Update CP/FC (Control Plan/Flow Chart) | `{{mfg_cpfc_update_yn}}` | `{{mfg_cpfc_update_responsible}}` | `{{mfg_cpfc_update_due_date}}` |
| Manufacturing | Update WI/PDS (Include attachments.) | `{{mfg_wi_pds_update_yn}}` | `{{mfg_wi_pds_update_responsible}}` | `{{mfg_wi_pds_update_due_date}}` |
| Manufacturing | First batch Mark, Special Mark (Inside Package) | `{{mfg_first_batch_mark_inside_package_yn}}` | `{{mfg_first_batch_mark_inside_package_responsible}}` | `{{mfg_first_batch_mark_inside_package_due_date}}` |
| Manufacturing | First batch Mark, Special Mark (Outside Package) | `{{mfg_first_batch_mark_outside_package_yn}}` | `{{mfg_first_batch_mark_outside_package_responsible}}` | `{{mfg_first_batch_mark_outside_package_due_date}}` |
| Manufacturing | Training | `{{mfg_training_yn}}` | `{{mfg_training_responsible}}` | `{{mfg_training_due_date}}` |
| COS | Confirm the storage of old parts and coordinate the introduction date for new part (RM) | `{{cos_storage_old_parts_new_rm_intro_yn}}` | `{{cos_storage_old_parts_new_rm_intro_responsible}}` | `{{cos_storage_old_parts_new_rm_intro_due_date}}` |
| COS | Confirm the delivery date of old parts and first delivery of new parts (FG) | `{{cos_delivery_old_parts_first_new_fg_yn}}` | `{{cos_delivery_old_parts_first_new_fg_responsible}}` | `{{cos_delivery_old_parts_first_new_fg_due_date}}` |
| COS | Check sample orders which affected: material order of CKD | `{{cos_ckd_material_order_sample_orders_yn}}` | `{{cos_ckd_material_order_sample_orders_responsible}}` | `{{cos_ckd_material_order_sample_orders_due_date}}` |
| COS | Confirm production scheduling according to the alignment, any changes share the information to MOEx, MFE | `{{cos_production_scheduling_alignment_yn}}` | `{{cos_production_scheduling_alignment_responsible}}` | `{{cos_production_scheduling_alignment_due_date}}` |
| COS | Confirm the old stock / do prioritize delivery and inventory handling | `{{cos_old_stock_inventory_handling_yn}}` | `{{cos_old_stock_inventory_handling_responsible}}` | `{{cos_old_stock_inventory_handling_due_date}}` |
| COS | Inform the first delivery to PMO | `{{cos_first_delivery_to_pmo_yn}}` | `{{cos_first_delivery_to_pmo_responsible}}` | `{{cos_first_delivery_to_pmo_due_date}}` |
| COS | Check sample orders which affected: material order of purchasing parts | `{{cos_ckd_purchasing_parts_sample_orders_yn}}` | `{{cos_ckd_purchasing_parts_sample_orders_responsible}}` | `{{cos_ckd_purchasing_parts_sample_orders_due_date}}` |
| Purchasing | Inform internal related departments (COS, MFE, MOEx) with following requirements: yellow sticker, delivery quantities and date, PN No. and name, change description... | `{{purchasing_internal_departments_requirements_yn}}` | `{{purchasing_internal_departments_requirements_responsible}}` | `{{purchasing_internal_departments_requirements_due_date}}` |
| Quality | Update incoming inspection plan | `{{quality_incoming_inspection_plan_update_yn}}` | `{{quality_incoming_inspection_plan_update_responsible}}` | `{{quality_incoming_inspection_plan_update_due_date}}` |
| Quality | Update testing program on testing equipment | `{{quality_testing_program_update_yn}}` | `{{quality_testing_program_update_responsible}}` | `{{quality_testing_program_update_due_date}}` |
| Quality | Update inspection plan for CKD parts | `{{quality_ckd_inspection_plan_update_yn}}` | `{{quality_ckd_inspection_plan_update_responsible}}` | `{{quality_ckd_inspection_plan_update_due_date}}` |
| CPjM | Distribute the Offer drawing, TCD to customer | `{{cpjm_offer_drawing_tcd_customer_yn}}` | `{{cpjm_offer_drawing_tcd_customer_responsible}}` | `{{cpjm_offer_drawing_tcd_customer_due_date}}` |
| LOP | Check 10 digit material order | `{{lop_10_digit_material_order_check_yn}}` | `{{lop_10_digit_material_order_check_responsible}}` | `{{lop_10_digit_material_order_check_due_date}}` |
| PMO | Check sample orders which affected: Customer order | `{{pmo_customer_order_sample_orders_yn}}` | `{{pmo_customer_order_sample_orders_responsible}}` | `{{pmo_customer_order_sample_orders_due_date}}` |
| PMO | Inform Customer the first delivery information | `{{pmo_customer_first_delivery_information_yn}}` | `{{pmo_customer_first_delivery_information_responsible}}` | `{{pmo_customer_first_delivery_information_due_date}}` |
| Others (e.g. actions in HW, SW) | Other action 1 / Description: `{{other_hw_sw_actions_1_description}}` | `{{other_hw_sw_actions_1_yn}}` | `{{other_hw_sw_actions_1_responsible}}` | `{{other_hw_sw_actions_1_due_date}}` |
| Others (e.g. actions in HW, SW) | Other action 2 / Description: `{{other_hw_sw_actions_2_description}}` | `{{other_hw_sw_actions_2_yn}}` | `{{other_hw_sw_actions_2_responsible}}` | `{{other_hw_sw_actions_2_due_date}}` |

规则：

- `Y/N` 根据新 ECR 是否涉及该执行项判断。
- `Responsible` 根据历史案例、部门职责和当前变更影响范围推断。
- `Due date` 根据计划导入日期、任务复杂度和历史案例合理推断。
- 如果是文档更新类，通常责任部门可能是 Development / MFE / Quality。
- 如果是生产、工装、FMEA、CP/FC、WI/PDS、Training，通常责任部门可能是 Manufacturing / MFE。
- 如果是检验计划、测试程序、CKD inspection，通常责任部门可能是 Quality。
- 如果是库存、交付、客户通知，通常责任部门可能是 COS / LOG / PMO。

---

# Step 6.2 Implementation Date / 执行日期

| Field | Placeholder | Expected value |
|---|---|---|
| Planned implementation date / 变更计划执行日期 | `{{planned_implementation_date}}` | `YYYY-MM-DD` |

---

# Step 7 Implementation Approval / 导入清单审批

| Department | Placeholder | Expected value |
|---|---|---|
| Development / 研发 | `{{approval_development}}` | 人名、部门、Required 或空字符串 |
| Purchasing / 采购 | `{{approval_purchasing}}` | 人名、部门、Required 或空字符串 |
| MFE / 工艺 | `{{approval_mfe}}` | 人名、部门、Required 或空字符串 |
| COS / 样品 | `{{approval_cos}}` | 人名、部门、Required 或空字符串 |
| Quality / 质量 | `{{approval_quality}}` | 人名、部门、Required 或空字符串 |
| CPjM / 客户项目 | `{{approval_cpjm}}` | 人名、部门、Required 或空字符串 |
| MOEx / 生产 | `{{approval_moex}}` | 人名、部门、Required 或空字符串 |
| LOG / 物流 | `{{approval_log}}` | 人名、部门、Required 或空字符串 |
| Other / 其他 | `{{approval_other}}` | 人名、部门、Required 或空字符串 |

规则：

- 需要审批的部门根据变更影响范围判断。
- 涉及图纸、BOM、技术文件时，Development 通常需要。
- 涉及供应商、采购件、物料订单时，Purchasing 通常需要。
- 涉及工艺、生产、FMEA、CP/FC、WI/PDS、工装夹具时，MFE / MOEx 通常需要。
- 涉及检验、质量验证、测试程序时，Quality 通常需要。
- 涉及库存、交付、物流时，LOG / COS / PMO 通常需要。

---

# AI JSON Output Schema

AI 必须只输出一个完整 JSON 对象，字段名与下列 schema 完全一致：

```json
{
  "dc_no": "",
  "date": "",
  "development_confirmation": "",
  "dev_bom_yn": "Y/N",
  "dev_bom_responsible": "",
  "dev_bom_due_date": "",
  "dev_doc_update_yn": "Y/N",
  "dev_doc_update_responsible": "",
  "dev_doc_update_due_date": "",
  "dev_offer_drawing_tcd_dfmea_yn": "Y/N",
  "dev_offer_drawing_tcd_dfmea_responsible": "",
  "dev_offer_drawing_tcd_dfmea_due_date": "",
  "dev_norm_wb_hf_yn": "Y/N",
  "dev_norm_wb_hf_responsible": "",
  "dev_norm_wb_hf_due_date": "",
  "dev_moc_imds_yn": "Y/N",
  "dev_moc_imds_responsible": "",
  "dev_moc_imds_due_date": "",
  "mfg_equipment_ready_yn": "Y/N",
  "mfg_equipment_ready_responsible": "",
  "mfg_equipment_ready_due_date": "",
  "mfg_program_ready_yn": "Y/N",
  "mfg_program_ready_responsible": "",
  "mfg_program_ready_due_date": "",
  "mfg_tooling_fixture_ready_yn": "Y/N",
  "mfg_tooling_fixture_ready_responsible": "",
  "mfg_tooling_fixture_ready_due_date": "",
  "mfg_old_tooling_disposal_yn": "Y/N",
  "mfg_old_tooling_disposal_responsible": "",
  "mfg_old_tooling_disposal_due_date": "",
  "mfg_old_materials_disposal_yn": "Y/N",
  "mfg_old_materials_disposal_responsible": "",
  "mfg_old_materials_disposal_due_date": "",
  "mfg_planning_sheet_update_yn": "Y/N",
  "mfg_planning_sheet_update_responsible": "",
  "mfg_planning_sheet_update_due_date": "",
  "mfg_fmea_update_yn": "Y/N",
  "mfg_fmea_update_responsible": "",
  "mfg_fmea_update_due_date": "",
  "mfg_cpfc_update_yn": "Y/N",
  "mfg_cpfc_update_responsible": "",
  "mfg_cpfc_update_due_date": "",
  "mfg_wi_pds_update_yn": "Y/N",
  "mfg_wi_pds_update_responsible": "",
  "mfg_wi_pds_update_due_date": "",
  "mfg_first_batch_mark_inside_package_yn": "Y/N",
  "mfg_first_batch_mark_inside_package_responsible": "",
  "mfg_first_batch_mark_inside_package_due_date": "",
  "mfg_first_batch_mark_outside_package_yn": "Y/N",
  "mfg_first_batch_mark_outside_package_responsible": "",
  "mfg_first_batch_mark_outside_package_due_date": "",
  "mfg_training_yn": "Y/N",
  "mfg_training_responsible": "",
  "mfg_training_due_date": "",
  "cos_storage_old_parts_new_rm_intro_yn": "Y/N",
  "cos_storage_old_parts_new_rm_intro_responsible": "",
  "cos_storage_old_parts_new_rm_intro_due_date": "",
  "cos_delivery_old_parts_first_new_fg_yn": "Y/N",
  "cos_delivery_old_parts_first_new_fg_responsible": "",
  "cos_delivery_old_parts_first_new_fg_due_date": "",
  "cos_ckd_material_order_sample_orders_yn": "Y/N",
  "cos_ckd_material_order_sample_orders_responsible": "",
  "cos_ckd_material_order_sample_orders_due_date": "",
  "cos_production_scheduling_alignment_yn": "Y/N",
  "cos_production_scheduling_alignment_responsible": "",
  "cos_production_scheduling_alignment_due_date": "",
  "cos_old_stock_inventory_handling_yn": "Y/N",
  "cos_old_stock_inventory_handling_responsible": "",
  "cos_old_stock_inventory_handling_due_date": "",
  "cos_first_delivery_to_pmo_yn": "Y/N",
  "cos_first_delivery_to_pmo_responsible": "",
  "cos_first_delivery_to_pmo_due_date": "",
  "cos_ckd_purchasing_parts_sample_orders_yn": "Y/N",
  "cos_ckd_purchasing_parts_sample_orders_responsible": "",
  "cos_ckd_purchasing_parts_sample_orders_due_date": "",
  "purchasing_internal_departments_requirements_yn": "Y/N",
  "purchasing_internal_departments_requirements_responsible": "",
  "purchasing_internal_departments_requirements_due_date": "",
  "quality_incoming_inspection_plan_update_yn": "Y/N",
  "quality_incoming_inspection_plan_update_responsible": "",
  "quality_incoming_inspection_plan_update_due_date": "",
  "quality_testing_program_update_yn": "Y/N",
  "quality_testing_program_update_responsible": "",
  "quality_testing_program_update_due_date": "",
  "quality_ckd_inspection_plan_update_yn": "Y/N",
  "quality_ckd_inspection_plan_update_responsible": "",
  "quality_ckd_inspection_plan_update_due_date": "",
  "cpjm_offer_drawing_tcd_customer_yn": "Y/N",
  "cpjm_offer_drawing_tcd_customer_responsible": "",
  "cpjm_offer_drawing_tcd_customer_due_date": "",
  "lop_10_digit_material_order_check_yn": "Y/N",
  "lop_10_digit_material_order_check_responsible": "",
  "lop_10_digit_material_order_check_due_date": "",
  "pmo_customer_order_sample_orders_yn": "Y/N",
  "pmo_customer_order_sample_orders_responsible": "",
  "pmo_customer_order_sample_orders_due_date": "",
  "pmo_customer_first_delivery_information_yn": "Y/N",
  "pmo_customer_first_delivery_information_responsible": "",
  "pmo_customer_first_delivery_information_due_date": "",
  "other_hw_sw_actions_1_yn": "Y/N",
  "other_hw_sw_actions_1_description": "",
  "other_hw_sw_actions_1_responsible": "",
  "other_hw_sw_actions_1_due_date": "",
  "other_hw_sw_actions_2_yn": "Y/N",
  "other_hw_sw_actions_2_description": "",
  "other_hw_sw_actions_2_responsible": "",
  "other_hw_sw_actions_2_due_date": "",
  "planned_implementation_date": "",
  "approval_development": "",
  "approval_purchasing": "",
  "approval_mfe": "",
  "approval_cos": "",
  "approval_quality": "",
  "approval_cpjm": "",
  "approval_moex": "",
  "approval_log": "",
  "approval_other": ""
}
```