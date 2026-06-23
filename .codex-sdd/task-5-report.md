Task 5 report: Assignment endpoint and automatic assignment email

Changes made:
- Added `assign_module(...)` to `backend/app/services/pd_ecr_case_service.py`.
- Added `PdEcrModuleAssignmentPayload` and `PATCH /cases/{case_id}/modules/{module_id}/assignment` to `backend/app/api/routes/pd_ecr.py`.
- Added `test_assign_module_updates_owner_and_due_date` to `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`.

TDD evidence:
- RED: `..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py::test_assign_module_updates_owner_and_due_date -v`
  - Failed during collection with `ImportError: cannot import name 'assign_module'`, as expected before implementation.
- GREEN: `..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py -v`
  - 8 passed.
- Regression: `..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_ai_case_service.py app/tests/services/test_pd_ecr_generation.py -v`
  - 4 passed.

Notes:
- No commit was created because git is unavailable/out of scope for this dispatched task.
