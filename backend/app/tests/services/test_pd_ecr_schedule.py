from app.services.pd_ecr_schedule import compute_signature_schedule


def test_compute_signature_schedule_counts_back_business_days():
    schedule = compute_signature_schedule("2026-07-03")

    assert schedule.target_close_date == "2026-07-03"
    assert schedule.first_signature_date == "2026-06-19"
    assert schedule.second_signature_date == "2026-06-26"
    assert schedule.first_signature_lead_business_days == 10
    assert schedule.second_signature_lead_business_days == 5
