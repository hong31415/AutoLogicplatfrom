from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ModuleNotFoundError:  # Optional for the portable offline demo.
    pymysql = None
    DictCursor = None

from app.config import settings


def is_configured() -> bool:
    if settings.database_driver == "sqlite":
        return settings.database_enabled and bool(settings.sqlite_path)
    return bool(
        settings.database_enabled
        and settings.database_host
        and settings.database_name
        and settings.database_user
    )


@contextmanager
def connection() -> Iterator[Any]:
    if settings.database_driver == "sqlite":
        database_path = Path(settings.sqlite_path).expanduser().resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(database_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return
    if pymysql is None:
        raise RuntimeError("PyMySQL is required when database storage is enabled.")
    conn = pymysql.connect(
        host=settings.database_host,
        port=settings.database_port,
        user=settings.database_user,
        password=settings.database_password,
        database=settings.database_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    if not is_configured():
        return
    if settings.database_driver == "sqlite":
        with connection() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS report_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_type TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    domain_key TEXT,
                    subtree_root TEXT,
                    artifact_mode TEXT,
                    state_count INTEGER NOT NULL DEFAULT 0,
                    edge_count INTEGER NOT NULL DEFAULT 0,
                    report_count INTEGER NOT NULL DEFAULT 0,
                    ai_used INTEGER NOT NULL DEFAULT 0,
                    model_name TEXT,
                    status TEXT NOT NULL DEFAULT 'success',
                    error_text TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_report_runs_created_at ON report_runs(created_at);
                CREATE INDEX IF NOT EXISTS idx_report_runs_domain ON report_runs(domain_key);
                CREATE TABLE IF NOT EXISTS report_run_payloads (
                    run_id INTEGER PRIMARY KEY,
                    request_json TEXT,
                    analysis_json TEXT,
                    report_json TEXT,
                    FOREIGN KEY (run_id) REFERENCES report_runs(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS material_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    node_id TEXT,
                    label TEXT,
                    source_type TEXT,
                    content TEXT,
                    facts_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES report_runs(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_material_records_run_node ON material_records(run_id, node_id);
                """
            )
        return
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS report_runs (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    run_type VARCHAR(32) NOT NULL,
                    query_text TEXT NOT NULL,
                    domain_key VARCHAR(128) NULL,
                    subtree_root VARCHAR(128) NULL,
                    artifact_mode VARCHAR(64) NULL,
                    state_count INT NOT NULL DEFAULT 0,
                    edge_count INT NOT NULL DEFAULT 0,
                    report_count INT NOT NULL DEFAULT 0,
                    ai_used BOOLEAN NOT NULL DEFAULT FALSE,
                    model_name VARCHAR(128) NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'success',
                    error_text TEXT NULL,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    INDEX idx_report_runs_created_at (created_at),
                    INDEX idx_report_runs_domain (domain_key)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS report_run_payloads (
                    run_id BIGINT UNSIGNED NOT NULL,
                    request_json JSON NULL,
                    analysis_json JSON NULL,
                    report_json JSON NULL,
                    PRIMARY KEY (run_id),
                    CONSTRAINT fk_report_run_payloads_run
                        FOREIGN KEY (run_id)
                        REFERENCES report_runs(id)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS material_records (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    run_id BIGINT UNSIGNED NULL,
                    node_id VARCHAR(128) NULL,
                    label VARCHAR(255) NULL,
                    source_type VARCHAR(64) NULL,
                    content MEDIUMTEXT NULL,
                    facts_json JSON NULL,
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    INDEX idx_material_records_run_node (run_id, node_id),
                    CONSTRAINT fk_material_records_run
                        FOREIGN KEY (run_id)
                        REFERENCES report_runs(id)
                        ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                """
            )


def health() -> dict[str, Any]:
    if not is_configured():
        return {
            "enabled": False,
            "connected": False,
            "driver": settings.database_driver,
            "database": settings.database_name,
        }
    try:
        if settings.database_driver == "sqlite":
            with connection() as conn:
                row = conn.execute("SELECT sqlite_version() AS version").fetchone()
            return {
                "enabled": True,
                "connected": True,
                "driver": "sqlite",
                "database": Path(settings.sqlite_path).name,
                "path": str(Path(settings.sqlite_path).expanduser().resolve()),
                "version": row["version"] if row else "",
            }
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS version")
                row = cur.fetchone() or {}
        return {
            "enabled": True,
            "connected": True,
            "driver": "mysql",
            "database": settings.database_name,
            "host": settings.database_host,
            "port": settings.database_port,
            "version": row.get("version", ""),
        }
    except Exception as exc:  # noqa: BLE001 - status is returned to local UI.
        return {
            "enabled": True,
            "connected": False,
            "driver": settings.database_driver,
            "database": settings.database_name,
            "host": settings.database_host,
            "port": settings.database_port,
            "error": str(exc),
        }


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def get_run(run_id: int) -> dict[str, Any] | None:
    if not is_configured():
        return None

    query = """
        SELECT
            r.id, r.run_type, r.query_text, r.domain_key, r.subtree_root,
            r.artifact_mode, r.state_count, r.edge_count, r.report_count,
            r.ai_used, r.model_name, r.status, r.error_text, r.created_at,
            p.request_json, p.analysis_json, p.report_json
        FROM report_runs AS r
        LEFT JOIN report_run_payloads AS p ON p.run_id = r.id
        WHERE r.id = {placeholder}
        LIMIT 1
    """
    with connection() as conn:
        if settings.database_driver == "sqlite":
            result = conn.execute(query.format(placeholder="?"), (run_id,)).fetchone()
            row = dict(result) if result else None
        else:
            with conn.cursor() as cur:
                cur.execute(query.format(placeholder="%s"), (run_id,))
                row = cur.fetchone()

    if not row:
        return None

    analysis = _json_value(row.get("analysis_json"), {})
    report_sections = _json_value(row.get("report_json"), [])
    if analysis and report_sections:
        analysis["report_sections"] = report_sections

    created_at = row.get("created_at")
    return {
        "run_id": int(row["id"]),
        "run_type": row.get("run_type", "report"),
        "query": row.get("query_text", ""),
        "domain": row.get("domain_key", ""),
        "status": row.get("status", "success"),
        "error": row.get("error_text", ""),
        "ai_used": bool(row.get("ai_used")),
        "model": row.get("model_name", ""),
        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
        "request": _json_value(row.get("request_json"), {}),
        "analysis": analysis,
        "report_sections": report_sections,
    }


def save_run(
    *,
    run_type: str,
    query: str,
    payload: dict[str, Any],
    analysis: dict[str, Any],
    report_sections: list[dict[str, Any]] | None = None,
    ai_used: bool = False,
    model_name: str = "",
    status: str = "success",
    error_text: str = "",
) -> int | None:
    if not is_configured():
        return None

    init_schema()
    report_sections = report_sections or analysis.get("report_sections", [])
    runtime = analysis.get("runtime", {})
    subdfa = analysis.get("subdfa", {})
    now = datetime.now()

    if settings.database_driver == "sqlite":
        timestamp = now.isoformat(timespec="seconds")
        with connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO report_runs (
                    run_type, query_text, domain_key, subtree_root, artifact_mode,
                    state_count, edge_count, report_count, ai_used, model_name,
                    status, error_text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_type,
                    query,
                    analysis.get("domain", ""),
                    str(analysis.get("subtree_root", "")),
                    runtime.get("artifact_mode", ""),
                    len(subdfa.get("node_ids", [])),
                    len(subdfa.get("edge_ids", [])),
                    len(report_sections),
                    int(bool(ai_used)),
                    model_name,
                    status,
                    error_text,
                    timestamp,
                ),
            )
            run_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO report_run_payloads (run_id, request_json, analysis_json, report_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    run_id,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    json.dumps(analysis, ensure_ascii=False, default=str),
                    json.dumps(report_sections, ensure_ascii=False, default=str),
                ),
            )
            for node_id, material in (analysis.get("materials") or {}).items():
                conn.execute(
                    """
                    INSERT INTO material_records (
                        run_id, node_id, label, source_type, content, facts_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        node_id,
                        material.get("label", ""),
                        material.get("source_type", material.get("source", "")),
                        material.get("content", ""),
                        json.dumps(material.get("facts", []), ensure_ascii=False, default=str),
                        timestamp,
                    ),
                )
        return run_id

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO report_runs (
                    run_type, query_text, domain_key, subtree_root, artifact_mode,
                    state_count, edge_count, report_count, ai_used, model_name,
                    status, error_text, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_type,
                    query,
                    analysis.get("domain", ""),
                    str(analysis.get("subtree_root", "")),
                    runtime.get("artifact_mode", ""),
                    len(subdfa.get("node_ids", [])),
                    len(subdfa.get("edge_ids", [])),
                    len(report_sections),
                    bool(ai_used),
                    model_name,
                    status,
                    error_text,
                    now,
                ),
            )
            run_id = int(cur.lastrowid)
            cur.execute(
                """
                INSERT INTO report_run_payloads (run_id, request_json, analysis_json, report_json)
                VALUES (%s, CAST(%s AS JSON), CAST(%s AS JSON), CAST(%s AS JSON))
                """,
                (
                    run_id,
                    json.dumps(payload, ensure_ascii=False, default=str),
                    json.dumps(analysis, ensure_ascii=False, default=str),
                    json.dumps(report_sections, ensure_ascii=False, default=str),
                ),
            )
            for node_id, material in (analysis.get("materials") or {}).items():
                cur.execute(
                    """
                    INSERT INTO material_records (
                        run_id, node_id, label, source_type, content, facts_json, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, CAST(%s AS JSON), %s)
                    """,
                    (
                        run_id,
                        node_id,
                        material.get("label", ""),
                        material.get("source_type", material.get("source", "")),
                        material.get("content", ""),
                        json.dumps(material.get("facts", []), ensure_ascii=False, default=str),
                        now,
                    ),
                )
    return run_id
