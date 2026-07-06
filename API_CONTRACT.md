# PD-ECR API 契约（前后端唯一真相）

> **规则**：任何接口/字段/状态变更，必须先改本文件并 @通知对方，再改代码。
> 前端只调用 `frontend/src/client/`（由 `openapi-ts` 从后端 OpenAPI 生成）+ `frontend/src/lib/pdEcrApi.ts` 封装，不手写请求。
> 所有端点前缀：`/api/v1/pd-ecr`（见 `backend/app/api/main.py`，tag=`pd-ecr`）。
> 认证：Bearer Token（沿用模板 `login` 流程，`CurrentUser` 依赖）。
>
> 本文档由代码还原（`backend/app/api/routes/pd_ecr.py`、`services/pd_ecr_workflow.py`、`models.py`），**D1 对齐会议上二人逐条确认后冻结**。

---

## 一、状态枚举（唯一真相 = 后端）

### 1.1 案件状态 `PdEcrCase.status`

| 状态 | 含义 | 进入方式 |
|---|---|---|
| `draft` / `generated` | 草稿 / AI已生成 | 创建 |
| `submitted` | 已提交经理审批 | `submit-for-approval` |
| `department_confirmation` | 部门确认中 | `workflow/submit` |
| `execution_assignment` | 执行分派中 | 部门确认完成 |
| `assignee_confirmation` | 待负责人接受 | `assign-execution` |
| `execution_in_progress` | 执行中 | 负责人确认 |
| `leader_review` | 领导评审中 | 执行完成 |
| `approved` | 审批通过 | `manager-approve` |
| `closed` | 关闭 | 评审通过后 |
| `changes_requested` | 被打回，待修改 | 任一环节 reject/request-changes |
| `cancelled` | 已取消 | — |
| `historical` | 历史参考（只读） | 导入 |

> 前端 `PdEcrWorkflowRules.ts` 的门禁提示必须与此表一致；**最终校验以后端返回的 409/422 为准**。

### 1.2 子任务状态

- 部门任务 `PdEcrDepartmentTask.status`：`pending_confirmation` → `confirmed` / `changes_requested`
- 执行任务 `PdEcrExecutionTask.status`：`pending_assignment` → `in_progress` → `completed` / `changes_requested` / `cancelled`
- 领导评审 `PdEcrLeaderReviewTask.status`：`pending` → `approved` / `changes_requested`
- 经理审批 `PdEcrApprovalTask.status`：`pending` → `approved` / `rejected`

---

## 二、端点清单

> 约定：`{id}` = 案件 UUID 字符串；`{task_id}` = 任务 UUID。成功返回 200，返回体统一含 `case`（序列化案件）或任务对象。错误码见每条备注。

### 2.1 案件基础

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/cases` | 案件列表（支持筛选） |
| GET | `/cases/{id}` | 案件详情 |
| POST | `/cases` | 创建案件 |
| PATCH | `/cases/{id}` | 更新案件（`PdEcrCaseUpdate`） |
| DELETE | `/cases/{id}` | 删除案件 |
| GET | `/cases/{id}/modules` | 模块列表 |
| PATCH | `/cases/{id}/modules/{module_id}` | 更新模块内容 |
| GET | `/cases/{id}/versions` | 版本历史 |
| GET | `/cases/{id}/activity` | 活动日志 |

### 2.2 经理审批链（提交前审批）

**`POST /cases/submit-for-approval`** — 提交案件给经理审批
```jsonc
// Request  (PdEcrSubmitForApprovalPayload)
{
  "title": "string",
  "initiator": "string?",
  "customer_project": "string?",
  "product_no": "string?",
  "part_no": "string?",
  "target_close_date": "ISO8601?",
  "form_data": { },                 // AI生成用表单数据(可含 members/changeSummary 等)
  "approver_email": "string?",      // 不填则从 members owner 或部门 leader 解析
  "approver_name": "string?"
}
// Response 200
{ "case": { }, "approval_task": { "id","status","approver_email","approver_name","flowable_task_id","flowable_task_definition_key" } }
```

**`POST /cases/{id}/manager-approve`** — 经理通过（无 body）
- 前置：`case.status == "submitted"` 且存在 `pending` 审批任务，否则 `409/404`
- 仅指定审批人可操作，否则 `403`
- Response：`{ "case", "message", "notification" }`

**`POST /cases/{id}/manager-reject`** — 经理驳回
```jsonc
{ "rejection_reason": "string?" }   // PdEcrRejectPayload
```

### 2.3 工作流主流转

**`POST /cases/{id}/workflow/submit`** — 提交进入部门确认
```jsonc
{
  "selected_departments": ["string"],           // 受影响部门
  "assignees": { "<dept>": { } } | null         // 可选：预分配
}
```

**`POST /cases/{id}/workflow/publish-departments`** — 下发部门任务
```jsonc
{ "selected_departments": ["string"] }
```

**`POST /cases/{id}/workflow/assign-execution`** — 分派执行任务
```jsonc
{
  "assignments": [{
    "checklist_row_id": "string",
    "department": "string",
    "description": "string",
    "assignee_id": "uuid?",
    "assignee_email": "string",          // 必填
    "assignee_name": "string?",
    "due_date": "ISO8601?"
  }]
}
```

**`GET /cases/{id}/workflow`** — 获取该案件完整工作流状态（含各类子任务）

**`POST /cases/{id}/transition`** — 通用状态跳转（谨慎用）
```jsonc
{ "status": "string" }   // 目标状态
```

### 2.4 我的任务 & 子任务动作

**`GET /workflow/my-tasks`** — 当前用户待办聚合（部门/执行/评审/审批）

**部门任务**
```jsonc
// POST /workflow/department-tasks/{task_id}/confirm
{ "impact_result": "string", "impact_remark": "string?", "action_required": "string?" }

// POST /workflow/department-tasks/{task_id}/request-changes
{ "comment": "string" }
```

**执行任务**
```jsonc
// POST /workflow/execution-tasks/{task_id}/confirm-assignment   (无 body)

// POST /workflow/execution-tasks/{task_id}/complete
{ "execution_result": "string", "execution_note": "string?", "evidence_note": "string?" }

// POST /workflow/execution-tasks/{task_id}/request-changes
{ "comment": "string" }
```

**领导评审**
```jsonc
// POST /workflow/leader-tasks/{task_id}/review
{ "decision": "approved | changes_requested", "review_comment": "string?", "signature_name": "string?" }
```

### 2.5 内容/AI/导出（后端已存在，按需联调）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/cases/generate-from-ai` | AI 生成案件 |
| POST | `/cases/{id}/modules/{module_id}/regenerate` | 重生成模块 |
| POST | `/cases/{id}/modules/{module_id}/apply-generated` | 应用生成结果 |
| POST | `/export` | 导出（`format` 默认 html） |
| POST | `/retrieve` / `/history/search` | RAG 检索 |
| POST | `/cases/upload-file` | 上传附件 |

---

## 三、变更登记（每次改契约在此追加一行）

| 日期 | 改动人 | 端点/字段 | 变更内容 | 已通知 |
|---|---|---|---|---|
| （D1） | — | — | 初版冻结 | — |
