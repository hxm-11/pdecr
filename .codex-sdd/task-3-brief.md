### Task 3: Module regeneration preview and apply flow

**Files:**
- Modify: `backend/app/services/pd_ecr_ai_case_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_ai_case_service.py`

**Interfaces:**
- Consumes:
  - Task 1 permission helpers
  - Task 2 AI case service
- Produces:
  - `regenerate_module_preview(...) -> dict[str, Any]`
  - `apply_generated_module(...) -> dict[str, Any]`
  - `POST /cases/{case_id}/modules/{module_id}/regenerate`
  - `POST /cases/{case_id}/modules/{module_id}/apply-generated`

- [ ] **Step 1: Add failing regeneration tests**

Append to `backend/app/tests/services/test_pd_ecr_ai_case_service.py`:

```python
from app.models import PdEcrModuleUpdate
from app.services.pd_ecr_ai_case_service import apply_generated_module, regenerate_module_preview


def test_regenerate_module_preview_does_not_overwrite_until_applied():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="regen-owner@example.com", hashed_password="not-used")
        session.add(user)
        session.commit()
        session.refresh(user)
        created = create_case_from_ai(
            session=session,
            input_data=VALID_INPUT | {"dc_no": "PD-ECR-AI-REGEN-001"},
            current_user=user,
            similar_cases=[],
        )

        preview = regenerate_module_preview(
            session=session,
            case_id=created["case"]["id"],
            module_id="impact-analysis",
            current_user=user,
            instruction="Focus on manufacturing impact.",
        )
        module = session.exec(
            select(PdEcrModule).where(PdEcrModule.module_id == "impact-analysis")
        ).one()
        before_version = module.version
        assert preview["module_id"] == "impact-analysis"
        assert preview["content_md"]
        assert module.version == before_version

        applied = apply_generated_module(
            session=session,
            case_id=created["case"]["id"],
            module_id="impact-analysis",
            generated=preview,
            expected_version=before_version,
            current_user=user,
        )

        assert applied["module"]["version"] == before_version + 1
        assert applied["module"]["content_md"] == preview["content_md"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py::test_regenerate_module_preview_does_not_overwrite_until_applied -v
```

Expected: FAIL because functions do not exist.

- [ ] **Step 3: Implement preview and apply helpers**

Append to `backend/app/services/pd_ecr_ai_case_service.py`:

```python
from fastapi import HTTPException
from app.models import PdEcrModuleUpdate
from app.services.pd_ecr_case_service import (
    ensure_module_edit_access,
    get_case_or_404,
    update_module,
)


def _module_by_id(session: Session, case, module_id: str):
    for module in list_modules(session=session, case_id=case.id):
        if module.module_id == module_id:
            return module
    raise HTTPException(status_code=404, detail="PD-ECR module not found")


def regenerate_module_preview(
    *,
    session: Session,
    case_id: str,
    module_id: str,
    current_user: User,
    instruction: str | None = None,
) -> dict[str, Any]:
    case = get_case_or_404(session=session, case_id=case_id)
    module = _module_by_id(session, case, module_id)
    ensure_module_edit_access(case, module, current_user)
    input_data = {
        "dc_no": case.dc_no or case.case_no,
        "mcr_no": case.mcr_no or "",
        "customer_project": case.customer_project or "",
        "product_no": case.product_no or "",
        "part_no": case.part_no or "",
        "change_type": case.change_type or "",
        "change_description": case.title or module.content_md or "",
        "change_reason": instruction or module.content_json.get("summary") or "",
    }
    draft = generate_grounded_draft(input_data, similar_cases=[])
    generated_module = next(
        (item for item in draft.modules if item.module_id.value == module_id),
        None,
    )
    if generated_module is None:
        raise HTTPException(status_code=404, detail=f"Generated module not found: {module_id}")
    payload = generated_module.model_dump(mode="json")
    return {
        "case_id": str(case.id),
        "module_id": module_id,
        "title": payload["title"],
        "content_md": payload.get("content") or "",
        "content_json": {
            "summary": payload.get("summary") or "",
            "warnings": payload.get("warnings") or [],
            "generated_from": "module_regenerate",
            "draft_id": draft.draft_id,
            "instruction": instruction or "",
        },
        "source_cases": payload.get("source_cases") or [],
        "source_files": payload.get("source_files") or [],
        "needs_human_input": bool(payload.get("needs_human_input")),
    }


def apply_generated_module(
    *,
    session: Session,
    case_id: str,
    module_id: str,
    generated: dict[str, Any],
    expected_version: int,
    current_user: User,
) -> dict[str, Any]:
    case = get_case_or_404(session=session, case_id=case_id)
    updated = update_module(
        session=session,
        case=case,
        module_id=module_id,
        module_in=PdEcrModuleUpdate(
            title=generated.get("title"),
            content_md=generated.get("content_md") or "",
            content_json=generated.get("content_json") or {},
            source_cases=generated.get("source_cases") or [],
            source_files=generated.get("source_files") or [],
            needs_human_input=bool(generated.get("needs_human_input")),
            expected_version=expected_version,
        ),
        current_user=current_user,
    )
    return {"module": serialize_module(updated)}
```

- [ ] **Step 4: Add route payloads and endpoints**

In `backend/app/api/routes/pd_ecr.py`, import:

```python
from app.services.pd_ecr_ai_case_service import (
    apply_generated_module,
    create_case_from_ai,
    regenerate_module_preview,
)
```

Add payloads:

```python
class PdEcrRegenerateModulePayload(BaseModel):
    instruction: str | None = None


class PdEcrApplyGeneratedModulePayload(BaseModel):
    generated: Dict[str, Any]
    expected_version: int
```

Add endpoints after module patch endpoint:

```python
@router.post("/cases/{case_id}/modules/{module_id}/regenerate")
def regenerate_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrRegenerateModulePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return regenerate_module_preview(
        session=session,
        case_id=case_id,
        module_id=module_id,
        instruction=payload.instruction,
        current_user=current_user,
    )


@router.post("/cases/{case_id}/modules/{module_id}/apply-generated")
def apply_generated_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrApplyGeneratedModulePayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    return apply_generated_module(
        session=session,
        case_id=case_id,
        module_id=module_id,
        generated=payload.generated,
        expected_version=payload.expected_version,
        current_user=current_user,
    )
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_ai_case_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/pd_ecr_ai_case_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_ai_case_service.py
git commit -m "feat: add pd-ecr module regeneration flow"
```

---

