### Task 2: Persist AI generation into editable case/modules

**Files:**
- Create: `backend/app/services/pd_ecr_ai_case_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_ai_case_service.py`

**Interfaces:**
- Consumes:
  - `generate_grounded_draft(data: dict[str, Any], similar_cases: list[dict[str, Any]] | None) -> GeneratedDraft`
  - `create_case(session: Session, case_in: PdEcrCaseCreate, current_user: User) -> PdEcrCase`
- Produces:
  - `create_case_from_ai(session: Session, input_data: dict[str, Any], current_user: User, similar_cases: list[dict[str, Any]] | None = None) -> dict[str, Any]`
  - `POST /api/v1/pd-ecr/cases/generate-from-ai`

- [ ] **Step 1: Write failing persisted-generation tests**

Create `backend/app/tests/services/test_pd_ecr_ai_case_service.py`:

```python
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import PdEcrModule, User
from app.services.pd_ecr_ai_case_service import create_case_from_ai


VALID_INPUT = {
    "dc_no": "PD-ECR-AI-001",
    "mcr_no": "MCR-AI-001",
    "customer_project": "JIM-493",
    "product_no": "F01ZH003G1-00",
    "part_no": "F01ZH003G1-00",
    "change_type": "A Sample release",
    "change_description": "Release detachable and integrated sample parts",
    "change_reason": "Customer request and design optimization",
}


def test_create_case_from_ai_persists_editable_modules():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="ai-owner@example.com", hashed_password="not-used")
        session.add(user)
        session.commit()
        session.refresh(user)

        result = create_case_from_ai(
            session=session,
            input_data=VALID_INPUT,
            current_user=user,
            similar_cases=[],
        )

        assert result["case"]["case_no"] == "PD-ECR-AI-001"
        assert result["case"]["status"] == "draft"
        assert result["redirect_to"].endswith(f"/pd-ecr/cases/{result['case']['id']}")
        modules = session.exec(select(PdEcrModule)).all()
        assert len(modules) >= 6
        change_module = next(module for module in modules if module.module_id == "change-description")
        assert "Release detachable" in (change_module.content_md or "")
        assert change_module.version == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py -v
```

Expected: FAIL because `pd_ecr_ai_case_service.py` does not exist.

- [ ] **Step 3: Create AI case persistence service**

Create `backend/app/services/pd_ecr_ai_case_service.py`:

```python
from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.models import PdEcrCaseCreate, User
from app.services.pd_ecr_case_service import create_case, list_modules, serialize_case, serialize_module
from app.services.pd_ecr_generation import generate_grounded_draft


def _case_no_from_input(input_data: dict[str, Any], draft_id: str) -> str:
    return str(
        input_data.get("dc_no")
        or input_data.get("case_no")
        or input_data.get("mcr_no")
        or draft_id
    )


def _module_payloads_from_draft(draft) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for module in draft.modules:
        module_data = module.model_dump(mode="json")
        modules.append(
            {
                "module_id": module_data["module_id"],
                "title": module_data["title"],
                "content_md": module_data.get("content") or "",
                "content_json": {
                    "summary": module_data.get("summary") or "",
                    "warnings": module_data.get("warnings") or [],
                    "generated_from": "ai",
                    "draft_id": draft.draft_id,
                },
                "source_cases": module_data.get("source_cases") or [],
                "source_files": module_data.get("source_files") or [],
                "needs_human_input": bool(module_data.get("needs_human_input")),
            }
        )
    return modules


def create_case_from_ai(
    *,
    session: Session,
    input_data: dict[str, Any],
    current_user: User,
    similar_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    draft = generate_grounded_draft(input_data, similar_cases=similar_cases)
    case_in = PdEcrCaseCreate(
        case_no=_case_no_from_input(input_data, draft.draft_id),
        title=str(input_data.get("change_description") or input_data.get("title") or "AI generated PD-ECR draft")[:500],
        status="draft",
        source_type="ai_generated",
        is_historical=False,
        dc_no=input_data.get("dc_no"),
        mcr_no=input_data.get("mcr_no"),
        customer_project=input_data.get("customer_project"),
        product_no=input_data.get("product_no"),
        part_no=input_data.get("part_no") or input_data.get("component_no"),
        change_type=input_data.get("change_type"),
        initiator=input_data.get("initiator"),
        modules=_module_payloads_from_draft(draft),
    )
    case = create_case(session=session, case_in=case_in, current_user=current_user)
    modules = list_modules(session=session, case_id=case.id)
    return {
        "case": serialize_case(case),
        "modules": [serialize_module(module) for module in modules],
        "draft_id": draft.draft_id,
        "draft_status": draft.draft_status.value,
        "warnings": [
            warning
            for module in draft.modules
            for warning in module.warnings
        ],
        "redirect_to": f"/pd-ecr/cases/{case.id}",
    }
```

- [ ] **Step 4: Add route payload and endpoint**

In `backend/app/api/routes/pd_ecr.py`, import the service:

```python
from app.services.pd_ecr_ai_case_service import create_case_from_ai
```

Add payload class near `PdEcrGenerateDraftPayload`:

```python
class PdEcrGenerateCasePayload(BaseModel):
    input: Dict[str, Any]
    similar_cases: list[Dict[str, Any]] | None = None
```

Add route after `create_pd_ecr_case`:

```python
@router.post("/cases/generate-from-ai")
def create_pd_ecr_case_from_ai(
    payload: PdEcrGenerateCasePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        return create_case_from_ai(
            session=session,
            input_data=payload.input,
            similar_cases=payload.similar_cases,
            current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"PD-ECR AI case creation failed: {e}",
        )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py backend/app/tests/services/test_pd_ecr_generation.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/pd_ecr_ai_case_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_ai_case_service.py
git commit -m "feat: persist ai generated pd-ecr drafts"
```

---

