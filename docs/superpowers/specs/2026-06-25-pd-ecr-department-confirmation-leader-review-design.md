# PD-ECR Department Confirmation and Leader Review Workflow Design

Date: 2026-06-25
Status: Proposed
Scope: PD-ECR V1 MVP workflow enhancement

## Context

The current PD-ECR UI can generate and display modular content, including Impact
Analysis and sign-off fields. However, the actual collaboration flow is still
mostly one directional:

1. The initiator creates or generates PD-ECR content.
2. Users fill confirmation or sign-off fields in the UI.
3. Some confirmation data is stored locally in the frontend.
4. There is no durable workflow state that drives department confirmation,
   leader review, rejection, rework, and final approval.

The codebase already has useful foundations:

- `backend/app/services/pd_ecr_departments.py` defines departments and module
  responsibility mappings.
- `backend/app/services/pd_ecr_notification_service.py` can send and record
  module-related email notifications.
- `backend/app/models.py` already includes PD-ECR case, module, activity, and
  notification models with status and assignee fields.
- `frontend/src/components/PdEcr/PdEcrModuleAccordion.tsx` has an approval panel,
  but the panel is currently local UI behavior rather than a backend-driven
  workflow.

This design keeps the MVP lightweight: each affected department needs only one
person to confirm. After every required department has confirmed, the system
notifies the relevant leader or result sign-off person for review and signature.

## Goals

- Let the initiator select affected departments during PD-ECR creation or Impact
  Analysis.
- Create one durable confirmation task per affected department.
- Notify the responsible person for each department by email.
- Allow one assignee per department to fill impact comments and confirm.
- Automatically start leader review after all department confirmations complete.
- Notify leader reviewers by email.
- Let leaders approve, reject, or request changes.
- Keep a visible workflow status and audit trail in the frontend.
- Reuse existing PD-ECR routes, models, department definitions, and notification
  service where possible.

## Non-Goals

- No full BPM/workflow engine.
- No multi-person approval inside a single department for the first version.
- No complex delegation, transfer, countersign, or conditional routing.
- No legally binding e-signature requirement in MVP.
- No production approval claim; this remains a local MVP workflow.

## Recommended Approach

Use a lightweight backend-driven workflow with two stages:

1. Department Confirmation
2. Leader Review and Sign-off

The frontend should no longer treat Impact Analysis confirmation as local-only
form state. It should read and update backend tasks. The backend becomes the
source of truth for current status, assignees, timestamps, comments, and email
notification results.

## Workflow State Model

### Case Status

PD-ECR case status should move through these values:

- `draft`: initiator is still editing the PD-ECR.
- `department_confirmation`: affected departments are confirming impact.
- `leader_review`: department confirmation is complete and leaders are reviewing.
- `changes_requested`: at least one department or leader requested changes.
- `approved`: all required leader reviews are approved.
- `closed`: final completed state after export or manual closure.

### Department Confirmation Task Status

Each affected department has one confirmation task:

- `pending`: task created, waiting for department confirmation.
- `confirmed`: department confirmed the impact information.
- `rejected`: department says the PD-ECR cannot proceed as written.
- `changes_requested`: department needs the initiator to revise information.

### Leader Review Task Status

Each required leader/sign-off person has one review task:

- `pending`: waiting for leader review.
- `approved`: leader approved and signed.
- `rejected`: leader rejected the workflow.
- `changes_requested`: leader requests revision before approval.

## Data Model Design

Add focused workflow tables rather than overloading module draft records.

### `PdEcrDepartmentTask`

Fields:

- `id`
- `case_id`
- `department`
- `assignee_id`
- `assignee_email`
- `assignee_name`
- `status`
- `impact_result`
- `impact_remark`
- `action_required`
- `confirmed_by_id`
- `confirmed_by_name`
- `confirmed_at`
- `due_date`
- `created_at`
- `updated_at`

Only one active task should exist per `case_id + department` in the MVP.

### `PdEcrLeaderReviewTask`

Fields:

- `id`
- `case_id`
- `department`
- `reviewer_id`
- `reviewer_email`
- `reviewer_name`
- `status`
- `review_comment`
- `signature_name`
- `reviewed_at`
- `created_at`
- `updated_at`

Leader review tasks are created only after all department tasks reach
`confirmed`.

### Existing Tables To Reuse

- `PdEcrCase.status` remains the top-level status.
- `PdEcrNotification` records email send results.
- `PdEcrActivity` records workflow events.
- `User.department` and `User.pd_ecr_role` identify department members and
  leaders.

## Backend Service Design

Add:

`backend/app/services/pd_ecr_workflow.py`

Responsibilities:

- `submit_for_department_confirmation(case_id, selected_departments, assignees)`
- `confirm_department_task(task_id, payload, current_user)`
- `check_department_stage_complete(case_id)`
- `start_leader_review(case_id)`
- `review_leader_task(task_id, payload, current_user)`
- `check_case_approved(case_id)`
- `request_changes(case_id, target_department, comment)`

This service owns state transitions and notification triggers. Route handlers
should remain thin.

## API Design

Add stable workflow endpoints under the existing PD-ECR router:

- `POST /api/v1/pd-ecr/cases/{case_id}/workflow/submit`
  - Input: affected departments and optional assignee mapping.
  - Effect: create department tasks, set case status to
    `department_confirmation`, send department emails.

- `GET /api/v1/pd-ecr/cases/{case_id}/workflow`
  - Returns case status, department tasks, leader review tasks, notifications,
    and activity summary.

- `POST /api/v1/pd-ecr/workflow/department-tasks/{task_id}/confirm`
  - Input: impact result, remark, action required.
  - Effect: mark task confirmed, check if all departments are complete.

- `POST /api/v1/pd-ecr/workflow/department-tasks/{task_id}/request-changes`
  - Input: comment.
  - Effect: mark task `changes_requested`, set case status
    `changes_requested`, notify initiator.

- `POST /api/v1/pd-ecr/workflow/leader-tasks/{task_id}/review`
  - Input: `approved`, `rejected`, or `changes_requested`, plus comment and
    signature name.
  - Effect: update leader task, possibly approve or reopen the case.

- `POST /api/v1/pd-ecr/cases/{case_id}/workflow/remind`
  - Optional manual reminder endpoint for pending tasks.

## Email Notification Design

Extend `pd_ecr_notification_service.py` with notification types:

- `department_confirmation_request`
- `department_confirmation_completed`
- `leader_review_request`
- `leader_review_approved`
- `leader_review_rejected`
- `changes_requested`

Email content should include:

- PD-ECR case number and title.
- MCR number and customer project when available.
- Current workflow stage.
- Target department or reviewer role.
- Due date if available.
- Link to the workflow detail page.

Email sending should be triggered by workflow service transitions, not by
frontend-only behavior.

## Frontend Design

### Impact Analysis Page

Enhance the current Impact Analysis module to include:

- Affected department selector.
- Submit button: `Submit for Department Confirmation`.
- Department confirmation progress table.
- Per-department status badges.
- Latest comment and confirmed-by fields.
- Clear indication of the current case status.

The existing impact checklist can remain, but durable confirmation data should
come from backend workflow tasks rather than localStorage.

### Department User View

When a department assignee opens the case:

- Show their department task prominently.
- Allow them to fill impact result, remark, and action required.
- Provide actions:
  - `Confirm`
  - `Request changes`

Users should not need to understand the whole workflow to complete their task.

### Leader Review View

When a leader opens the case:

- Show all department confirmation results.
- Show unresolved change requests.
- Provide actions:
  - `Approve and sign`
  - `Reject`
  - `Request changes`

Signature in MVP means storing reviewer identity, signature display name, and
timestamp. It is not a legally binding electronic signature.

### Dashboard

The case dashboard should make workflow state scannable:

- Draft
- Waiting for department confirmation
- Waiting for leader review
- Changes requested
- Approved
- Closed

## Permission Rules

- Initiator can edit draft fields before submission.
- Initiator can submit affected departments for confirmation.
- Assigned department user can confirm only their department task.
- Department leader can confirm tasks for their own department if needed.
- Leader reviewer can approve only their assigned leader review task.
- PD-ECR manager can view and administer all tasks.

## Error Handling

- If a selected department has no assignee or default recipient, block submission
  and show the missing department assignment.
- If email sending fails, still create the task and record notification failure.
  The UI should show that email delivery failed and allow manual resend.
- If a task is already confirmed, repeated confirmation should be rejected unless
  the case is reopened.
- If a leader requests changes, the case returns to `changes_requested`; the
  initiator must resubmit affected department tasks after revision.

## Testing Plan

Backend tests:

- Submitting selected departments creates one task per department.
- Submission sends or records one email notification per task.
- Department confirmation updates task status and timestamp.
- All department tasks confirmed triggers leader review task creation.
- Leader approval updates review task and case status.
- Leader changes requested reopens the case.
- Missing assignee blocks submission with a clear error.
- Email failure records a failed notification without losing the task.

Frontend tests:

- Initiator selects affected departments and submits workflow.
- Department progress table displays pending and confirmed states.
- Department user can confirm only their own task.
- Leader can see all department results before approving.
- Dashboard status updates after department confirmation and leader approval.

## Implementation Sequence

1. Add workflow task models and migration.
2. Add workflow service with state transitions.
3. Extend notification service with workflow email types.
4. Add workflow API endpoints.
5. Replace localStorage-only confirmation behavior with backend workflow calls.
6. Add workflow progress UI to Impact Analysis and dashboard.
7. Add backend and frontend tests.

## Open Decisions

- Department assignee source: choose one default assignee per department from user
  records, or let the initiator select the assignee during submission.
- Leader reviewer source: use `User.pd_ecr_role == "department_leader"` for the
  department, or configure an explicit review matrix.
- Rework behavior: resubmit all department tasks after changes, or only the
  departments affected by the change request.

Recommended MVP defaults:

- Let initiator select or confirm one assignee per affected department.
- Use department leaders as default leader reviewers.
- On changes requested, reopen only the department task that requested changes
  unless the initiator changes affected departments.
