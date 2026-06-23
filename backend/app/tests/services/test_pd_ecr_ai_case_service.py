from sqlmodel import SQLModel, Session, create_engine, select

from app.models import PdEcrModule, PdEcrModuleUpdate, User
from app.services.pd_ecr_ai_case_service import (
    apply_generated_module,
    create_case_from_ai,
    regenerate_module_preview,
)


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


def test_create_case_from_ai_uses_templates_pre_for_template_modules():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="template-owner@example.com", hashed_password="not-used")
        session.add(user)
        session.commit()
        session.refresh(user)
        response = create_case_from_ai(
            session=session,
            input_data={
                **VALID_INPUT,
                "target_close_date": "2026-07-03",
            },
            current_user=user,
            similar_cases=[
                {
                    "rank": 1,
                    "case_id": "PDECR25-084",
                    "source_file": "pilot_design_optimization.md",
                    "module_summary": "Implementation checklist available.",
                    "similarity_score": 0.82,
                }
            ],
        )

        implementation_module = next(
            module
            for module in response["modules"]
            if module["module_id"] == "implementation-plan"
        )

        assert "Step 6 Implementation Plan" in implementation_module["content_md"]
        assert implementation_module["content_json"]["template_file"] == (
            "5implementation_plan.md"
        )
        assert implementation_module["content_json"]["rag_retrieval_results"][0][
            "case_id"
        ] == "PDECR25-084"
        assert "AI prompt" in implementation_module["content_json"]["ai_prompt"]


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
