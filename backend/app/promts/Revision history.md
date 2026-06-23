# Revision History / 版本变更记录 Converted Markdown Template

用途：将 PD-ECR Excel 首页中的版本变更记录表转换为 AI 可填写的 Markdown 结构。  
AI 根据用户输入和历史 PD-ECR 知识库输出 JSON；Python 再把 JSON 替换回 Excel 中相同字段名的占位符。

---

# Revision History / 版本变更记录

| Nr. | Change content | Version | Date | Editor |
|---|---|---|---|---|
| `{{revision_1_nr}}` | `{{revision_1_change_content}}` | `{{revision_1_version}}` | `{{revision_1_date}}` | `{{revision_1_editor}}` |
| `{{revision_2_nr}}` | `{{revision_2_change_content}}` | `{{revision_2_version}}` | `{{revision_2_date}}` | `{{revision_2_editor}}` |

---

# Field Rules / 字段规则

| Field | Placeholder | Rule |
|---|---|---|
| Revision 1 No. | `{{revision_1_nr}}` | 固定为 `1` |
| Revision 1 Change content | `{{revision_1_change_content}}` | 本次 PD-ECR 的主要变更内容 |
| Revision 1 Version | `{{revision_1_version}}` | 版本号，例如 `V1.0`、`V1.1`、`V2.0` |
| Revision 1 Date | `{{revision_1_date}}` | 日期，格式 `YYYY-MM-DD` |
| Revision 1 Editor | `{{revision_1_editor}}` | 编辑人；如果用户未提供则留空 |
| Revision 2 No. | `{{revision_2_nr}}` | 固定为 `2` |
| Revision 2 Change content | `{{revision_2_change_content}}` | 第二次修订内容；没有则留空 |
| Revision 2 Version | `{{revision_2_version}}` | 第二次修订版本号；没有则留空 |
| Revision 2 Date | `{{revision_2_date}}` | 第二次修订日期；没有则留空 |
| Revision 2 Editor | `{{revision_2_editor}}` | 第二次修订编辑人；没有则留空 |

---

# AI Fill Rules / AI 填写规则

1. `Nr.` 按顺序填写 `1`、`2`、`3`……
2. `Change content` 应简短描述本次 PD-ECR 的主要变更内容。
3. `Version` 使用标准版本格式，例如 `V1.0`、`V1.1`、`V2.0`。
4. `Date` 统一使用 `YYYY-MM-DD`。
5. `Editor` 填写编辑人；如果用户输入和知识库都没有提供，则输出空字符串 `""`。
6. 如果只有一次变更，只填写 revision_1，revision_2 相关字段保持空字符串。
7. 不要输出“未提供”“无法判断”“AI”。

---

# AI JSON Output Schema

AI 必须只输出一个完整 JSON 对象，字段名与下列 schema 完全一致：

```json
{
  "revision_1_nr": "1",
  "revision_1_change_content": "",
  "revision_1_version": "",
  "revision_1_date": "",
  "revision_1_editor": "",
  "revision_2_nr": "2",
  "revision_2_change_content": "",
  "revision_2_version": "",
  "revision_2_date": "",
  "revision_2_editor": ""
}
```
