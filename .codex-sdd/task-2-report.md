# Task 2 Report

## Implemented

- Added `backend/app/tests/services/test_pd_ecr_ai_case_service.py`.
- Added `backend/app/services/pd_ecr_ai_case_service.py`.
- Added `create_case_from_ai(...)`.
- Added V1-to-editable module ID mapping so generated V1 IDs such as
  `change_description` persist into existing editable module IDs such as
  `change-description`.
- Added `PdEcrGenerateCasePayload`.
- Added `POST /api/v1/pd-ecr/cases/generate-from-ai`.

## TDD Evidence

RED:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_ai_case_service.py -v
```

Result:

```text
ModuleNotFoundError: No module named 'app.services.pd_ecr_ai_case_service'
```

This failure was expected because the test referenced the new service before
the service existed.

GREEN:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_ai_case_service.py app/tests/services/test_pd_ecr_generation.py -v
```

Result:

```text
collected 3 items
app/tests/services/test_pd_ecr_ai_case_service.py::test_create_case_from_ai_persists_editable_modules PASSED
app/tests/services/test_pd_ecr_generation.py::test_generate_grounded_draft_has_six_v1_modules_and_sources PASSED
app/tests/services/test_pd_ecr_generation.py::test_export_v1_draft_writes_demo_report_with_sources PASSED
3 passed in 11.92s
```

Regression check:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest app/tests/services/test_pd_ecr_permissions_notifications.py app/tests/services/test_pd_ecr_collaboration.py -v
```

Result:

```text
collected 7 items
7 passed in 0.61s
```

## Files changed

- `backend/app/tests/services/test_pd_ecr_ai_case_service.py`
- `backend/app/services/pd_ecr_ai_case_service.py`
- `backend/app/api/routes/pd_ecr.py`

## Commits

No commit created because this workspace has no `.git` directory and `git` is
not available in PATH.

## Concerns

- The implementation uses an explicit V1-to-existing editable module ID mapping
  to avoid duplicate module rows alongside existing default modules.

