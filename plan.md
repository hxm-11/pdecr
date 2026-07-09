# PDECR MVP Execution Plan

本计划用于交给 Claude Code 执行。目标是把当前 PDECR 系统推进到一个“能新建、能提交、能审批、能保存附件、能记录签核”的最小可运行版本。

## 总目标

先不接 Flowable，不强依赖 RAG。优先完成一个 service-driven 的本地审批闭环：

1. 统一前后端生命周期状态机。
2. 对齐新建/提交 PDECR 表单校验。
3. 补齐附件后端持久化。
4. 补齐审批/签核记录持久化。
5. 减少前端关键业务数据对 `localStorage` 的依赖。

## 当前判断

前端 `frontend/src/lib/pdEcrApi.ts` 中大部分 API 后端已经有 route。当前主要缺口不是大量接口不存在，而是部分功能仍然停留在前端本地状态：

- 附件只保存了文件名、类型、大小等 metadata，很多没有真实上传和后端绑定。
- 前端状态枚举仍有旧状态，后端已经引入新的 lifecycle status。
- 新建/提交审批字段与后端校验字段没有完全显式对齐。
- 部分 leader signoff、result signers、模块结果确认仍依赖 `localStorage` 或零散 draft。

## Phase 1: 统一生命周期状态机

### 目标

前后端只使用一套 PDECR 生命周期状态，避免状态条、按钮权限、任务流判断分叉。

### 后端状态

以现有后端 canonical lifecycle status 为准：

- `draft`
- `submitted`
- `applicant_confirming`
- `leader_reviewing`
- `task_executing`
- `result_confirming`
- `closed`
- `rejected`
- `cancelled`
- `expired`

后端可以继续兼容历史 alias，例如：

- `approved` -> `task_executing`
- `in_review` -> `leader_reviewing`

### 需要检查/修改的后端文件

- `backend/app/services/pd_ecr_lifecycle_service.py`
- `backend/app/services/pd_ecr_case_service.py`
- `backend/app/services/pd_ecr_approval_service.py`
- `backend/app/api/routes/pd_ecr.py`
- `backend/app/models.py`

### 需要检查/修改的前端文件

- `frontend/src/lib/pdEcrApi.ts`
- `frontend/src/components/PdEcr/PdEcrCaseStatusFlow.tsx`
- `frontend/src/components/PdEcr/pdEcrWorkflowRules.ts`
- 其他引用 `PdEcrCaseStatus` 的组件

### 执行项

1. 搜索前端旧状态：
   - `execution_assignment`
   - `assignee_confirmation`
   - `execution_in_progress`
   - `in_review`
   - `approved`
2. 将前端状态类型改为后端 canonical lifecycle status。
3. 前端优先使用后端返回的：
   - `status`
   - `lifecycle_status`
   - `lifecycle_label`
   - `allowed_next_statuses`
4. 状态条、按钮权限、任务入口统一基于 `lifecycle_status` 判断。
5. 保留兼容层：如果后端返回旧状态，前端可以映射到新状态，但 UI 内部不要继续扩散旧状态。

### 验收标准

- 新建 case 后显示 `draft`。
- 提交审批后显示 `submitted`。
- 审批通过后进入后端定义的下一生命周期状态。
- 前端状态条不出现未知状态。
- 状态相关 TypeScript 类型不再依赖旧 workflow status。

## Phase 2: 对齐新建 PDECR 表单校验

### 目标

用户在前端填写的字段，必须与后端 submit/create 校验字段一致。避免“前端填了，后端认为没填”。

### MVP 必填字段

建议后端和前端统一至少校验以下字段：

- `product`
- `customer`
- `change_title`
- `product_no`
- `change_reason`
- `change_description`
- `affected_departments`

### 需要检查/修改的后端文件

- `backend/app/services/pd_ecr_form_service.py`
- `backend/app/services/pd_ecr_approval_service.py`
- `backend/app/api/routes/pd_ecr.py`
- `backend/app/services/pd_ecr_case_service.py`

### 需要检查/修改的前端文件

- `frontend/src/lib/pdEcrApi.ts`
- `frontend/src/components/PdEcr/PdEcrPlatform.tsx`
- `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`
- 其他提交审批或新建 case 的组件

### 执行项

1. 确认后端 create case 和 submit approval 的 payload schema。
2. 修改前端 `PdEcrSubmitForApprovalPayload`，显式包含必填字段。
3. 不要只把关键字段藏在 `form_data` 里，提交审批时需要一层显式字段。
4. 后端校验失败时返回结构化错误，例如：

```json
{
  "missing_fields": ["product", "change_reason"]
}
```

5. 前端接收 `missing_fields` 并展示具体缺失项。
6. 后端 `GET /api/v1/pd-ecr/meta/new-form` 应返回前端可用的字段定义、必填信息、默认值。

### 验收标准

- 必填字段为空时，前端能明确显示缺哪些字段。
- 必填字段完整时，可以成功提交审批。
- 后端校验逻辑和前端表单必填提示一致。
- 不再出现字段名不一致导致的提交失败。

## Phase 3: 附件后端持久化

### 目标

将当前前端本地附件 metadata 改为真实后端附件。刷新页面后附件不丢失，审批记录可以追溯附件。

### 建议新增/完善接口

```http
POST /api/v1/pd-ecr/cases/{case_id}/attachments
GET /api/v1/pd-ecr/cases/{case_id}/attachments
DELETE /api/v1/pd-ecr/attachments/{attachment_id}
```

可选预览/下载接口：

```http
GET /api/v1/pd-ecr/attachments/{attachment_id}/download
GET /api/v1/pd-ecr/attachments/{attachment_id}/preview
```

### 附件数据结构建议

```json
{
  "id": "attachment-id",
  "case_id": "case-id",
  "module_id": "optional-module-id",
  "section": "before_change",
  "filename": "example.pdf",
  "content_type": "application/pdf",
  "file_size": 12345,
  "storage_path": "backend/app/uploads/pd_ecr/...",
  "uploaded_by": "user-id",
  "uploaded_by_name": "User Name",
  "created_at": "2026-07-07T10:00:00"
}
```

`section` 建议先支持：

- `before_change`
- `after_change`
- `feasibility`
- `execution`
- `result`
- `other`

### 需要检查/修改的后端文件

- `backend/app/models.py`
- `backend/app/api/routes/pd_ecr.py`
- 新增 `backend/app/services/pd_ecr_attachment_service.py`

如已有 `PdEcrAttachment` 模型，优先复用，不重复建表。

### 需要检查/修改的前端文件

- `frontend/src/lib/pdEcrApi.ts`
- `frontend/src/components/PdEcr/PdEcrPlatform.tsx`
- `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
- `frontend/src/components/PdEcr/PdEcrFeasibilityConfirmation.tsx`
- 其他使用 attachment localStorage 的组件

### 执行项

1. 检查后端是否已有 `PdEcrAttachment` 模型。
2. 新增 attachment service，负责：
   - 保存上传文件
   - 写入数据库
   - 查询 case 附件
   - 删除附件记录和本地文件
3. 本地文件先保存到：

```text
backend/app/uploads/pd_ecr/
```

4. 后端 route 接收 `UploadFile` 和 metadata：
   - `module_id`
   - `section`
5. 前端新增 API 方法：
   - `uploadPdEcrAttachment`
   - `listPdEcrAttachments`
   - `deletePdEcrAttachment`
6. 前端把变更前/变更后附件、可行性附件从 `localStorage` 切到后端接口。
7. 保留短期兼容：如果旧 localStorage 里有附件 metadata，可以展示为 legacy/local-only，但不要作为新上传路径。

### 验收标准

- 上传附件后刷新页面仍能看到。
- 附件能按 case 查询。
- 附件能按 section 区分。
- 删除附件后刷新页面不再出现。
- 提交审批时可以关联已上传附件。

## Phase 4: 审批/签核记录持久化

### 目标

审批动作、签核人、签核意见、签核时间必须落后端，不能只存在前端按钮状态或 `localStorage`。

### 建议新增接口

```http
POST /api/v1/pd-ecr/cases/{case_id}/signoffs
GET /api/v1/pd-ecr/cases/{case_id}/signoffs
```

如已有 approval/workflow service，可以集成到现有 service，不必单独暴露太多接口。

### 签核记录结构建议

```json
{
  "id": "signoff-id",
  "case_id": "case-id",
  "step": "manager_approval",
  "action": "approved",
  "operator_id": "user-id",
  "operator_name": "User Name",
  "comment": "approved",
  "created_at": "2026-07-07T10:00:00"
}
```

`step` 建议支持：

- `submit`
- `manager_approval`
- `leader_review`
- `department_confirmation`
- `execution_assignment`
- `execution_completion`
- `result_confirmation`

`action` 建议支持：

- `submitted`
- `approved`
- `rejected`
- `confirmed`
- `requested_changes`
- `completed`

### 需要检查/修改的后端文件

- `backend/app/services/pd_ecr_approval_service.py`
- `backend/app/services/pd_ecr_lifecycle_service.py`
- `backend/app/api/routes/pd_ecr.py`
- `backend/app/models.py`
- 可新增 `backend/app/services/pd_ecr_signoff_service.py`

### 需要检查/修改的前端文件

- `frontend/src/lib/pdEcrApi.ts`
- `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`
- `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`
- `frontend/src/components/PdEcr/PdEcrFeasibilityConfirmation.tsx`
- `frontend/src/components/PdEcr/PdEcrMyTasks.tsx`

### 执行项

1. 检查是否已有 activity/audit/version 表可以复用。
2. 如果没有合适结构，新增轻量 signoff model/service。
3. 在以下动作成功后自动写 signoff：
   - submit approval
   - manager approve
   - manager reject
   - leader review
   - department confirm
   - execution complete
   - result confirm
4. 前端签核区从后端读取 signoffs。
5. 把以下 localStorage 状态逐步替换为后端数据：
   - leader signoff buttons
   - result signers
   - feasibility signing result

### 验收标准

- 每次审批动作都有后端记录。
- 刷新页面后签核结果不丢失。
- 能看到操作人、动作、意见、时间。
- 驳回原因能持久化。

## Phase 5: 清理 localStorage 关键业务状态

### 目标

保留 localStorage 作为临时缓存，但关键业务数据必须以后端为准。

### 需要重点检查的前端组件

- `frontend/src/components/PdEcr/PdEcrContentBlocks.tsx`
- `frontend/src/components/PdEcr/PdEcrCreationWorkflow.tsx`
- `frontend/src/components/PdEcr/PdEcrDraftList.tsx`
- `frontend/src/components/PdEcr/PdEcrExecutionWorkflowPanel.tsx`
- `frontend/src/components/PdEcr/PdEcrFeasibilityConfirmation.tsx`
- `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx`
- `frontend/src/components/PdEcr/PdEcrModuleDetail.tsx`
- `frontend/src/components/PdEcr/PdEcrPlatform.tsx`
- `frontend/src/components/PdEcr/pdEcrState.ts`

### 执行项

1. 搜索：

```bash
rg -n localStorage frontend/src/components/PdEcr
```

2. 分类 localStorage 用途：
   - UI preference: 可以保留
   - temporary draft: 可以短期保留，但需要同步后端
   - approval/signoff/attachment/business result: 必须改成后端
3. 对于 module draft，优先复用已有接口：
   - `GET /api/v1/pd-ecr/module-drafts`
   - `POST /api/v1/pd-ecr/module-drafts`
   - `GET /api/v1/pd-ecr/module-drafts/list`
   - `DELETE /api/v1/pd-ecr/module-drafts`
4. 对于附件，统一走 Phase 3 的 attachment API。
5. 对于签核，统一走 Phase 4 的 signoff/workflow API。

### 验收标准

- 页面刷新后关键业务数据不丢。
- 换浏览器后仍能看到 case 的附件、签核、审批结果。
- `localStorage` 不再作为审批事实来源。

## 推荐执行顺序

1. Phase 1: 统一生命周期状态机。
2. Phase 2: 对齐新建 PDECR 表单校验。
3. Phase 3: 附件后端持久化。
4. Phase 4: 审批/签核记录持久化。
5. Phase 5: 清理关键 localStorage 依赖。

## 建议时间估算

一个人执行，按当前项目状态估算：

- Phase 1: 0.5 - 1 天
- Phase 2: 0.5 - 1 天
- Phase 3: 1 - 2 天
- Phase 4: 1 - 1.5 天
- Phase 5: 0.5 - 1 天

整体预计：

- 快速 MVP: 3 天左右
- 稳妥联调版: 4 - 5 天
- 加测试和历史数据兼容: 1 周左右

## 最小可运行验收清单

完成后至少需要验证以下流程：

1. 创建 PDECR case。
2. 填写必填字段。
3. 上传变更前/变更后附件。
4. 提交审批。
5. 经理审批通过。
6. 生命周期状态正确变化。
7. 签核记录可以查询。
8. 刷新页面后附件、状态、签核记录仍然存在。
9. 删除附件后刷新页面不再出现。
10. 必填字段缺失时前端能显示明确错误。

## Claude Code 执行注意事项

- 不要大规模重构无关代码。
- 优先复用现有 service pattern。
- 后端业务逻辑放 service，route 只做参数解析和调用。
- 前端优先复用 `frontend/src/lib/pdEcrApi.ts` 作为 API 出口。
- 修改状态枚举时要全局搜索旧状态，避免遗漏。
- 若测试环境不可用，至少做静态类型检查或说明无法运行的原因。
- 不要删除现有 mock/localStorage 兼容逻辑，除非已经确认后端替代路径可用。
