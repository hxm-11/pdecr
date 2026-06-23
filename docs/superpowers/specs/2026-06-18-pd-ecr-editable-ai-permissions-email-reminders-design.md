# PD-ECR Editable AI Drafts, Permissions, and Email Reminders Design

Date: 2026-06-18

## Context

The current PD-ECR V1 MVP plan focuses on historical case retrieval, AI draft
generation, modular display, and export. The existing implementation already has
several useful foundations:

- FastAPI routes under `/api/v1/pd-ecr`
- React PD-ECR workflow and module views
- `PdEcrCase`, `PdEcrModule`, task, comment, activity, version, and collaboration
  models
- basic user identity fields such as `is_superuser`, `department`,
  `owner_id`, and `created_by_id`
- module update/versioning services
- existing email utility support in `backend/app/utils.py`

The current user-facing problem is that AI one-click generation produces content
that is not the desired editable business object. Generated content is displayed
as a result, but it does not consistently become a persisted PD-ECR case with
editable modules, assigned owners, due dates, permissions, and reminders.

## Goals

1. One-click AI generation creates a complete editable PD-ECR draft.
2. Each generated module can be edited, saved, versioned, and regenerated
   independently.
3. Permission management is introduced early enough to protect edits and module
   assignment.
4. Outlook-related reminder needs are implemented as email reminders to the
   responsible person for each module.
5. Notification delivery is isolated behind a service interface so the first
   implementation can use existing SMTP/email support while preserving a clean
   path to Microsoft Graph `sendMail` later.

## Non-goals

- No Outlook calendar event creation in this phase.
- No full enterprise workflow engine.
- No tenant-wide Microsoft Graph implementation in the first cut unless SMTP is
  unavailable or explicitly preferred.
- No complex custom role administration UI beyond what is needed to assign
  module owners and enforce access.

## Recommended Approach

Use the existing PD-ECR database-backed case/module system as the source of
truth. AI generation should stop being only a frontend/local-storage display
result and should instead create or update persisted `PdEcrCase` and
`PdEcrModule` records.

The first implementation should use:

- persisted editable AI drafts
- module-level regenerate/apply behavior
- lightweight role-based access control plus case/module ownership checks
- module assignment and due dates
- email reminders through a notification service using the existing email
  utility first

This approach gives immediate business value and avoids overbuilding the
Outlook/Graph integration before the PD-ECR workflow is stable.

## Alternatives Considered

### Option A: Keep AI result local and make local fields editable

This is fast but weak. It would make the UI feel editable but would not support
permissions, audit, version history, reminders, or reliable collaboration.

### Option B: Persist complete AI drafts and modules, then add reminders

This is recommended. It aligns generation, editing, permissions, audit, and
reminders around the same database case/module records.

### Option C: Build Microsoft Graph notification first

This makes Outlook integration look polished but does not fix the core issue:
the system still needs persisted editable module ownership before reminders can
be meaningful.

## Functional Design

### One-click generation flow

1. User fills the initial PD-ECR input form.
2. User clicks the AI generation button.
3. Backend validates required PD-ECR fields.
4. Backend retrieves similar historical cases.
5. Backend generates the complete structured draft.
6. Backend creates a new `PdEcrCase` with status `draft`.
7. Backend creates default `PdEcrModule` records from generated modules.
8. Backend assigns module metadata:
   - title
   - module ID
   - generated markdown/content JSON
   - source cases/files
   - human-input warnings
   - initial status
   - optional suggested owner/department/due date
9. Backend records activity and initial version snapshots.
10. Frontend redirects to the persisted case module view.

The frontend may still keep a short-lived local result for navigation fallback,
but the database record is the source of truth.

### Module editing

Each module detail page should support:

- editing content
- saving content to the backend
- preserving `expected_version` to avoid overwriting someone else's edits
- showing save conflicts with the current version
- showing source cases/files and human-input warnings
- marking module status, such as `draft`, `in_progress`, `ready_for_review`,
  `approved`, or `done`

The existing module update endpoint can be reused and extended rather than
creating a parallel editing path.

### Module regeneration

Each module detail page should include a regenerate action:

1. User opens a module.
2. User clicks "Regenerate this module".
3. Backend regenerates only that module using:
   - current case metadata
   - current module content
   - similar case evidence
   - user optional instruction
4. Frontend shows a preview.
5. User chooses:
   - apply generated result to module
   - copy parts manually
   - discard

Applying a regenerated module creates a normal module update and version record.
Regeneration should never silently overwrite existing user edits.

### Permission model

Use lightweight role-based access control with ownership checks.

Initial roles:

- `admin`: all permissions.
- `pd_ecr_manager`: create cases, assign owners, assign module owners, change due
  dates, submit/close cases.
- `case_owner`: edit case metadata, edit modules, assign module owners inside
  their case.
- `module_owner`: edit assigned modules and mark them ready/done.
- `reviewer`: view, comment, and review assigned modules.
- `viewer`: read-only access.
- `integration_service`: internal service identity for sending reminders.

Initial permission rules:

- Admin can do everything.
- Manager can create and manage all PD-ECR cases.
- Case owner can update their case and its modules.
- Module owner can update only assigned modules.
- Reviewer can comment/review but not overwrite module content unless also a
  module owner.
- Viewer can only read.
- Historical imported cases remain read-only unless copied into a new editable
  draft.

Backend checks are mandatory. Frontend button hiding is only a convenience.

### Module assignment

Each module needs assignment fields. These can live directly on `PdEcrModule` or
be modeled as related tasks if the project prefers not to expand the module
table immediately.

Required assignment data:

- assignee user ID, when known
- assignee email
- assignee display name
- department/function
- due date
- reminder policy
- reminder status

Recommended implementation:

- Add module assignment fields directly if the workflow is module-centric.
- Also create/update `PdEcrTask` records when a module assignment becomes a
  trackable action.

### Email reminder design

The requirement is to email the responsible person when certain modules need
timely handling. This is not a calendar reminder.

Triggers:

- A module is assigned to a person.
- A module due date is approaching.
- A module is overdue.
- A module is reassigned.
- A module enters review and needs reviewer attention.

Suggested reminder policy:

- On assignment: send immediately.
- Before due date: send one reminder 1 business day before due date.
- Overdue: send once per business day until module is done, capped by a
  configurable maximum.
- On completion: stop future reminders.

Email content:

- PD-ECR number
- MCR number
- case title
- module title
- current module status
- responsible person
- due date
- action needed
- link to the module detail page
- source/warning summary when useful

Notification records should be persisted so the system knows what was sent and
can avoid duplicate reminders.

### Notification service abstraction

Create a backend notification service with a stable interface:

- `send_module_assignment_email(...)`
- `send_module_due_soon_email(...)`
- `send_module_overdue_email(...)`
- `send_review_request_email(...)`

First delivery adapter:

- existing SMTP/email utility in `backend/app/utils.py`

Future delivery adapter:

- Microsoft Graph `sendMail`

Microsoft Graph `sendMail` notes:

- Use Microsoft Graph only for email sending, not calendar events, for this
  requirement.
- Delegated sending works on behalf of a signed-in user.
- App-only sending can use a service mailbox but requires Microsoft Entra admin
  consent.
- Required Graph permission for mail sending is `Mail.Send`.

## Backend API Design

Extend existing `/api/v1/pd-ecr` endpoints:

- `POST /generate-draft`
  - Keep existing structured draft behavior.
  - Keep this as a non-persisted draft/preview-compatible endpoint for existing
    callers.

- `POST /cases/generate-from-ai`
  - New persisted generation endpoint.
  - Input: normalized PD-ECR form data and optional similar cases.
  - Output: created case, modules, warnings, and redirect target.

- `POST /cases/{case_id}/modules/{module_id}/regenerate`
  - Generate only one module.
  - Return preview content and source metadata.
  - Do not overwrite by default.

- `POST /cases/{case_id}/modules/{module_id}/apply-generated`
  - Apply a preview or generated content to the module.
  - Uses normal version/audit behavior.

- `PATCH /cases/{case_id}/modules/{module_id}/assignment`
  - Assign module owner, email, department, due date, and reminder policy.
  - Triggers assignment email when configured.

- `POST /cases/{case_id}/modules/{module_id}/send-reminder`
  - Manual reminder action for manager/case owner.

- `POST /notifications/run-due-reminders`
  - Internal/admin endpoint or scheduled job entry point.
  - Finds due-soon/overdue modules and sends reminders.

## Data Model Design

Add fields or related models to support permissions and reminders.

Minimal module assignment extension:

- `PdEcrModule.assignee_id`
- `PdEcrModule.assignee_email`
- `PdEcrModule.assignee_name`
- `PdEcrModule.department`
- `PdEcrModule.due_date`
- `PdEcrModule.reminder_policy`
- `PdEcrModule.last_reminded_at`

Notification log model:

- `PdEcrNotification`
  - `id`
  - `case_id`
  - `module_id`
  - `recipient_email`
  - `notification_type`
  - `subject`
  - `status`
  - `provider`
  - `provider_message_id`
  - `error_message`
  - `sent_at`
  - `created_at`

Role/permission model:

- Short term: add role-like values to users or derive from `is_superuser`,
  department, ownership, and module assignment.
- Better medium term:
  - `UserRole`
  - `PdEcrCaseMember`
  - `PdEcrModuleAssignment`

For the first implementation, direct module assignment fields plus a small
permission helper is enough.

## Frontend Design

### Creation workflow

Replace the final static generated-result behavior:

- Generate button calls the new persisted AI generation endpoint.
- On success, navigate to `/pd-ecr/cases/{case_id}` or the existing content view
  backed by the created case.
- Show generated warnings and source references.

### Module detail

Each module page should show:

- editable content fields
- save button
- regenerate button
- generated preview panel
- apply/discard actions
- assignment panel
- due date
- responsible person
- reminder status
- source cases/files
- version/save conflict status

### Permission-aware UI

The UI should ask the backend for current permissions or receive permissions in
case/module responses:

- `can_edit`
- `can_assign`
- `can_regenerate`
- `can_send_reminder`
- `can_review`
- `can_close`

Buttons are hidden or disabled based on these flags, but backend remains the
real enforcement point.

## Scheduling Design

Email reminders need a repeatable job.

Recommended simple implementation:

- Add an admin/internal endpoint that scans for due reminders.
- In local/dev, call it manually or from a lightweight background process.
- In production, run it through a scheduled worker, cron, or platform scheduler.

The job should:

1. Find assigned modules not done/approved/closed.
2. Compare due date with current date.
3. Check notification log to avoid duplicates.
4. Send assignment/due-soon/overdue emails.
5. Store success/failure.
6. Record activity on the PD-ECR case.

## Error Handling

- If AI generation succeeds but persistence fails, return an error and do not
  pretend the draft is editable.
- If module regeneration fails, keep the current module unchanged.
- If email sending fails, persist a failed notification record and show status
  to manager/admin.
- If a recipient has no email, show a missing-recipient warning.
- If two users edit the same module, use version checks and show conflict
  resolution.

## Testing Plan

Backend tests:

- AI generation can create a persisted case and modules.
- Generated modules are editable through existing update endpoints.
- Module regeneration returns a preview without overwriting content.
- Applying generated content increments module version.
- Permission helper allows and denies expected actions.
- Assignment update triggers notification logic.
- Due reminder job sends only eligible reminders.
- Duplicate reminders are not sent in the same reminder window.
- Email failures are recorded.

Frontend tests:

- One-click generation redirects to an editable persisted case.
- Module content can be edited and saved.
- Regenerate preview can be applied or discarded.
- Assignment panel appears for permitted users.
- Read-only users cannot edit or assign.
- Reminder status is visible after manual/send-trigger action.

## Rollout Plan

Phase 1:

- Persist AI-generated drafts into case/module records.
- Make modules editable and versioned from the generated draft.

Phase 2:

- Add module assignment, due dates, and permission checks.
- Add permission flags to API responses and UI.

Phase 3:

- Add SMTP-backed email notification service and notification logs.
- Add assignment, due-soon, and overdue reminder triggers.

Phase 4:

- Add optional Microsoft Graph `sendMail` adapter if the organization prefers
  sending from a Microsoft 365 mailbox.

## Implementation Decision

Module assignment fields should be added directly to `PdEcrModule` in the first
implementation, because the requirement is explicitly module ownership and
timely handling. `PdEcrTask` records can still be created or synchronized later
when the project needs a richer task-management view.
