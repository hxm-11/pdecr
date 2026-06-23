# Task 4 Report

## Implemented

- Added `backend/app/services/pd_ecr_notification_service.py`.
- Added notification service functions:
  - `send_module_assignment_email`
  - `send_module_due_soon_email`
  - `send_module_overdue_email`
  - `run_due_reminders`
- Added notification email subject/body builders and notification persistence.
- Added duplicate same-day reminder suppression by `case_id`, `module_id`,
  `notification_type`, and sent date.
- Added route wiring:
  - `POST /cases/{case_id}/modules/{module_id}/send-reminder`
  - `POST /notifications/run-due-reminders`
- Added notification tests in
  `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`.

## TDD Evidence

RED:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Result:

```text
ModuleNotFoundError: No module named 'app.services.pd_ecr_notification_service'
```

This failure was expected because the tests referenced the new notification
service before it existed.

GREEN:

Initial GREEN run found one implementation failure:

```text
FAILED test_due_reminder_scans_due_modules_once_per_day
assert 1 == 0
```

Cause: reminder records used real wall-clock `now_utc()` for `sent_at`, while the
due-reminder scan used an injected scheduler time. Same-day duplicate detection
therefore compared against the wrong date.

Fix: due-soon/overdue reminders now pass the scheduler `current_time` into the
notification record.

Final command:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Result:

```text
collected 7 items
7 passed in 0.60s
```

Regression:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_ai_case_service.py app/tests/services/test_pd_ecr_generation.py -v
```

Result:

```text
collected 4 items
4 passed in 33.28s
```

## Files changed

- `backend/app/services/pd_ecr_notification_service.py`
- `backend/app/api/routes/pd_ecr.py`
- `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`

## Commits

No commit created because this workspace has no `.git` directory and `git` is
not available in PATH.

## Concerns

- Full SMTP delivery is not exercised against a real mail server; tests
  monkeypatch the send function and verify persistence/trigger behavior.

