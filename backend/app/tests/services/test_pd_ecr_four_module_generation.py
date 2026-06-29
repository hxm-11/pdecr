from app.services.pd_ecr_four_module_generation import (
    generate_modules_from_change_description,
)


def test_generate_modules_from_change_description_returns_only_generated_modules(monkeypatch):
    def fake_retrieve(input_data, top_k=5):
        assert input_data["customer_project"] == "JP360"
        assert input_data["product_no"] == "F03ZS0000B-04"
        assert input_data["part_no"] == "F03Z20046V-01"
        assert input_data["change_description"] == "Change bolt material and update related process flow"
        return object(), [
            {
                "case_id": "T0006",
                "source_file": "T0006-PD-ECR.md",
                "module_summary": "Historical case required impact review, trial run, BOM check, and implementation checklist.",
            }
        ]

    monkeypatch.setattr(
        "app.services.pd_ecr_four_module_generation.retrieve_similar_cases",
        fake_retrieve,
    )

    result = generate_modules_from_change_description(
        {
            "source": "Design optimization",
            "reason": "Improve assembly reliability",
            "department": "ENG",
            "initiator": "Fan",
            "date": "2026-06-26",
            "product": "F03ZS0000B-04",
            "customer": "JP360",
            "partNumber": "F03Z20046V-01",
            "title": "Bolt material change",
            "changeSummary": "Change bolt material and update related process flow",
            "notChange": "No customer interface change",
            "departments": ["Development", "Quality"],
        },
        top_k=5,
    )

    assert result["generated_module_ids"] == [
        "impact-analysis",
        "validation-plan",
        "implementation-plan",
    ]
    assert [module["id"] for module in result["modules"]] == result["generated_module_ids"]
    assert result["similar_cases"][0]["case_id"] == "T0006"

    impact = result["modules"][0]
    assert impact["data"]["impacts"][0]["yes"] is True
    assert impact["data"]["documents"][0]["yes"] is True
    assert impact["source_cases"] == ["T0006"]
    assert impact["source_files"] == ["T0006-PD-ECR.md"]

    validation_plan = result["modules"][1]
    assert validation_plan["data"]["rows"][0]["label"] == "Try run"
    assert validation_plan["data"]["rows"][0]["checked"] is True

    implementation = result["modules"][2]
    assert implementation["data"]["checklistRows"]
    assert implementation["data"]["checklistRows"][0]["department"] == "Development"
    assert "change-description" not in result["generated_module_ids"]


def test_implementation_generation_preserves_full_import_checklist(monkeypatch):
    def fake_retrieve(input_data, top_k=5):
        return object(), []

    monkeypatch.setattr(
        "app.services.pd_ecr_four_module_generation.retrieve_similar_cases",
        fake_retrieve,
    )

    result = generate_modules_from_change_description(
        {
            "changeSummary": "Update one released drawing for the assembly.",
            "departments": ["Development"],
        },
        top_k=5,
    )

    implementation = next(
        module for module in result["modules"] if module["id"] == "implementation-plan"
    )
    checklist = implementation["data"]["checklistRows"]
    departments = {row["department"] for row in checklist}
    descriptions = {row["description"] for row in checklist}

    assert len(checklist) == 34
    assert departments == {
        "Development",
        "Manufacturing",
        "COS",
        "Purchasing",
        "Quality",
        "CPjM",
        "LOP",
        "PMO",
        "Others",
    }
    assert "Change BOMs & Drawings & Documents in POE system" in descriptions
    assert "Related (Production/Testing) equipment be ready on site" in descriptions
    assert "Check sample orders which affected: Customer order" in descriptions
    assert {row["yn"] for row in checklist}.issubset({"Y", "N", ""})
    assert any(row["yn"] == "Y" for row in checklist)
    assert any(row["yn"] == "N" for row in checklist)


def test_generate_modules_from_change_description_uses_summary_when_reason_missing(monkeypatch):
    captured = {}

    def fake_retrieve(input_data, top_k=5):
        captured.update(input_data)
        return object(), []

    monkeypatch.setattr(
        "app.services.pd_ecr_four_module_generation.retrieve_similar_cases",
        fake_retrieve,
    )

    result = generate_modules_from_change_description(
        {
            "changeSummary": "Only the change description was filled",
            "departments": ["Development"],
        },
        top_k=5,
    )

    assert captured["change_description"] == "Only the change description was filled"
    assert captured["change_reason"] == "Only the change description was filled"
    assert result["generated_module_ids"] == [
        "impact-analysis",
        "validation-plan",
        "implementation-plan",
    ]
