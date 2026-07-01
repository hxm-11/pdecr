# PD-ECR Workflow Contract

**Feature**: PD-ECR V1 MVP

**Purpose**: Define the workflow states, task model, routing rules, deep-link
targets, notification events, and permission boundaries for PD-ECR approval and
execution work.

This contract answers three questions for every PD-ECR case:

- What stage is the case in?
- Who needs to do what next?
- Which module or field should the user open to complete the task?

## 1. Scope

V1 workflow covers:

- Draft preparation
- Manager initial review
- Department impact confirmation
- Implementation task assignment
- Assignee confirmation
- Execution tracking
- Leader review / sign-off
- Rework / supplement information
- Basic approval and closure
- Task deep links and email notification targets

V1 does not cover:

- Full enterprise BPM replacement
- Complex multi-level approval by amount or risk class
- Legal-grade audit trail
- Full Outlook / Feishu integration
- SuperOPL automatic synchronization
- External customer portal workflow

## 2. Case Statuses

| Status | Display Name | Primary Owner | Meaning |
|---|---|---|---|
| `draft` | Draft | Initiator | Case is being prepared and edited. |
| `submitted` | Submitted | Manager approver | Case has been submitted for initial approval. |
| `department_confirmation` | Department Confirmation | Department owners | Impacted departments confirm impact and required actions. |
| `execution_assignment` | Execution Assignment | Initiator / coordinator | Implementation checklist rows need assignees and due dates. |
| `assignee_confirmation` | Assignee Confirmation | Task assignees | Execution owners confirm they accept assigned tasks. |
| `execution_in_progress` | Execution In Progress | Task assignees | Execution tasks are being completed and evidenced. |
| `leader_review` | Leader Review | Department leaders | Leaders review results and sign off. |
| `changes_requested` | Changes Requested | Initiator / task owner | Case or field requires rework before continuing. |
| `approved` | Approved | Coordinator | PD-ECR is approved but not fully archived or closed. |
| `closed` | Closed | Coordinator | PD-ECR is completed, exported, and archived. |
| `cancelled` | Cancelled | Coordinator / admin | Workflow was stopped before completion. |

## 3. Task Buckets

Task buckets drive the My Tasks UI. A bucket is user-facing; a task type is
workflow-facing.

| Bucket | Display Name | Meaning |
|---|---|---|
| `confirmation` | 我的待确认 | User must confirm impact, responsibility, or assignment. |
| `signoff` | 我的待签核 | User must approve, reject, or sign off. |
| `execution` | 我的待执行 | User must perform an implementation task and submit evidence. |
| `supplement` | 我的待补资料 | User must fix missing, rejected, or incomplete information. |
| `overdue` | 超期任务 | Open task whose due date has passed. |
| `returned` | 退回任务 | Task or case was rejected and returned. |

Rules:

- `overdue` is computed from `due_date` and open task status.
- `returned` is computed from `rejected` status or explicit return records.
- A task may appear in both its normal bucket and `overdue`.
- A rejected task should appear in `returned` and usually also in `supplement`.

## 4. Task Types

| Task Type | Bucket | Target Module | Target Field Pattern | Owner Source |
|---|---|---|---|---|
| `manager_approval` | `signoff` | `change-description` | `manager_approval` | Direct manager or selected approver |
| `department_confirmation` | `confirmation` | `impact-analysis` | `department_confirmation.{department}` | Impacted department owner |
| `execution_assignment` | `confirmation` | `implementation-plan` | `checklistRows.{row_id}.assignee` | Initiator or coordinator |
| `assignee_confirmation` | `confirmation` | `implementation-plan` | `checklistRows.{row_id}` | Execution assignee |
| `execution` | `execution` | `implementation-plan` | `checklistRows.{row_id}` | Execution assignee |
| `leader_review` | `signoff` | `validation-plan` | `leader_review.{department}` | Department leader |
| `supplement_info` | `supplement` | Any module | `{module_field_path}` | Responsible field owner |
| `rework_requested` | `supplement` | Any module | `{module_field_path}` | Person assigned by reviewer |
| `close_confirmation` | `signoff` | `approval-signoff-information` | `close_confirmation` | Coordinator or final approver |

## 5. Generic Task Schema

All workflow task APIs should normalize task records to this frontend contract.
Existing backend tables may keep specialized columns, but API responses should
preserve these common fields.

| Field | Required | Description |
|---|---|---|
| `task_id` / `id` | Yes | Stable task identifier. |
| `case_id` | Yes | Linked PD-ECR case ID. |
| `task_type` | Yes | One of the task types in this contract. |
| `task_bucket` | Yes | One of the task buckets in this contract. |
| `status` | Yes | `pending`, `pending_confirmation`, `in_progress`, `completed`, `approved`, `rejected`, `changes_requested`, or `cancelled`. |
| `assignee_id` | Required when assigned | Internal user ID or company employee ID. |
| `assignee_email` | Required for notification | Email recipient for task notification. |
| `assignee_name` | No | Display name. |
| `module_id` | Yes | Target PD-ECR module. |
| `field_path` | Recommended | Target field inside module. |
| `anchor_id` | Recommended | Frontend scroll/highlight anchor. |
| `action_required` | Recommended | Human-readable instruction. |
| `due_date` | Recommended | Due date for SLA and overdue checks. |
| `priority` | No | `low`, `normal`, `high`, or `urgent`. |
| `return_reason` | Required for returned tasks | Reason when rejected or returned. |
| `created_at` | Yes | Task creation time. |
| `updated_at` | Yes | Last update time. |
| `completed_at` | No | Completion time. |

Example:

```json
{
  "id": "task-123",
  "case_id": "case-001",
  "task_type": "department_confirmation",
  "task_bucket": "confirmation",
  "status": "pending",
  "assignee_id": "u-quality-01",
  "assignee_email": "quality.owner@example.com",
  "assignee_name": "Quality Owner",
  "module_id": "impact-analysis",
  "field_path": "department_confirmation.Quality",
  "anchor_id": "impact-department-quality",
  "action_required": "Confirm quality impact and required inspection plan updates.",
  "due_date": "2026-07-10T17:00:00+08:00"
}
```

## 6. State Transitions

| From Status | Trigger | Required Condition | Generated Tasks | To Status |
|---|---|---|---|---|
| `draft` | Submit | Draft required fields complete | `manager_approval` | `submitted` |
| `submitted` | Manager approves | Manager approval task approved | `department_confirmation` tasks | `department_confirmation` |
| `submitted` | Manager rejects | Rejection reason provided | `supplement_info` | `changes_requested` |
| `changes_requested` | Resubmit | All required rework tasks completed | Prior-stage task or `manager_approval` | Prior stage or `submitted` |
| `department_confirmation` | All departments confirmed | All department tasks completed | `execution_assignment` tasks | `execution_assignment` |
| `execution_assignment` | Assign owners | All Y checklist rows have owner and due date | `assignee_confirmation` tasks | `assignee_confirmation` |
| `assignee_confirmation` | All assignees confirm | All assignment confirmations completed | `execution` tasks | `execution_in_progress` |
| `execution_in_progress` | All execution complete | Result and evidence submitted for required tasks | `leader_review` tasks | `leader_review` |
| `leader_review` | All leaders approve | All leader review tasks approved | `close_confirmation` | `approved` |
| `leader_review` | Any leader requests changes | Comment or field target provided | `supplement_info` / `rework_requested` | `changes_requested` |
| `approved` | Close | Final report exported and archive reference recorded | None | `closed` |
| Any open status | Cancel | Cancel reason provided | None | `cancelled` |

## 7. Required Fields By Status

| Status | Required Fields |
|---|---|
| `draft` | `title`, `dc_no`, `mcr_no`, `customer_project`, `product_no`, `part_no`, `change_type`, `change_description`, `change_reason` |
| `submitted` | `manager_approver` |
| `department_confirmation` | `impacted_departments`, department task assignees |
| `execution_assignment` | implementation checklist rows, `assignee`, `due_date` |
| `assignee_confirmation` | assignee confirmation per required execution row |
| `execution_in_progress` | `execution_result`, `execution_note`, `evidence_note` for required tasks |
| `leader_review` | reviewer, signature name, rejection comment when rejected |
| `approved` | approval record, generated report reference |
| `closed` | final report, close date, archive reference |

## 8. Deep Link Contract

Every task should be able to open a precise work location.

Pattern:

```text
/pd-ecr/content/{module_id}?caseId={case_id}&field={field_path}&anchor={anchor_id}&taskId={task_id}
```

Examples:

```text
/pd-ecr/content/impact-analysis?caseId=case-001&field=department_confirmation.Quality&anchor=impact-department-quality&taskId=task-123

/pd-ecr/content/implementation-plan?caseId=case-001&field=checklistRows.row-12&anchor=implementation-task-row-12&taskId=task-456
```

Frontend behavior:

| Input | Behavior |
|---|---|
| `module_id` only | Open module detail. |
| `field_path` present | Show task banner and target field label. |
| `anchor_id` present | Scroll to anchor and highlight it. |
| `taskId` present | Show task action panel when the task is open. |

Anchor rules:

- Use stable `data-pdecr-anchor` for visual blocks.
- Use stable `data-pdecr-field` for specific fields or rows.
- Anchors should not depend on translated labels.
- If the field cannot be found, open the module and show the task banner.

## 9. Notification Events

| Event | When | Recipient | Link Target |
|---|---|---|---|
| `task_created` | New task generated | Task assignee | Task deep link |
| `task_due_soon` | Due date within reminder window | Task assignee | Task deep link |
| `task_overdue` | Due date passed | Task assignee and coordinator | Task deep link |
| `task_completed` | Task completed | Coordinator or prior reviewer | Case workflow page |
| `changes_requested` | Reviewer requests changes | Responsible person | Target field deep link |
| `case_submitted` | Draft submitted | Manager approver | Manager approval task |
| `case_approved` | Final approval completed | Initiator and stakeholders | Approved case |
| `case_closed` | Case archived | Stakeholders | Final report |

Email requirements:

- Subject includes case number and task type.
- Body includes action required, due date, requester, and target module.
- Email link must use the deep-link contract.
- Email should not expose unsupported AI-generated content as approved facts.

## 10. Permission Rules

| Action | Allowed Role |
|---|---|
| Create draft | Initiator |
| Edit draft | Initiator, coordinator, assigned supplement owner |
| Submit draft | Initiator or coordinator |
| Approve manager review | Assigned manager approver |
| Reject manager review | Assigned manager approver |
| Confirm department impact | Assigned department owner |
| Assign execution task | Initiator or coordinator |
| Confirm assignment | Assigned execution owner |
| Complete execution | Assigned execution owner |
| Request execution changes | Coordinator or reviewer |
| Leader sign-off | Assigned department leader |
| Request leader-review changes | Assigned department leader |
| Close case | Coordinator or admin |
| Cancel case | Coordinator or admin |
| View historical cases | Authorized PD-ECR users |

## 11. Personnel Data Dependencies

Company personnel data should provide:

- Stable employee ID
- Display name
- Email
- Active / inactive status
- Department
- Function
- Site / plant
- Manager employee ID

PD-ECR system should maintain or derive:

- `approval_role`
- `approval_scope`
- task delegation
- backup approver
- department owner mapping
- coordinator mapping

Recommended internal tables or views:

```text
person
organization
pd_ecr_role_assignment
pd_ecr_approval_matrix
pd_ecr_delegation
```

## 12. Approval Matrix Inputs

The approval matrix should be able to route by:

- `plant`
- `business_unit`
- `customer_project`
- `product_family`
- `product_no`
- `part_no`
- `change_type`
- `department`
- `risk_level`
- `approval_role`

Minimum V1 routing rules:

- Manager approval: initiator's manager or selected approver.
- Department confirmation: impacted department owner.
- Execution task: manually selected assignee.
- Leader review: leader for each impacted department.
- Final close: coordinator or PD-ECR admin.

## 13. Status Completion Rules

| Status | Completion Rule |
|---|---|
| `draft` | Required draft fields complete. |
| `submitted` | Manager approval task approved. |
| `department_confirmation` | All open department tasks confirmed. |
| `execution_assignment` | All required implementation rows have assignee and due date. |
| `assignee_confirmation` | All assigned execution owners confirm assignment. |
| `execution_in_progress` | All required execution tasks completed with result and evidence. |
| `leader_review` | All required leader tasks approved. |
| `changes_requested` | All supplement / rework tasks completed and resubmitted. |
| `approved` | Final approval package generated. |
| `closed` | Archive reference stored. |

## 14. Open Questions

- Should manager approval always happen before department confirmation?
- Should department confirmation create tasks for all departments or only impacted departments?
- Can a department owner delegate confirmation?
- Can execution tasks be reassigned after assignee confirmation?
- Does leader review require all impacted departments or all fixed departments?
- Should rejected tasks return to the previous state or always to `changes_requested`?
- What SLA should each task type use?
- Should overdue escalation notify only the coordinator or also department leaders?
- Should final approval happen before or after official report export?
- Which fields are legally required for archive in the production version?

## 15. V1 Implementation Notes

Current V1 should prefer additive changes:

- Keep existing task tables and specialized workflow APIs.
- Normalize My Tasks API response to the generic task schema.
- Use task buckets for UI grouping.
- Use module and field deep links for task navigation.
- Keep generated drafts clearly marked as V1 MVP draft content.
- Treat unsupported AI content as requiring human input.

