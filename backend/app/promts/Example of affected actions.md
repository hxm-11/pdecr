# Example of Affected Actions / 受影响措施示例 Converted Markdown Template

用途：将 PD-ECR 中 “Example of affected actions” 页面转换为 AI 可填写的 Markdown 结构。  
AI 根据用户输入和历史 PD-ECR 知识库输出 JSON；Python 再把 JSON 替换回 Excel 中相同字段名的占位符。

---

# Table Structure / 表格结构

| Related domain | PD-ECR check points | Specific analysis points | Team discussion results to be documented |
|---|---|---|---|
| ME | Step 3.1 Impact analysis / 5. Manufacturing/assembly/testing will be influenced? | `{{affected_action_me_specific_analysis_points}}` | `{{affected_action_me_discussion_result}}` |
| HW | Step 3.2 Quality Assurance Items / 检查项目 | `{{affected_action_hw_specific_analysis_points}}` | `{{affected_action_hw_discussion_result}}` |
| SW | Step 3.1 Impact analysis / 5. Manufacturing/assembly/testing will be influenced? | `{{affected_action_sw_impact_specific_analysis_points}}` | `{{affected_action_sw_impact_discussion_result}}` |
| SW | Step 6.1 Implementation check list / 导入清单 | `{{affected_action_sw_implementation_specific_analysis_points}}` | `{{affected_action_sw_implementation_discussion_result}}` |
| SW | Step 6.1 Implementation check list / Mechanical electrical valve design changed, triggered SW version updated. Prevention defined to prevent Label/type error. Add SW identification code into Barcode for ensuring traceability. | `{{affected_action_sw_label_traceability_specific_analysis_points}}` | `{{affected_action_sw_label_traceability_discussion_result}}` |

---

# Field Rules / 字段规则

## 1. ME affected action

| Field | Placeholder | Rule |
|---|---|---|
| PD-ECR check point | `affected_action_me_check_point` | 固定为 Step 3.1 Impact analysis / 5. Manufacturing/assembly/testing will be influenced? |
| Specific analysis points | `{{affected_action_me_specific_analysis_points}}` | 填写 ME 相关具体分析点，例如装配、加工、测试、工装、产线、设备、工艺文件影响 |
| Team discussion results | `{{affected_action_me_discussion_result}}` | 填写团队讨论结论，例如是否影响、需要采取的措施、责任部门、后续验证要求 |

## 2. HW affected action

| Field | Placeholder | Rule |
|---|---|---|
| PD-ECR check point | `affected_action_hw_check_point` | 固定为 Step 3.2 Quality Assurance Items |
| Specific analysis points | `{{affected_action_hw_specific_analysis_points}}` | 填写 HW 相关质量验证、测试、可靠性、样件验证、硬件变更确认点 |
| Team discussion results | `{{affected_action_hw_discussion_result}}` | 填写硬件团队讨论结论，例如是否需要 Trial run、CMK、MSA、MAE release、Test report 等 |

## 3. SW impact affected action

| Field | Placeholder | Rule |
|---|---|---|
| PD-ECR check point | `affected_action_sw_impact_check_point` | 固定为 Step 3.1 Impact analysis / 5. Manufacturing/assembly/testing will be influenced? |
| Specific analysis points | `{{affected_action_sw_impact_specific_analysis_points}}` | 填写 SW 对制造、装配、测试、烧录、版本、追溯的影响分析 |
| Team discussion results | `{{affected_action_sw_impact_discussion_result}}` | 填写 SW 团队讨论结论，例如是否需要 SW version update、reflash、barcode traceability、calibration alignment |

## 4. SW implementation affected action

| Field | Placeholder | Rule |
|---|---|---|
| PD-ECR check point | `affected_action_sw_implementation_check_point` | 固定为 Step 6.1 Implementation check list |
| Specific analysis points | `{{affected_action_sw_implementation_specific_analysis_points}}` | 填写 SW 在导入清单中的执行动作，例如版本更新、程序更新、防错措施、标识变更 |
| Team discussion results | `{{affected_action_sw_implementation_discussion_result}}` | 填写团队讨论结论，例如导入步骤、责任人、完成时间、验证方式 |

## 5. SW label / traceability affected action

| Field | Placeholder | Rule |
|---|---|---|
| PD-ECR check point | `affected_action_sw_label_traceability_check_point` | 固定为机械电磁阀设计变更触发 SW 版本更新、标签/型号防错、Barcode 增加 SW identification code |
| Specific analysis points | `{{affected_action_sw_label_traceability_specific_analysis_points}}` | 填写针对 label/type error、SW identification、barcode traceability 的具体分析 |
| Team discussion results | `{{affected_action_sw_label_traceability_discussion_result}}` | 填写讨论结论，例如是否更新条码规则、是否需要防错验证、是否通知 SW/ME/HW/Calibration 团队 |

---

# AI Fill Rules / AI 填写规则

1. 本页主要用于记录受影响领域 ME / HW / SW 的分析点和团队讨论结论。
2. `PD-ECR check points` 通常为固定参考点，不建议 AI 改写。
3. `Specific analysis points` 应填写具体、可执行、和当前变更相关的分析内容。
4. `Team discussion results to be documented` 应填写团队讨论结论，包括影响判断、措施、责任部门、验证要求。
5. 如果用户输入或知识库没有某个领域的影响信息，则对应字段输出空字符串 `""`。
6. 不要输出“未提供”“无法判断”“AI”。
7. 内容应简短，适合直接写入 Excel 单元格。
8. 如果涉及 SW reflashing、SW version update、barcode traceability、label/type error，应优先补充到 SW 相关字段。
9. 如果涉及加工、装配、测试、工装、设备，应优先补充到 ME 相关字段。
10. 如果涉及硬件验证、质量验证、可靠性测试、测试报告，应优先补充到 HW 相关字段。

---

# AI JSON Output Schema

AI 必须只输出一个完整 JSON 对象，字段名与下列 schema 完全一致：

```json
{
  "affected_action_me_check_point": "Step 3.1 Impact analysis / 5. Manufacturing/assembly/testing will be influenced?",
  "affected_action_me_specific_analysis_points": "",
  "affected_action_me_discussion_result": "",
  "affected_action_hw_check_point": "Step 3.2 Quality Assurance Items",
  "affected_action_hw_specific_analysis_points": "",
  "affected_action_hw_discussion_result": "",
  "affected_action_sw_impact_check_point": "Step 3.1 Impact analysis / 5. Manufacturing/assembly/testing will be influenced?",
  "affected_action_sw_impact_specific_analysis_points": "",
  "affected_action_sw_impact_discussion_result": "",
  "affected_action_sw_implementation_check_point": "Step 6.1 Implementation check list",
  "affected_action_sw_implementation_specific_analysis_points": "",
  "affected_action_sw_implementation_discussion_result": "",
  "affected_action_sw_label_traceability_check_point": "Step 6.1 Implementation check list / Mechanical electrical valve design changed, triggered SW version updated. Prevention defined to prevent Label/type error. Add SW identification code into Barcode for ensuring traceability.",
  "affected_action_sw_label_traceability_specific_analysis_points": "",
  "affected_action_sw_label_traceability_discussion_result": ""
}
```
