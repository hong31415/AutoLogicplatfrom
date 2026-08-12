from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.database import health as database_health
from app.database import get_run, init_schema, save_run
from app.services.deepseek import generate_sections, refine_sections
from app.services.market_data import provider_health
from app.services.pipeline import build_analysis, build_steps, enrich_analysis_internal_dfa
from app.services.template_dfa_builder import (
    archive_template_dfa_record,
    create_template_dfa_job,
    get_template_dfa_job,
    template_dfa_detail,
    template_dfa_library,
)


def response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    origin = handler.headers.get("Origin", "")
    handler.send_response(status)
    if origin in settings.cors_origins:
        handler.send_header("Access-Control-Allow-Origin", origin)
    else:
        handler.send_header("Access-Control-Allow-Origin", settings.cors_origins[0])
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "SubDFAPlatformBackend/1.0"

    def do_OPTIONS(self) -> None:
        response(self, 204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == f"{settings.api_prefix}/health":
            response(
                self,
                200,
                {
                    "ok": True,
                    "service": "subdfa-report-backend",
                    "model": settings.deepseek_model,
                    "has_api_key": bool(settings.deepseek_api_key),
                    "demo_mode": settings.demo_mode,
                    "embedding": {
                        "has_api_key": bool(settings.embedding_api_key),
                        "model": settings.embedding_model,
                        "base_url": settings.embedding_base_url,
                    },
                    "ifind": {
                        "enabled": settings.ifind_enabled,
                        "has_credentials": bool(settings.ifind_enabled and settings.ifind_username and settings.ifind_password),
                        "mode": "iFinDPy",
                        "status": (
                            "configured_unverified"
                            if settings.ifind_enabled and settings.ifind_username and settings.ifind_password
                            else "disabled" if not settings.ifind_enabled else "not_configured"
                        ),
                    },
                    "data_sources": provider_health(),
                    "database": database_health(),
                },
            )
            return
        run_prefix = f"{settings.api_prefix}/runs/"
        if path.startswith(run_prefix):
            run_id_text = path.removeprefix(run_prefix).strip("/")
            if not run_id_text.isdigit():
                response(self, 400, {"error": "Invalid run id"})
                return
            run = get_run(int(run_id_text))
            if not run:
                response(self, 404, {"error": "History run not found"})
                return
            if isinstance(run.get("analysis"), dict):
                run["analysis"] = enrich_analysis_internal_dfa(run["analysis"])
            response(self, 200, run)
            return
        if path == f"{settings.api_prefix}/template-dfas":
            response(self, 200, {"items": template_dfa_library()})
            return
        job_prefix = f"{settings.api_prefix}/template-dfa-jobs/"
        if path.startswith(job_prefix):
            job_id = path.removeprefix(job_prefix).strip("/")
            job = get_template_dfa_job(job_id)
            if not job:
                response(self, 404, {"error": "Template DFA build job not found"})
                return
            response(self, 200, job)
            return
        template_prefix = f"{settings.api_prefix}/template-dfas/"
        if path.startswith(template_prefix):
            dfa_id = path.removeprefix(template_prefix).strip("/")
            item = template_dfa_detail(dfa_id)
            if not item:
                response(self, 404, {"error": "Uploaded template DFA not found"})
                return
            response(self, 200, item)
            return
        response(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = read_json(self)
            if path == f"{settings.api_prefix}/template-dfa-jobs":
                response(self, 202, create_template_dfa_job(payload))
                return
            if path == f"{settings.api_prefix}/template-dfas/archive":
                dfa_id = str(payload.get("id") or "").strip()
                if not dfa_id:
                    response(self, 400, {"error": "Template DFA id is required"})
                    return
                archived = archive_template_dfa_record(dfa_id)
                response(self, 200 if archived else 404, {"archived": archived, "id": dfa_id})
                return
            query = str(payload.get("query", "")).strip()
            tau = float(payload.get("tau", 0.42))
            if not query:
                response(self, 400, {"error": "query is required"})
                return

            if path == f"{settings.api_prefix}/pipeline/preview":
                analysis = build_analysis(query, tau, payload)
                run_id = save_run(
                    run_type="preview",
                    query=query,
                    payload=payload,
                    analysis=analysis,
                    report_sections=analysis.get("report_sections", []),
                    model_name=settings.deepseek_model,
                )
                response(self, 200, {"analysis": analysis, "run_id": run_id})
                return

            if path == f"{settings.api_prefix}/reports/generate":
                analysis = build_analysis(query, tau, payload)
                sections = analysis["report_sections"]
                ai_used = False
                ai_error = ""
                has_evidence = any(section.get("evidence_verified") for section in sections)
                if bool(payload.get("use_ai", True)) and has_evidence and settings.deepseek_api_key:
                    try:
                        sections = generate_sections(
                            settings=settings,
                            query=query,
                            date=analysis["date"],
                            draft_sections=sections,
                            materials=analysis["materials"],
                            language=str(payload.get("language", "zh")),
                        )
                        ai_used = True
                    except Exception as exc:  # noqa: BLE001 - API returns controlled fallback.
                        ai_error = str(exc)

                verified_sections = sum(1 for section in sections if section.get("evidence_verified"))
                if sections and verified_sections == len(sections):
                    report_status = "complete"
                elif verified_sections:
                    report_status = "partial"
                else:
                    report_status = "blocked"
                analysis["report_sections"] = sections
                analysis["report_status"] = report_status
                analysis.setdefault("evidence_summary", {})["sections_verified"] = verified_sections
                analysis["steps"] = build_steps(analysis, sections)
                persistence_status = "fallback" if ai_error else report_status
                run_id = save_run(
                    run_type="report",
                    query=query,
                    payload=payload,
                    analysis=analysis,
                    report_sections=sections,
                    ai_used=ai_used,
                    model_name=settings.deepseek_model,
                    status=persistence_status,
                    error_text=ai_error,
                )
                response(
                    self,
                    200,
                    {
                        "analysis": analysis,
                        "report_sections": sections,
                        "ai_used": ai_used,
                        "ai_error": ai_error,
                        "report_status": report_status,
                        "evidence_summary": analysis.get("evidence_summary", {}),
                        "model": settings.deepseek_model,
                        "run_id": run_id,
                    },
                )
                return

            if path == f"{settings.api_prefix}/reports/refine":
                instruction = str(payload.get("instruction", "")).strip()
                sections = payload.get("sections", [])
                if not instruction or not isinstance(sections, list) or not sections:
                    response(self, 400, {"error": "instruction and sections are required"})
                    return
                if not settings.deepseek_api_key:
                    response(self, 503, {"error": "报告微调需要配置 DeepSeek API Key"})
                    return
                refined = refine_sections(
                    settings=settings,
                    query=query,
                    date=str(payload.get("date", "")),
                    sections=sections,
                    materials=payload.get("materials", {}) if isinstance(payload.get("materials", {}), dict) else {},
                    instruction=instruction,
                    language=str(payload.get("language", "zh")),
                )
                response(self, 200, {"report_sections": refined, "ai_used": True, "model": settings.deepseek_model})
                return

            response(self, 404, {"error": "Not found"})
        except Exception as exc:  # noqa: BLE001 - keep local API debuggable.
            response(self, 500, {"error": str(exc)})


def run() -> None:
    init_schema()
    httpd = ThreadingHTTPServer((settings.host, settings.port), ApiHandler)
    print(f"SubDFA backend listening on http://{settings.host}:{settings.port}{settings.api_prefix}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
