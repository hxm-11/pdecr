### Task 5: Assignment endpoint and automatic assignment email

**Files:**
- Modify: `backend/app/services/pd_ecr_case_service.py`
- Modify: `backend/app/api/routes/pd_ecr.py`
- Test: `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`

**Interfaces:**
- Consumes:
  - Task 1 module assignment fields
  - Task 4 notification service
- Produces:
  - `assign_module(...) -> PdEcrModule`
  - `PATCH /cases/{case_id}/modules/{module_id}/assignment`

- [ ] **Step 1: Add failing assignment test**

Append to `backend/app/tests/services/test_pd_ecr_permissions_notifications.py`:

```python
from app.services.pd_ecr_case_service import assign_module


def test_assign_module_updates_owner_and_due_date(session: Session):
    owner = make_user(session, "assign-owner@example.com")
    assignee = make_user(session, "module-owner@example.com", role="module_owner")
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-ASSIGN-001", title="Assign"),
        current_user=owner,
    )

    module = assign_module(
        session=session,
        case=case,
        module_id="implementation-plan",
        assignee_id=assignee.id,
        assignee_email=assignee.email,
        assignee_name=assignee.full_name,
        department="Manufacturing",
        due_date=datetime(2026, 6, 21, tzinfo=timezone.utc),
        reminder_policy={"on_assignment": True, "overdue": True},
        current_user=owner,
    )

    assert module.assignee_id == assignee.id
    assert module.department == "Manufacturing"
    assert module.reminder_policy["on_assignment"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py::test_assign_module_updates_owner_and_due_date -v
```

Expected: FAIL because `assign_module` does not exist.

- [ ] **Step 3: Implement `assign_module`**

In `backend/app/services/pd_ecr_case_service.py`, add:

```python
def assign_module(
    *,
    session: Session,
    case: PdEcrCase,
    module_id: str,
    assignee_id: uuid.UUID | None,
    assignee_email: str | None,
    assignee_name: str | None,
    department: str | None,
    due_date: datetime | None,
    reminder_policy: dict[str, Any] | None,
    current_user: User,
) -> PdEcrModule:
    ensure_case_manage_access(case, current_user)
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == module_id,
        )
    ).first()
    if module is None:
        raise HTTPException(status_code=404, detail="PD-ECR module not found")
    previous = serialize_module(module)
    module.assignee_id = assignee_id
    module.assignee_email = assignee_email
    module.assignee_name = assignee_name
    module.department = department
    module.due_date = due_date
    module.reminder_policy = reminder_policy or {}
    module.updated_at = now_utc()
    module.updated_by_id = current_user.id
    session.add(module)
    write_version(
        session=session,
        case=case,
        entity_type="module",
        entity_id=str(module.id),
        actor_id=current_user.id,
        snapshot=previous,
        diff_metadata={
            "module_id": module.module_id,
            "updated_fields": [
                "assignee_id",
                "assignee_email",
                "assignee_name",
                "department",
                "due_date",
                "reminder_policy",
            ],
        },
    )
    write_activity(
        session=session,
        action="module.assigned",
        case_id=case.id,
        actor_id=current_user.id,
        target_type="module",
        target_id=module.module_id,
        metadata={
            "assignee_id": str(assignee_id) if assignee_id else None,
            "assignee_email": assignee_email,
            "department": department,
        },
    )
    session.commit()
    session.refresh(module)
    return module
```

- [ ] **Step 4: Add route payload and assignment endpoint**

In `backend/app/api/routes/pd_ecr.py`, import:

```python
from datetime import datetime

from app.services.pd_ecr_case_service import assign_module
```

Add payload:

```python
class PdEcrModuleAssignmentPayload(BaseModel):
    assignee_id: uuid.UUID | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    department: str | None = None
    due_date: datetime | None = None
    reminder_policy: Dict[str, Any] | None = None
    send_assignment_email: bool = True
```

Add endpoint:

```python
@router.patch("/cases/{case_id}/modules/{module_id}/assignment")
def assign_pd_ecr_case_module(
    case_id: str,
    module_id: str,
    payload: PdEcrModuleAssignmentPayload,
    session: SessionDep,
    current_user: CurrentUser,
):
    case = get_case_or_404(session=session, case_id=case_id)
    module = assign_module(
        session=session,
        case=case,
        module_id=module_id,
        assignee_id=payload.assignee_id,
        assignee_email=payload.assignee_email,
        assignee_name=payload.assignee_name,
        department=payload.department,
        due_date=payload.due_date,
        reminder_policy=payload.reminder_policy,
        current_user=current_user,
    )
    notification = None
    if payload.send_assignment_email and module.reminder_policy.get("on_assignment", True):
        notification = send_module_assignment_email(session=session, case=case, module=module)
    return {
        "module": serialize_module(module),
        "notification": notification.model_dump(mode="json") if notification else None,
    }
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/app/tests/services/test_pd_ecr_permissions_notifications.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/services/pd_ecr_case_service.py backend/app/api/routes/pd_ecr.py backend/app/tests/services/test_pd_ecr_permissions_notifications.py
git commit -m "feat: add pd-ecr module assignment endpoint"
```

---

