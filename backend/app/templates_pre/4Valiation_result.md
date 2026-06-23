# Step 5 Validation & Trial Run Result / 验证与试运行结果

## 1. Validation Result Summary / 验证结果概要

{{ validation_result_summary | default("请记录本次变更的验证执行结果、OK/NOK 状态、证据文件、责任人及未关闭风险。") }}

---

## 2. Validation Items / 验证项目

| Validation item / 验证项 | Result / 结果 | Evidence / 证据 | Responsible / 负责人 | Date / 日期 | Comments / 备注 |
|---|---|---|---|---|---|
| Function & Performance | {{ function_performance_result | default("TBD") }} | {{ function_performance_evidence | default("") }} | {{ function_performance_responsible | default("") }} | {{ function_performance_date | default("") }} | {{ function_performance_comments | default("") }} |
| Interface / Appearance | {{ interface_result | default("TBD") }} | {{ interface_evidence | default("") }} | {{ interface_responsible | default("") }} | {{ interface_date | default("") }} | {{ interface_comments | default("") }} |
| Reliability / Robustness | {{ reliability_result | default("TBD") }} | {{ reliability_evidence | default("") }} | {{ reliability_responsible | default("") }} | {{ reliability_date | default("") }} | {{ reliability_comments | default("") }} |
| Manufacturing / Assembly / Test | {{ manufacturing_result | default("TBD") }} | {{ manufacturing_evidence | default("") }} | {{ manufacturing_responsible | default("") }} | {{ manufacturing_date | default("") }} | {{ manufacturing_comments | default("") }} |
| Supplier Part | {{ supplier_part_result | default("TBD") }} | {{ supplier_part_evidence | default("") }} | {{ supplier_part_responsible | default("") }} | {{ supplier_part_date | default("") }} | {{ supplier_part_comments | default("") }} |

---

## 3. Open Risks / 未关闭风险

{{ open_risks | default("No open validation risk has been confirmed yet. Please update after trial run review.") }}

---

## 4. Validation Approval / 验证结果确认

| Development / 研发 | Quality / 质量 | Manufacturing / 生产 | Other / 其他 |
|---|---|---|---|
| {{ approval_development_person | default("") }} | {{ approval_quality_person | default("") }} | {{ approval_mfe_person | default("") }} | {{ approval_other_person | default("") }} |
