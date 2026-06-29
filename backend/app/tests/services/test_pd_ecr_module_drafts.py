import sqlite3

from app.api.routes import pd_ecr


def test_draft_db_connection_migrates_legacy_table_without_created_at(tmp_path, monkeypatch):
    draft_db = tmp_path / "pd_ecr_module_drafts.sqlite3"
    with sqlite3.connect(draft_db) as connection:
        connection.execute(
            """
            CREATE TABLE pd_ecr_module_draft (
                record_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (record_id, module_id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO pd_ecr_module_draft (record_id, module_id, data, updated_at)
            VALUES ('record-1', 'change-description', '{}', '2026-06-26 10:00:00')
            """
        )

    monkeypatch.setattr(pd_ecr, "DRAFT_DB_PATH", draft_db)

    with pd_ecr.get_draft_db_connection() as connection:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(pd_ecr_module_draft)")
        }
        row = connection.execute(
            """
            SELECT title, created_at, updated_at
            FROM pd_ecr_module_draft
            WHERE record_id = 'record-1' AND module_id = 'change-description'
            """
        ).fetchone()

    assert {"title", "created_at", "updated_at"}.issubset(columns)
    assert row["title"] == ""
    assert row["created_at"] == "2026-06-26 10:00:00"
