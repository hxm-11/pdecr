# PD-ECR Execution Workflow MVP Design

## Goal

Build PD-ECR as a collaborative workflow tool, not only an AI generation tool.
The MVP workflow is:

`draft -> generated -> department_alignment -> execution_assignment -> assignee_confirmation -> execution_in_progress -> leader_review -> approved`

If a leader requests changes, the case moves to `changes_requested` and the
assigned employee updates the execution result before resubmitting for review.

## Product Flow

1. The creator or PD-ECR manager fills `change-description`.
2. The AI generates `impact-analysis`, `validation-plan`, and `implementation-plan`.
3. The implementation checklist always shows every template row. AI only
   suggests `Y`, `N`, and optional reasoning.
4. The creator selects the involved departments from the change description and
   generated impact analysis.
5. The selected departments can see the change package and discuss ownership
   offline. The system does not force an online department nomination in the
   MVP.
6. After offline alignment, the creator or PD-ECR manager assigns each required
   `Y` checklist row to the responsible employee, department, and due date.
7. Assigned employees see their own review/execution tasks in a "My Tasks" view.
8. The responsible employee reviews the change information and confirms that
   they accept the assignment before execution starts.
9. Employees perform the work and fill the execution result page:
   - completion status
   - result note
   - optional evidence note
   - completed date
10. When all required execution tasks are completed, the case enters leader review.
11. Department leaders review the completed execution results for their
   departments and approve or request changes.
12. When all required leaders approve, the case becomes `approved`.
13. Only approved cases can be exported as a formal completed PD-ECR package.

## Roles

- `pd_ecr_manager`: creates cases, generates AI modules, assigns execution
  tasks, submits workflow, can see all cases.
- `department_member`: can see changes for their involved department and edits
  only execution tasks assigned to them.
- `department_leader`: reviews completed execution tasks for their department.
- `admin` or `is_superuser`: manages users and can perform fallback operations.

Existing user fields support this MVP:

- `User.department`
- `User.pd_ecr_role`
- `User.is_superuser`

## Case Statuses

Use these statuses for the execution workflow:

- `draft`: change description is being edited.
- `generated`: AI-generated modules are available for review.
- `department_alignment`: involved departments can see the change package and
  align offline on ownership.
- `execution_assignment`: implementation checklist `Y` rows are being assigned.
- `assignee_confirmation`: assigned employees are reviewing and confirming their
  responsibilities before execution.
- `execution_in_progress`: assigned employees are filling execution results.
- `leader_review`: all execution results are complete; leaders are reviewing.
- `changes_requested`: one or more leaders requested updates.
- `approved`: all required leaders approved.
- `closed`: optional post-MVP archival state.

The older `department_confirmation` status should be treated as legacy for this
new flow. Existing service names may be refactored or adapted, but the product
language should say execution task, execution result, and leader review.

## Core Data Model

The MVP can reuse existing tables with narrowed semantics:

- `PdEcrCase`: one workflow case.
- `PdEcrModule`: persisted module content for the four current modules.
- `PdEcrDepartmentTask`: should become or be replaced by execution tasks.
- `PdEcrLeaderReviewTask`: leader approval tasks after execution completion.
- `PdEcrActivity`: audit trail for submission, completion, approval, and return.
- `PdEcrWorkflowNotification`: optional notification record.

Recommended execution task fields:

- `case_id`
- `checklist_row_id`
- `department`
- `description`
- `assignee_id`
- `assignee_email`
- `assignee_name`
- `status`: `pending_confirmation`, `confirmed`, `in_progress`, `completed`, `changes_requested`
- `due_date`
- `execution_result`
- `execution_note`
- `evidence_note`
- `completed_by_id`
- `completed_at`
- `review_comment`

Recommended department visibility fields:

- `case_id`
- `department`
- `visible_to_department`: `true`
- `published_at`
- `published_by_id`

If reusing `PdEcrDepartmentTask`, map fields as:

- `impact_result` -> `execution_result`
- `impact_remark` -> `execution_note`
- `action_required` -> `evidence_note` or follow-up action

For clarity and future maintenance, a new `PdEcrExecutionTask` model is
preferred if the migration cost is acceptable.

## Backend API Contract

The workflow MVP should expose these stable endpoints:

- `GET /api/v1/pd-ecr/cases/{case_id}/workflow`
  Returns case status, execution tasks, leader review tasks, and current user
  permissions.

- `POST /api/v1/pd-ecr/cases/{case_id}/workflow/publish-departments`
  Publishes the generated change package to selected departments for offline
  ownership alignment. Allowed for creator, `pd_ecr_manager`, or superuser.

- `POST /api/v1/pd-ecr/cases/{case_id}/workflow/assign-execution`
  Creates execution tasks from selected implementation checklist rows.
  Allowed for `pd_ecr_manager`, creator, or superuser.

- `POST /api/v1/pd-ecr/workflow/execution-tasks/{task_id}/confirm-assignment`
  Confirms that the assigned employee reviewed the change information and
  accepts responsibility before execution starts. Allowed for the assignee,
  manager, or superuser.

- `POST /api/v1/pd-ecr/workflow/execution-tasks/{task_id}/complete`
  Saves employee execution result and marks the task completed.
  Allowed for the assignee, department leader, manager, or superuser.

- `POST /api/v1/pd-ecr/workflow/execution-tasks/{task_id}/request-changes`
  Sends an execution task back to the assignee.
  Allowed for department leader, manager, or superuser.

- `POST /api/v1/pd-ecr/workflow/leader-tasks/{task_id}/review`
  Approves or requests changes for a department's completed execution package.
  Allowed for assigned leader, manager, or superuser.

## Frontend Views

### Case Dashboard

Shows all PD-ECR cases with status, owner, customer project, product, update
time, and next action.

### Four-Module Case Detail

The existing four modules remain the main work surface:

- `change-description`
- `impact-analysis`
- `validation-plan`
- `implementation-plan`

The implementation checklist should include assignment controls for rows marked
`Y`.

### Department Alignment Panel

Visible after the creator selects involved departments. It shows the generated
change package to members and leaders in those departments so they can review
the information and align ownership offline. In the MVP, this panel is mostly a
visibility and status surface; final assignment is still done by the creator or
PD-ECR manager.

### Execution Assignment Panel

Visible to manager/creator after department alignment. It lists all checklist
rows marked `Y` and requires:

- assignee
- department
- due date

Submission is blocked until all required rows have assignees.

### My Tasks

Employees see assigned execution tasks. Each task first opens an assignment
confirmation view. After confirmation, the task opens an execution result form
that writes back to the workflow state.

### Leader Review Panel

Leaders see completed execution tasks for their department, source modules, and
employee result notes. They can approve or request changes.

## Permissions

The frontend should hide unavailable actions, but the backend must enforce all
permission rules.

- A department member can only complete tasks assigned to them.
- A department member or leader can view cases where their department is selected
  as involved during department alignment.
- A department leader can review only tasks in their department.
- A PD-ECR manager and superuser can see and operate all workflow actions.
- A creator can assign execution tasks before workflow submission.

## RAG Boundary

RAG assists content creation and checklist suggestions only. It must not
automatically approve workflow actions.

AI may generate:

- impact analysis suggestions
- validation plan suggestions
- implementation checklist `Y` or `N`
- optional rationale for checklist decisions

Human users must provide:

- involved department selection
- offline ownership alignment
- final execution assignment
- assignee responsibility confirmation
- execution results
- leader approval decisions

## MVP Exclusions

Defer these until after the workflow loop is working:

- Outlook or enterprise notification integration
- digital signature compliance
- attachment evidence upload as a hard requirement
- multi-level executive approval
- SLA escalation
- formal audit export

## Acceptance Criteria

- A manager can generate the four-module PD-ECR package from Change Description.
- The implementation checklist keeps all rows and only uses AI for `Y` or `N`.
- The creator can publish the generated change package to involved departments.
- Members and leaders of involved departments can see the change information.
- After offline department alignment, the creator can assign all required `Y`
  checklist rows to responsible employees.
- An assigned employee can review the change information and confirm the
  assignment before execution.
- An employee can complete the execution result only after confirming the
  assignment.
- The case enters leader review only after all required execution tasks are completed.
- A leader can approve or request changes for their department.
- A rejected or changes-requested task returns to the assigned employee.
- The case becomes `approved` only after all required leaders approve.
- Backend tests cover status transitions and permission checks.
- Frontend tests cover assignment, employee completion, and leader approval paths.
