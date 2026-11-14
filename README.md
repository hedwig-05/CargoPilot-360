# CargoPilot 360

AI-assisted logistics operations management backend. This repository currently contains the FastAPI backend, SQLAlchemy data layer, logistics engines, agent orchestration, and LLM integrations. A frontend is intentionally out of scope.

## Current implementation

- Shipment, event, document, validation, exception, investigation, risk, resolution-plan, action, workflow, run, and audit APIs.
- Document extraction and cross-document validation.
- Monitoring for shipment delays and missing documents.
- Evidence-based exception investigation.
- Risk assessment and resolution-plan generation.
- Human approval and simulated action execution.
- Resolution verification.
- Supervisor orchestration and a LangGraph workflow.
- Gemini and Ollama LLM providers with optional fallback routing.

The repository should be treated as an active prototype until the isolated-database integration tests and a complete end-to-end workflow have passed. Do not infer production readiness from the presence of these modules.

## Repository layout

```text
backend/
  app/
    agents/       LangGraph state and workflow
    api/          FastAPI routers
    database/     SQLAlchemy connection/session setup
    engines/      Logistics business logic
    llm/          Gemini/Ollama provider routing
    models/       SQLAlchemy models
  test_*.py       Existing manual and focused test scripts
  .env.example    Local configuration template
cargopilot_schema_v3.sql
data/
```

## Requirements

- Python 3.11+ recommended; use a version supported by all installed dependencies.
- MySQL 8.x.
- An optional Gemini API key for cloud LLM calls.
- Optional Ollama installation and a locally pulled model for local inference.

## Local setup (Windows PowerShell)

From the repository root:

```powershell
cd backend
py -m venv ..\venv
..\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install the backend dependencies used by the project in the active environment. A consolidated, pinned dependency manifest is still required before a clean-machine reproducibility claim can be made.

Copy the environment template and fill in the local database credentials:

```powershell
Copy-Item .env.example .env
```

Never commit `.env`, database passwords, API keys, or private certificates.

## Database safety

The default database name in the template is `cargopilot`, matching the existing developer database. **Do not run mutating integration tests or full agent workflows against that database.**

Before end-to-end testing:

1. Create a separate MySQL database named `cargopilot_test`.
2. Restore a disposable copy of the schema and representative seed data into it.
3. Verify that the application is connected to `cargopilot_test`.
4. Use a test-specific environment file/configuration and add a hard guard that refuses destructive tests unless the database name ends in `_test`.
5. Keep the original `cargopilot` database untouched.

The schema file at the repository root is `cargopilot_schema_v3.sql`. Confirm that the schema and SQLAlchemy models are aligned before applying migrations or altering an existing database.

## Run the API

From the `backend` directory, with the virtual environment activated and a configured database:

```powershell
uvicorn app.main:app --reload
```

- API root: http://127.0.0.1:8000/
- Health check: http://127.0.0.1:8000/health
- OpenAPI / Swagger UI: http://127.0.0.1:8000/docs

The health endpoint currently reports application process health; it is not a database or LLM readiness check.

## LLM configuration

Configure the provider in `backend/.env`:

- `LLM_PROVIDER=gemini` or `ollama`
- `LLM_FALLBACK_PROVIDER=ollama` or `gemini`
- `GEMINI_API_KEY` and optionally `GEMINI_MODEL`
- `OLLAMA_MODEL`

The fallback provider is optional. For Ollama, install Ollama separately and pull the selected model before requesting local inference. LLM output is advisory: it must not independently approve or execute operational actions.

## Verification status

Focused scripts exist under `backend/test_*.py`, but many are developer scripts that connect to the configured database and may write records. Review each script before running it. No claim is made here that the full monitoring-to-verification workflow has passed on a clean, isolated test database.

## Operational safeguards

- Keep human approval in the action lifecycle.
- Treat model-generated explanations as suggestions, not verified facts.
- Preserve investigation evidence and audit records.
- Test retry/idempotency behavior before enabling scheduled or repeated workflows.
- Do not expose credentials or internal database details through API responses.
