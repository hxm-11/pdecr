from pathlib import Path

from fastapi.testclient import TestClient


def test_knowledge_base_status_reports_index_and_staged_counts(client: TestClient):
    response = client.get("/api/v1/pd-ecr/knowledge-base/status")

    assert response.status_code == 200
    payload = response.json()

    assert isinstance(payload["knowledge_files_on_disk"], int)
    assert isinstance(payload["vector_store"], dict)
    assert payload["vector_store"]["index_path"].endswith("pd_ecr.faiss")
    assert payload["vector_store"]["meta_path"].endswith("pd_ecr_meta.pkl")
    assert isinstance(payload["vector_store"]["index_exists"], bool)
    assert isinstance(payload["vector_store"]["meta_exists"], bool)
    assert isinstance(payload["vector_store"]["chunk_files"], int)
    assert isinstance(payload["staged_documents"], dict)
    assert set(payload["staged_documents"]) >= {"pending", "confirmed", "total"}
    assert isinstance(payload["parser_capabilities"], dict)
    assert payload["parser_capabilities"]["xlsx_controls"] is True
    assert "excel_to_markdown" in payload["parser_capabilities"]
