# Example of Affected Actions / 受影响措施示例

## Affected Domain Discussion / 受影响领域讨论

| Related Domain / 相关领域 | PD-ECR Check Point / 检查点 | Specific Analysis Points / 具体分析点 | Team Discussion Results / 团队讨论结论 |
|---|---|---|---|
| ME | {{ affected_action_me_check_point | default("Step 3.1 Impact analysis / Manufacturing / assembly / testing will be influenced?") }} | {{ affected_action_me_specific_analysis_points | default("需评估本次变更对机械结构、装配过程、制造工艺、测试方式、工装夹具及生产文件的影响。") }} | {{ affected_action_me_discussion_result | default("ME / MFE 需确认变更是否影响现有生产和装配过程，如涉及工装、设备或工艺文件变更，应制定更新和验证计划。") }} |
| HW | {{ affected_action_hw_check_point | default("Step 3.2 Quality Assurance Items / 检查项目") }} | {{ affected_action_hw_specific_analysis_points | default("需评估本次变更对硬件验证、质量保证、可靠性测试、样件验证和测试报告的影响。") }} | {{ affected_action_hw_discussion_result | default("HW / Quality 需确认是否需要 Trial run、CMK、MSA、MAE release、Test report 或其他质量验证项目。") }} |
| SW | {{ affected_action_sw_impact_check_point | default("Step 3.1 Impact analysis / Manufacturing / assembly / testing will be influenced?") }} | {{ affected_action_sw_impact_specific_analysis_points | default("需评估本次变更是否影响软件版本、烧录流程、测试程序、标定数据、条码追溯或库存产品 reflash。") }} | {{ affected_action_sw_impact_discussion_result | default("SW 团队需确认是否触发软件版本更新、reflashing、barcode traceability、calibration alignment 或测试程序更新。") }} |
| SW | {{ affected_action_sw_implementation_check_point | default("Step 6.1 Implementation check list / 导入清单") }} | {{ affected_action_sw_implementation_specific_analysis_points | default("如涉及软件或测试程序变更，需在导入清单中定义版本更新、程序更新、防错验证、导入时间和责任人。") }} | {{ affected_action_sw_implementation_discussion_result | default("SW / MFE / Manufacturing 需确认导入步骤、责任部门、完成时间和验证方式，确保变更后产品可追溯。") }} |
| SW | {{ affected_action_sw_label_traceability_check_point | default("Step 6.1 Implementation check list / Label / Type error prevention and barcode traceability") }} | {{ affected_action_sw_label_traceability_specific_analysis_points | default("需评估标签、型号、防错规则、SW identification code 和 Barcode traceability 是否需要同步更新。") }} | {{ affected_action_sw_label_traceability_discussion_result | default("如变更影响标签或条码规则，应更新防错措施并通知 SW / ME / HW / Calibration / Quality 团队完成确认。") }} |

---

## ME Affected Actions / 机械与工艺受影响措施

| Item / 项目 | Content / 内容 |
|---|---|
| Check Point / 检查点 | {{ affected_action_me_check_point | default("Step 3.1 Impact analysis / Manufacturing / assembly / testing will be influenced?") }} |
| Specific Analysis Points / 具体分析点 | {{ affected_action_me_specific_analysis_points | default("需评估本次变更对装配、加工、测试、工装、设备、产线、工艺文件和制造节拍的影响。") }} |
| Team Discussion Result / 团队讨论结论 | {{ affected_action_me_discussion_result | default("ME / MFE 需确认是否影响当前生产过程。如涉及制造或装配变更，应安排工艺验证、文件更新和现场导入确认。") }} |

---

## HW Affected Actions / 硬件与质量受影响措施

| Item / 项目 | Content / 内容 |
|---|---|
| Check Point / 检查点 | {{ affected_action_hw_check_point | default("Step 3.2 Quality Assurance Items") }} |
| Specific Analysis Points / 具体分析点 | {{ affected_action_hw_specific_analysis_points | default("需评估硬件验证、质量验证、可靠性测试、测试报告、样件确认和释放流程是否受影响。") }} |
| Team Discussion Result / 团队讨论结论 | {{ affected_action_hw_discussion_result | default("HW / Quality 需确认是否需要补充 Trial run、CMK、MSA、MAE release、Test report、PAV release 或其他质量保证项目。") }} |

---

## SW Affected Actions / 软件受影响措施

| Item / 项目 | Content / 内容 |
|---|---|
| Impact Check Point / 影响分析检查点 | {{ affected_action_sw_impact_check_point | default("Step 3.1 Impact analysis / Manufacturing / assembly / testing will be influenced?") }} |
| Impact Analysis Points / 影响分析点 | {{ affected_action_sw_impact_specific_analysis_points | default("需评估软件版本、测试程序、烧录流程、标定数据、库存产品 reflash 和版本追溯是否受影响。") }} |
| Impact Discussion Result / 影响讨论结论 | {{ affected_action_sw_impact_discussion_result | default("SW 团队需确认是否需要软件版本更新、reflashing、calibration alignment、测试程序更新和条码追溯规则调整。") }} |
| Implementation Check Point / 导入清单检查点 | {{ affected_action_sw_implementation_check_point | default("Step 6.1 Implementation check list") }} |
| Implementation Analysis Points / 导入分析点 | {{ affected_action_sw_implementation_specific_analysis_points | default("需明确软件导入动作、程序更新、防错措施、责任部门、完成时间和验证方式。") }} |
| Implementation Discussion Result / 导入讨论结论 | {{ affected_action_sw_implementation_discussion_result | default("SW / MFE / Manufacturing 需共同确认导入计划，确保变更后产品软件版本、测试结果和追溯信息一致。") }} |

---

## Label / Type Error Prevention and Traceability / 标签、型号防错与追溯

| Item / 项目 | Content / 内容 |
|---|---|
| Check Point / 检查点 | {{ affected_action_sw_label_traceability_check_point | default("Step 6.1 Implementation check list / Label, type error prevention and barcode traceability") }} |
| Specific Analysis Points / 具体分析点 | {{ affected_action_sw_label_traceability_specific_analysis_points | default("需确认本次变更是否影响标签信息、型号识别、防错规则、SW identification code 和 Barcode traceability。") }} |
| Team Discussion Result / 团队讨论结论 | {{ affected_action_sw_label_traceability_discussion_result | default("如涉及标签或条码追溯变化，应同步更新相关规则，并由 SW / ME / HW / Calibration / Quality 完成确认。") }} |

---

# Revision History / 版本变更记录

## Revision Information / 版本信息

| Nr. | Change Content / 变更内容 | Version / 版本 | Date / 日期 | Editor / 编辑人 |
|---|---|---|---|---|
| {{ revision_1_nr | default("1") }} | {{ revision_1_change_content | default(change_request.change_proposal) }} | {{ revision_1_version | default("V1.0") }} | {{ revision_1_date | default(basic_info.date) }} | {{ revision_1_editor | default(basic_info.initiator) }} |
{% if revision_2_change_content %}
| {{ revision_2_nr | default("2") }} | {{ revision_2_change_content }} | {{ revision_2_version | default("V1.1") }} | {{ revision_2_date | default("") }} | {{ revision_2_editor | default("") }} |
{% endif %}

---

## Change Summary / 变更概要

| Item / 项目 | Content / 内容 |
|---|---|
| DC No. / 开发更改单号 | {{ basic_info.dc_no | default(dc_no) }} |
| Customer Project / 客户项目 | {{ basic_info.customer_project | default(customer_project) }} |
| Product No. / 产品号 | {{ basic_info.product_no | default(product_no) }} |
| Component No. / 部件号 | {{ basic_info.component_no | default(component_no) }} |
| Reason of Change / 变更原因 | {{ change_request.reason | default(reason) }} |
| Current Design / 当前设计 | {{ change_request.current_design | default(current_design) }} |
| Change Proposal / 更改建议 | {{ change_request.change_proposal | default(change_proposal) }} |
| Remarks / 备注 | {{ change_request.remarks | default(remarks) }} |

---

## Revision Description / 版本说明

{{ revision_description | default("本版本为当前 PD-ECR 工程变更报告的初始版本，用于记录变更内容、影响分析、验证计划及导入计划。") }}


## Summary / 小结

{{ affected_action_summary | default("本页用于汇总 ME / HW / SW 等相关领域针对本次 PD-ECR 的受影响措施、分析点和团队讨论结论。各责任团队需根据影响范围完成文件更新、验证计划、导入措施和追溯确认。") }}