# Task 1A Report

## Status

Task 1A was partially implemented by a subagent that did not return a report.
The controller inspected the resulting files and ran focused verification.

## Implemented

- Added `pd_ecr_role` to `UserBase`.
- Added module assignment/reminder fields to `PdEcrModuleBase`.
- Added `PdEcrNotificationBase` and `PdEcrNotification`.
- Extended `PdEcrModuleUpdate` with module assignment/reminder fields.
- Added permission helpers in `backend/app/services/pd_ecr_case_service.py`:
  - `user_pd_ecr_role`
  - `can_manage_case`
  - `can_edit_module`
  - `ensure_case_manage_access`
  - `ensure_module_edit_access`
  - `module_permission_flags`
- Updated `update_module` to allow assigned module owners to edit their modules.
- Extended `serialize_module` with assignment/reminder fields and empty default permissions.
- Added `serialize_module_for_user`.
- Added `backend/app/tests/services/test_pd_ecr_permissions_notifications.py` with three focused permission tests.

## TDD Evidence

RED evidence is missing because the interrupted subagent did not write its report.
The controller could not reconstruct the pre-implementation RED state without
reverting the generated changes. This is a process concern for review.

GREEN:

Command:

```powershell
cd backend
..\ .venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Actual command used without the space after `..`:

```powershell
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Result:

```text
collected 3 items
app/tests/services/test_pd_ecr_permissions_notifications.py::test_case_manager_can_assign_but_viewer_cannot PASSED
app/tests/services/test_pd_ecr_permissions_notifications.py::test_module_owner_can_update_assigned_module PASSED
app/tests/services/test_pd_ecr_permissions_notifications.py::test_permission_flags_for_viewer_are_read_only PASSED
3 passed in 0.54s
```

Regression check:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_collaboration.py -v
```

Result:

```text
collected 2 items
app/tests/services/test_pd_ecr_collaboration.py::test_create_case_adds_default_modules PASSED
app/tests/services/test_pd_ecr_collaboration.py::test_update_module_increments_version_and_rejects_stale_update PASSED
2 passed in 0.53s
```

## Files changed

- `backend/app/models.py`
- `backend/app/services/pd_ecr_case_service.py`
- `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`

## Commits

No commit created because this workspace has no `.git` directory and `git` is
not available in PATH.

## Concerns

- RED test output is missing due to interrupted subagent execution.
- Alembic migration from full Task 1 has not been created yet; this was
  intentionally deferred to Task 1B.

## Fix pass after review

Reviewer found two Important authorization gaps:

1. Assigned module owners could change assignment/reminder fields.
2. Historical imported cases were not enforced as read-only by the new helpers.

Fix implemented:

- Added `MODULE_MANAGEMENT_FIELDS`.
- Added `ensure_case_mutable`.
- Updated `can_manage_case`, `can_edit_module`, `ensure_write_access`, and
  `ensure_module_edit_access` to treat historical cases as read-only.
- Updated `update_module` to require case manage permission for assignment and
  reminder-management fields.
- Added tests:
  - `test_module_owner_cannot_change_assignment_due_or_reminder_fields`
  - `test_owner_cannot_update_module_on_historical_case`

Fix RED evidence:

The fix subagent was interrupted before writing its report, so RED output is not
available. The tests existed in the file before controller verification and now
pass against the fixed implementation.

Fix GREEN:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Result:

```text
collected 5 items
app/tests/services/test_pd_ecr_permissions_notifications.py::test_case_manager_can_assign_but_viewer_cannot PASSED
app/tests/services/test_pd_ecr_permissions_notifications.py::test_module_owner_can_update_assigned_module PASSED
app/tests/services/test_pd_ecr_permissions_notifications.py::test_module_owner_cannot_change_assignment_due_or_reminder_fields PASSED
app/tests/services/test_pd_ecr_permissions_notifications.py::test_owner_cannot_update_module_on_historical_case PASSED
app/tests/services/test_pd_ecr_permissions_notifications.py::test_permission_flags_for_viewer_are_read_only PASSED
5 passed in 0.59s
```

Regression check:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_collaboration.py -v
```

Result:

```text
collected 2 items
app/tests/services/test_pd_ecr_collaboration.py::test_create_case_adds_default_modules PASSED
app/tests/services/test_pd_ecr_collaboration.py::test_update_module_increments_version_and_rejects_stale_update PASSED
2 passed in 0.51s
```
