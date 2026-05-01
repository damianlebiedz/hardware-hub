# Hardware Hub

Internal MVP to **rent and maintain company equipment**: hardware catalog, rental flow, admin panel, and an **AI layer** (seed import + semantic search). Built as a timeboxed demo of AI-assisted development and AI-native data features.

## Table of contents

- [Tech stack](#tech-stack)
- [Installation & running](#installation--running)
- [Features](#features)
- [Implementation status & trade-offs](#implementation-status--trade-offs)
- [AI development log](#ai-development-log)

---

## Tech stack

| Layer | Choice |
|--------|--------|
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| Package manager | Poetry |
| Frontend | Vue.js, Vite (dev proxy to `/api`) |
| Database | SQLite (file), default `data/hardware.db` |
| AI | Google Gemini API |
| Container | Docker Compose, persistent volume for DB |

---

## Installation & running

**Prerequisites:** Python 3.12+, Poetry, Node 22+ (local frontend), Docker (optional), `GEMINI_API_KEY` for AI routes.

**Config:** Root `.env` is loaded on import (`python-dotenv`); **environment variables already set (e.g. in Docker) are not overridden** by `.env`. See [`.env.example`](.env.example). Default DB path: `data/hardware.db` unless `DATABASE_URL` is set.

### Local (backend + Vite)

```bash
poetry install --with dev
cp .env.example .env   # set GEMINI_API_KEY, bootstrap vars, etc.
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd frontend && npm install && npm run dev
```

- **UI:** [http://localhost:5173](http://localhost:5173) — Vite proxies `/api` → `http://localhost:8000`
- **API docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### Docker (all-in-one)

```bash
docker compose up --build
```

Frontend on port **5173**, API on **8000**; SQLite persisted in the named volume (see `docker-compose.yml`).

### Quality & tests (from repo root)

```bash
poetry run black --check backend/ tests/
poetry run ruff check backend/ tests/
poetry run mypy backend/
poetry run pytest tests/ -v
```

AI tests mock Gemini; use `DATABASE_URL=sqlite:///:memory:` in containers when running tests so the live DB file is not touched.

---

## Features

**Core (non-AI):**

- **Login** — email + password; user objects stored in `localStorage` (MVP session shortcut; see [Implementation status](#implementation-status--trade-offs)).
- **Dashboard** — hardware list (sort/filter), **rent / return** with strict state guards (e.g. cannot rent items in Repair or already in use).
- **My rentals** — current user’s rentals.
- **Admin** — user creation (new users are always `user` role), hardware CRUD, **admin bootstrap** on startup: first admin is created or promoted from env (`BOOTSTRAP_ADMIN_*`) so a cold DB is usable without a chicken-and-egg path through `/api/admin/users`.

**AI — seed importer**

- Admin uploads (or pastes) JSON seed data. **Before** insert, the payload goes to Gemini to fix typos, resolve duplicate IDs, normalize dates/statuses, etc.
- Response includes a **per-field diff** so imports are **auditable** (what changed vs raw input).

**AI — semantic search (LLM as filter)**

- “Search with AI” sends the **full hardware list + natural-language query** to the model; the model returns **IDs** that match by meaning (e.g. “something to test a mobile app on” → phones/tablets). **Not** Text-to-SQL: the schema has no `use_case` / country columns, so SQL generation **hallucinated** filters; filtering over serialized rows fixes correctness at the cost of **O(n) tokens** per search (see trade-offs).

---

## Implementation status & trade-offs

**Intentional MVP shortcuts**

| Area | What we did | Risk |
|------|-------------|------|
| **Auth** | Login validates password (bcrypt); “session” is **client-stored** user + **`X-User-Role`** for admin | No server session, no token; **role header is spoofable**; XSS can read `localStorage` |
| **AI search / seed** | Entire table or whole seed array in one Gemini request | **Context / cost limits** as inventory grows; free-tier **rate limits** under demo load |
| **Bootstrap admin** | Env-based first admin; idempotent; password not logged | Password in env is operational debt; no env-driven **password rotation** after first provision |

**Gaps (including AI-assisted review)**

- **`/api/ai/*`** — no auth/role on AI routes: any client that can reach the API can burn quota or run seed (mitigation: session + admin-only for seed, tie quotas to `user_id`).
- **Rentals** — `user_id` from body/query not bound to a server principal (mitigation: derive from token only).
- **PII / compliance** — `notes` and future columns may reach Gemini; needs column policy + DPA awareness before real prod.
- **Prompt injection** — query and DB text are in the prompt; mitigations: delimited data blocks, length limits, logging (SQL injection from LLM output is blocked by int/list validation + Pydantic).
- **Tests** — `POST /api/admin/seed` (non-AI bulk) not fully covered; **`purchase_date`**: ORM `DateTime` vs Pydantic `date` may need alignment for PostgreSQL later.

**Next steps (by priority)**

- **Critical** — Real authN/Z (signed tokens, server-side role, no client-trusted `X-User-Role`); protect `/api/ai/*` and admin; bind rentals `user_id` to the authenticated user; **embedding + vector store** (or batching) before the catalog hits context limits; paid Gemini / budget caps for multi-user.
- **Medium** — Per-user AI quotas, usage logging, admin overrides; strip/pseudonymize PII in LLM prompts; prompt-injection mitigations (delimiters, field limits); integration tests for non-AI bulk seed; `purchase_date` type alignment for future PostgreSQL; split dev/prod config and secret management; human pass over AI-generated code.
- **Low** — Cancel in-flight AI on client disconnect; optional `BOOTSTRAP_ADMIN` password rotation flag; async session in lifespan if migrating to async SQLAlchemy; E2E / Vue tests; quota UX in the UI.

---

## AI development log

**How we used AI**

- **Phase 0 — planning & research:** wide architectural questions, stack choices, and deliverables (e.g. `ARCHITECTURE.md`, `INSTRUCTIONS_FOR_AGENTS.md`) drafted with **Gemini** (3.1 Pro) from a single product/tech brief.
- **Phase 1 — implementation:** **Cursor** with **Claude Sonnet 4.6** and **Composer 2** to execute steps, wire FastAPI + Vue, tests, and Docker, iterating on the generated instruction files.

**Why semantic search was reworked (short):** The first design used **Text-to-SQL**. Queries grounded in *intent* (e.g. “something to test a mobile app on”, “US companies”) have **no matching columns**, so the model **hallucinated** filters and returned plausibly wrong rows with HTTP 200. The replacement is **LLM-as-filter** (full JSON + query → list of matching IDs) — **correct** for the MVP, **O(n)** in tokens; production would use **embeddings + vector search**.

**Prompts (expand to view full text)**

<details>
<summary>Phase 0 — Gemini 3.1 Pro (broad research → ARCHITECTURE + INSTRUCTIONS_FOR_AGENTS)</summary>

```text
**# Role**

Act as a Senior Software Architect and AI Implementation Specialist.

**# Context**
I am building "Hardware Hub", an internal tool for employees to manage, rent, and maintain company equipment. The project must be delivered as a high-quality MVP in a 4-5 hours.

I have to deliver a solution focusing on three pillars:

**1. Admin & Users (The Management Engine):**

- A dedicated Admin Panel where the Admin can: manage hardware (add new items, delete old ones, toggle the "Repair" status) and manage accounts (create new user accounts; this is the only way to gain access to the system).
- Simple login screen where only users previously created by the admin (or the admin themselves) can access the system.
- Smart Dashboard with a list of hardware showing Name, Brand, Purchase Date, and Status (Available, In Use, Repair). Must support sorting and filtering.

**2. Business Logic (The Rental Engine):**

- Rent/Return Flow: Users should be able to "Rent" gear (Status -> In Use) and "Return" it.
- Core Logic: Implement strict database guards to ensure the rental process is logical and prevents impossible states (e.g., renting a device that is in "Repair" or already "In Use").

**3. AI-Native Layer (Semantic Search via Text-to-SQL):**

- Integrate an LLM via the Gemini API to provide a Semantic Search.
- **UX Rules:** The hardware table will have a standard search bar. It should include a "Search with AI" toggle/button. When activated, the user types natural language (e.g., "Find all broken Apple gear"). The backend uses the LLM to translate this into a safe SQL `SELECT` query, executes it, and returns the filtered data. The search bar retains the query but grayed out, with an 'X' button to clear it and return to the standard table view.

**# Data Strategy & The "Dirty" Seed**

Instead of just a background script, the data cleaning process will be an actual feature. We will have two ways to add data:

1. Standard manual CRUD (via Admin Form).
2. **AI-Assisted Seed Import:** A mini-feature in the Admin Panel where the Admin can initialize the database using the provided seed JSON. The backend must intercept this JSON, send it to the LLM to automatically fix typos (e.g., "Appel" -> "Apple") and resolve ID collisions (e.g., the duplicated ID `4`), and then safely insert the sanitized payload into the SQLite DB.

**# Tech Stack & Constraints:**

- **Backend:** Python 3.12 with FastAPI.
- **Frontend:** Vue.js.
- **Database:** File-based SQLite.
- Dependency Management: POETRY (strictly).
- Coding Standards: type hints (PEP 484), Google docstrings, Docker with Poetry, `docker-compose.yml` with volume for SQLite, tests + GitHub Actions CI, localStorage session hack (documented).

**# Your Task:**
Analyze my technical context and produce two markdown files:
1. **`ARCHITECTURE.md`**
2. **`INSTRUCTIONS_FOR_AGENTS.md`**

(Seed JSON from the original brief, tables for Dashboard/Admin/Rentals, and full step breakdown are omitted here for length; the Phase 0 output lives in the repo as those files.)
```

*Optional “dirty” seed themes: duplicate IDs, future dates, `"Appel"`, `notes` with assignee, etc.*

</details>

<details>
<summary>Phase 1 — Cursor (Claude Sonnet 4.6, Composer 2) — execute steps</summary>

```text
@INSTRUCTIONS_FOR_AGENTS.md @ARCHITECTURE.md Analyze the instructions and strictly execute Step 1/2/.../7.
```

</details>

<details>
<summary>Semantic search rework — LLM-as-filter (Claude Sonnet 4.6 in Cursor)</summary>

*Summary:* Replaces Text-to-SQL. Full hardware JSON + query → LLM returns only matching **integer IDs**; no frontend or schema change. *Code:* `backend/services/ai_service.py`, `backend/routers/ai.py`, `tests/test_ai_service.py`.

```text
Task: Replace the Text-to-SQL semantic search pipeline with an LLM-as-filter approach.

## Context

The current POST /api/ai/search endpoint translates a natural-language query into a SQL SELECT
statement via Gemini and executes it. This only works when the query maps to an explicit schema
column. Use-case queries like "I need something to test a mobile app on" or "all gear from US
companies" have no matching column, so the LLM hallucinates — returning factually incorrect
results (e.g. Samsung appearing in "US companies" results). The fix is to send the full list of
hardware records to the LLM and let it act as a semantic filter, returning only the IDs of
records that genuinely match the query.

## Requirements

### 1. backend/services/ai_service.py

Remove: text_to_sql(), sanitize_sql(), _SEARCH_SYSTEM_PROMPT, _HARDWARE_SCHEMA_DDL, _FORBIDDEN_KEYWORDS.

Add: def llm_filter_hardware(query: str, records: list[dict[str, Any]]) -> list[int]
(Gemini call, _strip_markdown_fences, JSON int list validation, 502/503, INFO logging, docstring.)

### 2. backend/routers/ai.py

POST /api/ai/search: load all rows → llm_filter_hardware → WHERE id IN (...). Empty DB → [].

### 3. tests/test_ai_service.py

Mock Gemini; cover matching IDs, empty records, empty LLM result, invalid JSON, non-array, missing API key.

### 4. Constraints

Do NOT modify SearchRequest, HardwareRead, or the frontend, or the seed importer.

Run: poetry run ruff check backend/ tests/ && poetry run mypy backend/
```

</details>

<details>
<summary>Bootstrap admin (Claude Sonnet 4.6 in Cursor)</summary>

```text
Task: Implement automatic bootstrap of the first admin user at application startup.

## Context

Currently, a fresh database has no admin user. The `/api/admin/users` endpoint itself requires admin role, so initial setup is blocked.

## Requirements

1. Add environment variables:
    - `BOOTSTRAP_ADMIN_ENABLED` (default: "true")
    - `BOOTSTRAP_ADMIN_EMAIL` (required if enabled)
    - `BOOTSTRAP_ADMIN_PASSWORD` (required if enabled)
2. On FastAPI startup (after DB initialization), run a bootstrap routine:
    - If `BOOTSTRAP_ADMIN_ENABLED` is false -> do nothing.
    - If enabled and user with `BOOTSTRAP_ADMIN_EMAIL` does not exist -> create user with role `"admin"` and hashed password.
    - If user exists but role is not `"admin"` -> promote role to `"admin"` (do not overwrite password).
    - If user exists and is already admin -> no-op.
3. Behavior must be idempotent and safe across repeated restarts.
4. Validation:
    - If enabled but email/password missing, fail startup with a clear error message.
5. Logging:
    - Add clear startup logs for each path: disabled / created / promoted / already exists / invalid config.
6. Architecture:
    - Keep startup handler clean; place bootstrap logic in a dedicated helper/service function.
7. Security:
    - Never store plaintext password.
    - Use the same password hashing utility used by auth/user creation.
8. DB compatibility:
    - Ensure this works with existing SQLite DBs that may not yet have password column (use project's migration strategy).
9. Docs:
    - Update README with bootstrap admin env vars and startup behavior.
    - Update/create `.env.example` with placeholders.
10. Reflection note (mandatory):
- In @README.md, in section '**AI Development Log'** include a subsection titled exactly:
`The "Correction"`
- In that section, describe at least one specific moment where the AI proposed a suboptimal, buggy, or insecure approach during this task.
- Explain how you identified the issue and how you corrected it to match the intended architecture/security.

## Deliverables

- Code changes in backend startup + auth/user domain as needed.
- Updated docs.
- A short summary of changed files and exact runtime behavior.
- Mandatory `The "Correction"` subsection in the final report.
```

</details>

**Corrections after AI output (summary)**

| Issue | What went wrong | Fix |
|--------|-----------------|-----|
| **Login** | First draft compared passwords as plain strings or leaked “user not found” | **bcrypt** + generic 401 for all failures |
| **Bootstrap logging** | Draft logged confirmation including password | Log email + action only, never password |
| **Seed UI** | Hardcoded seed JSON in `AdminView.vue` | File picker + parse/validate + send to API |
| **Admin features** | Missing hardware **DELETE** and create UI; DELETE route absent | Full stack: `DELETE` API, `deleteHardware`, admin UI add/remove |
| **AI seed** | Opaque “cleaned” data | **Field-level diff** in API + admin diff panel |
| **User form** | Role selector allowed new **admins** | Create only `user`; admin via bootstrap only |
| **Semantic search** | **Text-to-SQL** silent wrong answers on intent queries | **LLM-as-filter** by ID list; same API contract for frontend |

