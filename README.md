# AutoLogic Studio · Executable Writing Graph Platform

AutoLogic Studio is a bilingual, evidence-driven research report workspace. It builds a query-specific execution graph from an offline global writing graph, retrieves market evidence, exposes the complete execution trace, and generates or revises structured reports in Chinese or English. Legacy code and environment-variable names retain `DFA`/`SUBDFA` for backward compatibility; the interface does not claim that the reusable graph is a classical DFA.

## Highlights

- Chinese and International/English interfaces with language-aware model output
- Offline global writing-graph views for precious metals, ETF, macro, cotton, and agriculture
- User-created and editable writing graphs
- Upload-driven writing-graph induction for TXT, Markdown, CSV, JSON, HTML, DOCX, PPTX, XLSX, and PDF templates, with live progress, classified storage, preview, reuse, and editable copies
- Query parsing, semantic state matching, query-specific execution-graph construction, evidence binding, and report assembly traces
- DeepSeek-compatible report generation and configurable embedding providers
- AkShare, Tushare, optional iFinD, and optional MySQL integrations
- Markdown report download and version-preserving report revision

## Repository layout

```text
subdfa-report-platform/
  backend/
    app/                       # HTTP API, pipeline, providers, persistence
    logicrag_core/             # Bundled DFA learning and query-processing code
    logicrag_runtime/          # Sanitized derived DFA artifacts only
    .env.example               # Public configuration template
  frontend/                    # HTML/CSS/JavaScript application and assets
  scripts/
    sanitize_runtime.py        # Removes private paths/credentials from DFA artifacts
    security_audit.py          # Scans tracked files before publishing
  vendor/README.md             # Optional proprietary SDK installation guidance
  configure_keys.ps1           # Safe local credential setup helper
  start_all.ps1                # Starts frontend and backend together
```

Personal queries, custom user writing graphs, raw corpora, retrieved market data, logs, databases, `.env`, and proprietary vendor binaries are intentionally excluded from Git.

## Online frontend showcase

Open the anonymous interactive frontend: <https://anonymous.4open.science/w/abfbab90-7d9f-49d0-8616-a000137fd930/>

The anonymous review mirror can expose the static frontend as an interactive browser demo. It constructs a query-specific DFA, visualizes state matching and execution, assembles a clearly labelled demo report, and stores uploaded-template DFA records in IndexedDB on the current device. Live market data, cross-device persistence, and model-generated conclusions require the Python backend; use the Windows quick start below for the complete application.

## Quick start on Windows

Requirements:

- Python 3.10+
- PowerShell 5.1+

Install dependencies:

```powershell
python -m pip install -r backend/requirements.txt
```

Create your private configuration file:

```powershell
.\configure_keys.ps1
```

Alternatively:

```powershell
Copy-Item backend/.env.example backend/.env
notepad backend/.env
```

Start the complete application:

```powershell
.\start_all.ps1
```

Open <http://127.0.0.1:8790/>. Use `stop_all.ps1` to stop both services.

## Add your own API keys

Credentials stay in `backend/.env`, which is ignored by Git. Never put keys in frontend code or commit them to the repository.

### Report model (DeepSeek-compatible)

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

You can use another OpenAI-compatible provider by changing the model and base URL.

### Semantic embedding

```dotenv
LOGICRAG_EMBEDDING_API_KEY=
LOGICRAG_EMBEDDING_MODEL=text-embedding-v4
LOGICRAG_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LOGICRAG_EMBEDDING_BATCH_SIZE=10
```

Without an embedding key, the platform falls back to local hash embeddings.

### Market-data providers

AkShare does not require a personal key. Tushare requires your own token:

```dotenv
SUBDFA_MARKET_DATA_SOURCE=auto
TUSHARE_TOKEN=
```

iFinD is optional and requires an official SDK installation and your own licensed account. See `vendor/README.md`.

### Database

The public template disables database persistence by default. To enable MySQL:

```dotenv
SUBDFA_DATABASE_ENABLED=true
SUBDFA_DATABASE_HOST=127.0.0.1
SUBDFA_DATABASE_PORT=3306
SUBDFA_DATABASE_NAME=logicrag_subdfa
SUBDFA_DATABASE_USER=root
SUBDFA_DATABASE_PASSWORD=
```

## Private training corpus

The repository includes sanitized derived writing-graph artifacts for the offline demonstration, not the raw FinLDP corpus. To re-induce a writing graph from a corpus you are authorized to use:

```dotenv
FINLDP_ROOT=D:\path\to\your\FinLDP-Bench
AUTOLOGIC_MAX_CASE_FILES=10000
AUTOLOGIC_FREQUENCY_THRESHOLD=0.03
```

Raw datasets under `data/` and `FinLDP-Bench-*` are ignored by Git.

## API

The frontend proxies the backend under `/api/v1`.

```http
GET /api/v1/health
```

```http
POST /api/v1/pipeline/preview
Content-Type: application/json

{
  "query": "Generate a macro report using high-frequency evidence.",
  "language": "en",
  "theta": 0.5,
  "tau": 0.2,
  "fallback_top_k": 3
}
```

Template-induced writing graphs are built as background jobs. Uploaded source files and a local DFA record are retained under `backend/data/template_uploads/`; when database persistence is enabled, the same record is also indexed in `template_dfas`.

```http
POST /api/v1/template-dfa-jobs
GET  /api/v1/template-dfa-jobs/{job_id}
GET  /api/v1/template-dfas
GET  /api/v1/template-dfas/{dfa_id}
POST /api/v1/template-dfas/archive
```

```http
POST /api/v1/reports/generate
Content-Type: application/json

{
  "query": "Generate a macro report using high-frequency evidence.",
  "language": "en",
  "use_ai": true
}
```

## Privacy checklist before publishing

1. Keep all real credentials only in `backend/.env`.
2. Run the runtime sanitizer after rebuilding writing-graph artifacts:

   ```powershell
   python scripts/sanitize_runtime.py
   ```

3. Stage files and run:

   ```powershell
   python scripts/security_audit.py
   ```

4. Confirm that `.env`, logs, databases, `vendor/ifind-sdk/`, personal query caches, and raw corpora are absent from `git status`.

See `SECURITY.md` for the full policy.

## License

No open-source license has been selected yet. Add a license only after the repository owner chooses the intended terms.
