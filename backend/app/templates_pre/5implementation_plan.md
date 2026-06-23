# Step 6 Implementation Plan / 导入计划

## 1. Header / 表头信息

| Field / 字段 | Content / 内容 |
|---|---|
| Corresponding DC No. / 对应开发更改编号 | {{ basic_info.dc_no | default(dc_no) }} |
| Date / 日期 | {{ basic_info.date | default(date) }} |
| Development Confirmation / 研发确认 | {{ development_confirmation | default("Development") }} |

---

## 2. Implementation Summary / 导入概要

{{ implementation_plan | default("根据本次工程变更内容，需完成相关文件更新、生产准备、质量验证、库存切换及部门审批。") }}

---

# Step 6.1 Implementation Checklist / 导入清单

## 2.1 Development / 研发

| Departments | Y/N |  Description  | Responsible | Due date | Status / Comments |
|---|---|---|---|---|---|
| Development | {{ dev_bom_yn | default("N") }} | Change BOMs & Drawings & Documents in POE system | {{ dev_bom_responsible | default("") }} | {{ dev_bom_due_date | default("") }} | {{ dev_bom_comments | default("") }} |
| Development | {{ dev_doc_update_yn | default("N") }} | Inform documents update（check work-on car requirements） | {{ dev_doc_update_responsible | default("") }} | {{ dev_doc_update_due_date | default("") }} | {{ dev_doc_update_comments | default("") }} |
| Development | {{ dev_offer_drawing_tcd_dfmea_yn | default("N") }} | Update Offer drawing, TCD, D-FMEA | {{ dev_offer_drawing_tcd_dfmea_responsible | default("") }} | {{ dev_offer_drawing_tcd_dfmea_due_date | default("") }} | {{ dev_offer_drawing_tcd_dfmea_comments | default("") }} |
| Development | {{ dev_norm_wb_hf_yn | default("N") }} | Norm, WB, HF... | {{ dev_norm_wb_hf_responsible | default("") }} | {{ dev_norm_wb_hf_due_date | default("") }} | {{ dev_norm_wb_hf_comments | default("") }} |
| Development | {{ dev_moc_imds_yn | default("N") }} | MoC, IMDS | {{ dev_moc_imds_responsible | default("") }} | {{ dev_moc_imds_due_date | default("") }} | {{ dev_moc_imds_comments | default("") }} |

---

## 2.2 Manufacturing / MFE / 生产与工艺

| Departments | Y/N |  Description  | Responsible | Due date | Status / Comments |
|---|---|---|---|---|---|
| Manufacturing | {{ mfg_equipment_ready_yn | default("N" )}} | Related (Production/Testing) equipement be ready on site | {{ mfg_equipment_ready_responsible | default("") }} | {{ mfg_equipment_ready_due_date | default("") }} | {{ mfg_equipment_ready_comments | default("") }} |
| Manufacturing | {{ mfg_program_ready_yn | default("N" )}} | Related (Production/Testing) program be ready( If related to lettering, labeling or marking change, it's mandatory to provide the change evidence in Remark column) | {{ mfg_program_ready_responsible | default("") }} | {{ mfg_program_ready_due_date | default("") }} | {{ mfg_program_ready_comments | default("") }} |
| Manufacturing | {{ mfg_tooling_fixture_ready_yn | default("N" )}} | Related (Production/Testing) tooling / cutting / fixture etc. be ready | {{ mfg_tooling_fixture_ready_responsible | default("") }} | {{ mfg_tooling_fixture_ready_due_date | default("") }} | {{ mfg_tooling_fixture_ready_comments | default("") }} |
| Manufacturing | {{ mfg_old_tooling_disposal_yn | default("N" )}} | Old tooling / cutting / fixture disposal | {{ mfg_old_tooling_disposal_responsible | default("") }} | {{ mfg_old_tooling_disposal_due_date | default("") }} | {{ mfg_old_tooling_disposal_comments | default("") }} |
| Manufacturing | {{ mfg_old_materials_disposal_yn | default("N" )}} | Old materials disposal | {{ mfg_old_materials_disposal_responsible | default("") }} | {{ mfg_old_materials_disposal_due_date | default("") }} | {{ mfg_old_materials_disposal_comments | default("") }} |
| Manufacturing | {{ mfg_planning_sheet_update_yn | default("N" )}} | Planner update the planning sheet | {{ mfg_planning_sheet_update_responsible | default("") }} | {{ mfg_planning_sheet_update_due_date | default("") }} | {{ mfg_planning_sheet_update_comments | default("") }} |
| Manufacturing | {{ mfg_fmea_update_yn | default("N" )}} | Update FMEA | {{ mfg_fmea_update_responsible | default("") }} | {{ mfg_fmea_update_due_date | default("") }} | {{ mfg_fmea_update_comments | default("") }} |
| Manufacturing | {{ mfg_cpfc_update_yn | default("N" )}} | Update CP/FC (Control Plan/Flow Chart) | {{ mfg_cpfc_update_responsible | default("") }} | {{ mfg_cpfc_update_due_date | default("") }} | {{ mfg_cpfc_update_comments | default("") }} |
| Manufacturing | {{ mfg_wi_pds_update_yn | default("N" )}} | Update WI/PDS (Include attachments.) | {{ mfg_wi_pds_update_responsible | default("") }} | {{ mfg_wi_pds_update_due_date | default("") }} | {{ mfg_wi_pds_update_comments | default("") }} |
| Manufacturing | {{ mfg_first_batch_mark_inside_package_yn | default("N" )}} | First batch Mark, Special Mark (Inside Package) | {{ mfg_first_batch_mark_inside_package_responsible | default("") }} | {{ mfg_first_batch_mark_inside_package_due_date | default("") }} | {{ mfg_first_batch_mark_inside_package_comments | default("") }} |
| Manufacturing | {{ mfg_first_batch_mark_outside_package_yn | default("N" )}} | First batch Mark, Special Mark (Outside Package) | {{ mfg_first_batch_mark_outside_package_responsible | default("") }} | {{ mfg_first_batch_mark_outside_package_due_date | default("") }} | {{ mfg_first_batch_mark_outside_package_comments | default("") }} |
| Manufacturing | {{ mfg_training_yn | default("N" )}} | Training | {{ mfg_training_responsible | default("") }} | {{ mfg_training_due_date | default("") }} | {{ mfg_training_comments | default("") }} |

---

## 2.3 COS

| Departments | Y/N |  Description  | Responsible | Due date | Status / Comments |
|---|---|---|---|---|---|
| COS | {{ cos_storage_old_parts_new_rm_intro_yn | default("N" )}} | Confirm the storage of old parts and coordinate the introduction date for new part (RM) | {{ cos_storage_old_parts_new_rm_intro_responsible | default("") }} | {{ cos_storage_old_parts_new_rm_intro_due_date | default("") }} | {{ cos_storage_old_parts_new_rm_intro_comments | default("") }} |
| COS | {{ cos_delivery_old_parts_first_new_fg_yn | default("N" )}} | Confirm the delivery date of old parts and first delivery of new parts (FG) | {{ cos_delivery_old_parts_first_new_fg_responsible | default("") }} | {{ cos_delivery_old_parts_first_new_fg_due_date | default("") }} | {{ cos_delivery_old_parts_first_new_fg_comments | default("") }} |
| COS | {{ cos_ckd_material_order_sample_orders_yn | default("N" )}} | Check sample orders which affected:material order of  CKD | {{ cos_ckd_material_order_sample_orders_responsible | default("") }} | {{ cos_ckd_material_order_sample_orders_due_date | default("") }} | {{ cos_ckd_material_order_sample_orders_comments | default("") }} |
| COS | {{ cos_production_scheduling_alignment_yn | default("N" )}} | Confirm production scheduling according to the alignment, any changes share the information to MOEx,MFE | {{ cos_production_scheduling_alignment_responsible | default("") }} | {{ cos_production_scheduling_alignment_due_date | default("") }} | {{ cos_production_scheduling_alignment_comments | default("") }} |
| COS | {{ cos_old_stock_inventory_handling_yn | default("N" )}} | Confirm the old stock/ do prioritize delivery and inventory handling | {{ cos_old_stock_inventory_handling_responsible | default("") }} | {{ cos_old_stock_inventory_handling_due_date | default("") }} | {{ cos_old_stock_inventory_handling_comments | default("") }} |
| COS | {{ cos_first_delivery_to_pmo_yn | default("N" )}} | Inform the first delivery to PMO | {{ cos_first_delivery_to_pmo_responsible | default("") }} | {{ cos_first_delivery_to_pmo_due_date | default("") }} | {{ cos_first_delivery_to_pmo_comments | default("") }} |

---

## 2.4 Purchasing / 采购

| Departments | Y/N |  Description  | Responsible | Due date | Status / Comments |
|---|---|---|---|---|---|
| Purchasing | {{ purchasing_check_yn | default("N" )}} | Check sample orders which affected: material order of purchasing parts | {{ purchasing_check_responsible | default("") }} | {{ purchasing_check_due_date | default("") }} | {{ purchasing_check_comments | default("") }} |
| Purchasing | {{ purchasing_internal_departments_requirements_yn | default("N" )}} | Inform internal related departments(COS,MFE,MOEx)with following requirements.:Yellow sticker, delivery quantities and date, PN No. and name,change description… | {{ purchasing_internal_departments_requirements_responsible | default("") }} | {{ purchasing_internal_departments_requirements_due_date | default("") }} | {{ purchasing_internal_departments_requirements_comments | default("") }} |
| Purchasing | {{ purchasing_incoming_inspection_plan_update_yn}} | Update incoming inspection plan | {{ purchasing_incoming_inspection_plan_update_responsible | default("") }} | {{ purchasing_incoming_inspection_plan_update_due_date | default("") }} | {{ purchasing_incoming_inspection_plan_update_comments | default("") }} |

---

## 2.5 Quality / 质量

| Departments | Y/N |  Description  | Responsible | Due date | Status / Comments |
|---|---|---|---|---|---|
| Quality | {{ quality_testing_program_update_yn | default("N" )}} | Update testing programe on testing equipmen | {{ quality_testing_program_update_responsible | default("") }} | {{ quality_testing_program_update_due_date | default("") }} | {{ quality_testing_program_update_comments | default("") }} |
| Quality | {{ quality_ckd_inspection_plan_update_yn | default("N" )}} | Update inspection plan for CKD parts | {{ quality_ckd_inspection_plan_update_responsible | default("") }} | {{ quality_ckd_inspection_plan_update_due_date | default("") }} | {{ quality_ckd_inspection_plan_update_comments | default("") }} |


---

## 2.6 CPjM / LOP / PMO / 客户项目与订单


| Departments | Y/N |  Description  | Responsible | Due date | Status / Comments |
|---|---|---|---|---|---|
| CPjM | {{cpjm_offer_drawing_tcd_customer_yn | default("N") }} | Distribute the Offer drawing, TCD to customer  | {{ cpjm_offer_drawing_tcd_customer_responsible | default("") }} | {{ cpjm_offer_drawing_tcd_customer_due_date | default("") }} |
{{ cpjm_offer_drawing_tcd_customer_comments | default("") }} |
| LOP | {{lop_10_digit_material_order_check_yn | default("N") }} | Check 10 digit material order  | {{ lop_10_digit_material_order_check_responsible | default("") }} | {{ lop_10_digit_material_order_check_due_date | default("") }} |
{{ lop_10_digit_material_order_check_comments | default("") }} |
{{ cpjm_offer_drawing_tcd_customer_comments | default("") }} |
| PMO | {{pmo_customer_order_sample_orders_yn | default("N") }} | Check sample orders affected: customer order | {{ pmo_customer_order_sample_orders_responsible | default("") }} | {{ pmo_customer_order_sample_orders_due_date | default("") }} |
{{ pmo_customer_order_sample_orders_comments | default("") }} |
| PMO | {{pmo_customer_first_delivery_information_yn | default("N") }} | Inform Customer the first delivery information | {{ pmo_customer_first_delivery_information_responsible | default("") }} | {{ pmo_customer_first_delivery_information_due_date | default("") }} |
{{ pmo_customer_first_delivery_information_comments | default("") }} |

| Others(e.g. actions in HW, SW) | {{Others_yn | default("N") }} |  | {{ Others_responsible | default("") }} | {{ Others_due_date | default("") }} |
{{ Others_comments | default("") }} |
---

---

# Step 6.2 Implementation Date / 执行日期

| Field / 字段 | Content / 内容 |
|---|---|
| Planned Implementation Date / 变更计划执行日期 | {{ planned_implementation_date | default("") }} |

---

# Step 7 Implementation Approval / Suggested Approvers 


| Development / 研发 | Purchasing / 采购 | TEF / 工艺 | COS / 样品 | Quality / 质量 | CPjM / 客户项目 | MOEx / 生产 | LOG / 物流 |
|---|---|---|---|---|---|---|---|
| {{ approval_development_person | default("") }} | {{ approval_purchasing_person | default("") }} | {{ approval_mfe_person | default("") }} | {{ approval_cos_person | default("") }} | {{ approval_quality_person | default("") }} | {{ approval_cpjm_person | default("") }} | {{ approval_moex_person | default("") }} | {{ approval_log_person | default("") }} |

{% if approval_other_person %}
| Other / 其他 |
|---|
| {{ approval_other_person }} |
{% endif %}

{% if approval_note %}
Approval Note / 审批说明：

{{ approval_note }}
{% endif %}