import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select

from app.models import (
    PdEcrCaseCreate,
    PdEcrModule,
    PdEcrModuleUpdate,
    User,
)
from app.services.pd_ecr_case_service import (
    create_case,
    list_modules,
    serialize_case,
    update_module,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


@pytest.fixture()
def user(session: Session):
    user = User(
        email="owner@example.com",
        hashed_password="not-used",
        full_name="Owner",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_create_case_adds_default_modules(session: Session, user: User):
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(
            case_no="PDECR-TEST-001",
            title="Test PD-ECR",
            customer_project="Demo",
            product_no="P-1",
            part_no="Part-1",
            change_type="sample release",
        ),
        current_user=user,
    )

    modules = list_modules(session=session, case_id=case.id)

    assert serialize_case(case)["case_no"] == "PDECR-TEST-001"
    assert len(modules) >= 6
    assert {module.module_id for module in modules} >= {
        "basic-information",
        "change-description",
        "impact-analysis",
        "implementation-plan",
    }


def test_update_module_increments_version_and_rejects_stale_update(
    session: Session, user: User
):
    case = create_case(
        session=session,
        case_in=PdEcrCaseCreate(case_no="PDECR-TEST-002", title="Versioned"),
        current_user=user,
    )
    module = session.exec(
        select(PdEcrModule).where(
            PdEcrModule.case_id == case.id,
            PdEcrModule.module_id == "change-description",
        )
    ).one()
    original_version = module.version

    updated = update_module(
        session=session,
        case=case,
        module_id=module.module_id,
        module_in=PdEcrModuleUpdate(
            content_md="new content",
            expected_version=module.version,
        ),
        current_user=user,
    )

    assert updated.version == original_version + 1
    assert updated.content_md == "new content"

    with pytest.raises(HTTPException) as exc:
        update_module(
            session=session,
            case=case,
            module_id=module.module_id,
            module_in=PdEcrModuleUpdate(
                content_md="stale",
                expected_version=original_version,
            ),
            current_user=user,
        )

    assert exc.value.status_code == 409
