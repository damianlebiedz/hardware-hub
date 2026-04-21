# Hardware Hub

Hardware Hub is an internal MVP application designed to manage, rent, and maintain company equipment. It leverages an AI-Native architecture to handle data migration and natural language search.

## Tech Stack
* **Backend:** Python (FastAPI, SQLAlchemy)
* **Dependency Management:** Poetry
* **Frontend:** Vue.js
* **Database:** SQLite (File-based)
* **AI Layer:** Google Gemini API

---

## Installation & Running

### Prerequisites

- Python `3.12+`
- [Poetry](https://python-poetry.org/docs/#installation)
- Node.js `22+` and npm (for local frontend dev)
- Docker Desktop (for containerized run)
- Gemini API key (required for `/api/ai/seed` and `/api/ai/search`)

---

### Option A: Local Run (Poetry + Vite)

Use this mode for fastest development feedback (hot reload on frontend).

#### 1) Clone and enter the project

```bash
git clone <your-repo-url>
cd hardware-hub
```

#### 2) Install backend dependencies with Poetry

```bash
poetry install --with dev
```

#### 3) Configure environment variables

Set `GEMINI_API_KEY` in your shell before starting the backend.

PowerShell:

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

bash/zsh:

```bash
export GEMINI_API_KEY="your_api_key_here"
```

Optional:
- `GEMINI_MODEL` (default: `gemini-2.5-flash`)
- `DATABASE_URL` (default: `sqlite:////app/data/hardware.db`)

**Bootstrap admin** (see [Admin Bootstrap](#admin-bootstrap) below):
- `BOOTSTRAP_ADMIN_ENABLED` (default: `true`)
- `BOOTSTRAP_ADMIN_EMAIL` (required when enabled)
- `BOOTSTRAP_ADMIN_PASSWORD` (required when enabled, min 8 chars)

#### 4) Start backend (FastAPI)

```bash
poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 5) Start frontend (Vite)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

#### 6) Open the app

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

> Note: In local mode, Vite proxies `/api` calls to `localhost:8000`.

---

### Option B: Docker Run (Backend + Frontend + Persistent SQLite Volume)

Use this mode for environment parity and one-command startup.

#### 1) Configure API key for Docker

Set `GEMINI_API_KEY` in your shell before running compose:

PowerShell:

```powershell
$env:GEMINI_API_KEY="your_api_key_here"
```

bash/zsh:

```bash
export GEMINI_API_KEY="your_api_key_here"
```

#### 2) Build and run all services

```bash
docker compose up --build
```

#### 3) Open the app

- Frontend (nginx): [http://localhost:5173](http://localhost:5173)
- Backend API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

#### 4) Stop services

```bash
docker compose down
```

The SQLite DB is persisted in the named Docker volume (`hardware-hub-sqlite-data`) mounted at `/app/data`, so data survives container restarts.

---

### Linting & Formatting

All commands run from the repository root via Poetry.

#### Black — code formatter

Check only (no changes written — used by CI):

```bash
poetry run black --check backend/ tests/
```

Auto-fix formatting in place:

```bash
poetry run black backend/ tests/
```

#### Ruff — linter

Check only:

```bash
poetry run ruff check backend/ tests/
```

Auto-fix safe issues in place:

```bash
poetry run ruff check --fix backend/ tests/
```

#### Mypy — static type checker

```bash
poetry run mypy backend/
```

Mypy is configured in `pyproject.toml` (`[tool.mypy]`). It covers the `backend/` package only; test files are excluded from strict checking to keep fixtures ergonomic.

---

### Running Tests

#### Option A: Local (Poetry)

Run the full test suite with verbose output from the repository root:

```bash
poetry run pytest tests/ -v
```

Run a specific test file:

```bash
poetry run pytest tests/test_logic.py -v
```

Run a specific test by name:

```bash
poetry run pytest tests/ -v -k "test_successful_rent"
```

The test suite uses an **in-memory SQLite database** (injected via the `DATABASE_URL` environment variable) so no running backend or Docker stack is needed.

> **Note:** Tests that involve AI features (`test_ai_service.py`) mock the Gemini API entirely — no `GEMINI_API_KEY` is required to run the suite.

#### Option B: Inside Docker Compose

If you want to run the test suite against the containerized backend (useful for integration checks), exec into the running backend container:

```bash
# Start the stack first (if not already running)
docker compose up -d --build

# Open a shell in the backend container
docker compose exec backend bash

# Inside the container — run tests against an isolated in-memory DB
DATABASE_URL=sqlite:///:memory: pytest tests/ -v
```

Or as a one-liner without an interactive shell:

```bash
docker compose exec backend bash -c "DATABASE_URL=sqlite:///:memory: pytest tests/ -v"
```

The `DATABASE_URL=sqlite:///:memory:` override is required inside the container so the tests get a clean, isolated database instead of the production SQLite file mounted at `/app/data/hardware.db`.

---

## AI Integration Strategy

In an AI-augmented world, choosing *how* to use AI is as important as using it at all. Here is the reasoning behind the architectural choices for the AI features in this MVP:

### 1. AI Seed Importer (Data Strategy)
**The Problem:** The initial seed data provided contained intentional anomalies (duplicate IDs, future purchase dates, and typos like "Appel"). Relying solely on standard database constraints during a CRUD import would result in silent failures or skipped records, causing the business to permanently lose track of physical assets.
**The AI Solution:** I implemented an "AI Seed Importer" feature for the Admin. Before the data hits the database, the raw JSON payload is sent to the LLM. The AI acts as a data sanitizer: resolving ID collisions, fixing typographical errors, and logically deducing missing statuses. 
**Result:** Safe, resilient data migration without losing records, wrapped in a sleek, non-blocking UI modal.

### 2. Semantic Search via LLM-as-Filter
**The Problem:** Users need to find hardware using natural-language, use-case driven queries — e.g. *"I need something to test a mobile app on"* should return phones and tablets. A Text-to-SQL approach (translating the query into a SQL `SELECT`) only works when the query maps directly to an explicit schema column (`brand`, `status`, `purchase_date`). Use-case queries have no corresponding column, so the LLM is forced to hallucinate — producing incorrect results (e.g. returning Samsung when asked for "US companies").
**The AI Solution:** The backend fetches all hardware records and sends them — together with the user's natural-language query — to the LLM. The LLM acts as a semantic filter: it reads every record, understands the intent of the query, and returns only the IDs of the records that genuinely match. The backend then retrieves exactly those rows and returns them.
**Result:** True semantic understanding regardless of which columns exist in the schema. An intuitive UI with distinct "Standard" and "AI-Mode" states, and an unchanged API contract — the frontend required zero changes.

---

## Implementation Status & Trade-offs

As this is a timeboxed MVP, certain architectural trade-offs were made intentionally to prioritize a rock-solid core business logic.

### Admin Bootstrap

Because `/api/admin/users` itself requires admin role, a fresh database would make initial setup impossible.  
The backend resolves this by automatically creating (or promoting) the first admin user on every startup.

#### Environment variables

| Variable | Default | Description |
|---|---|---|
| `BOOTSTRAP_ADMIN_ENABLED` | `true` | Set to `false` to disable the routine entirely (e.g. in CI). |
| `BOOTSTRAP_ADMIN_EMAIL` | — | Email of the bootstrap admin account. Required when enabled. |
| `BOOTSTRAP_ADMIN_PASSWORD` | — | Password for a **new** bootstrap account (min 8 chars). Not used if the user already exists. Required when enabled. |

A ready-to-copy template of all variables is in [`.env.example`](.env.example).

#### Startup behaviour (idempotent)

| Condition | Action | Log message |
|---|---|---|
| `BOOTSTRAP_ADMIN_ENABLED=false` | Skip entirely | `[bootstrap] Admin bootstrap is disabled` |
| Enabled, user not found | Create new admin with hashed password | `[bootstrap] Admin user '...' created successfully` |
| Enabled, user exists, role ≠ admin | Promote role to `admin` (password unchanged) | `[bootstrap] Existing user '...' promoted to admin role` |
| Enabled, user exists, role = admin | No-op | `[bootstrap] Admin user '...' already exists — no changes made` |
| Enabled, email or password missing | **Abort startup** with `RuntimeError` | Clear error in startup log |

#### Security

- The bootstrap password is hashed with bcrypt via the same `hash_password()` utility used everywhere else.
- The plaintext password is read once from the environment and never logged or stored.
- Treat `BOOTSTRAP_ADMIN_PASSWORD` as a production secret: provide it via a secret manager/CI secret, never commit it to git, and avoid sharing it in plain `.env` files.
- For production, prefer running bootstrap only for initial provisioning (`BOOTSTRAP_ADMIN_ENABLED=false` afterwards) and rotate the admin password immediately after first login.

---

### Authentication Hack (What / How / Why)

**What:** We intentionally do not use JWT/OAuth2/OIDC yet.  
The app uses password-verified login, but session/auth state is still handled with an MVP shortcut.

**How:** The backend validates `email + password` against a bcrypt password hash and returns a user profile on success.  
The frontend stores that user object in `localStorage` and sends role context in headers for admin-gated routes.  
No signed access token, refresh token, or HTTP-only cookie session is issued.

**Why:** This project is a timeboxed MVP focused on proving the rental workflow, AI seed import, and semantic search.  
Implementing full token/session lifecycle security (JWT/OIDC, refresh, revocation, hardened cookie handling) was deferred to keep delivery scope realistic.

**Production warning:** This shortcut is not sufficient for production and must be replaced before public or sensitive deployment.
Minimum production baseline:
- Use OAuth2/OIDC (or equivalent SSO) and issue signed tokens (JWT/PASETO) server-side.
- Prefer HTTP-only, Secure, SameSite cookies for session transport (instead of frontend-managed `localStorage` auth state).
- Add refresh-token rotation, token expiry, logout/revocation, and server-side authorization checks (never trust role headers from the client).

* **Fully Implemented:** * Strict Rental Logic Guardrails (preventing impossible states).
  * 100% Type-hinted backend with comprehensive docstrings.
  * AI-driven Seed Import pipeline & Semantic Search.
* **Shortcuts & "Hacks":** * **Authentication:** Login now requires `email + password`, with BCrypt password hashing on the backend. We still keep the MVP session shortcut where the returned user object is stored in `localStorage`, and role checks continue to use request headers for admin-gated operations.
  * **The "Why":** Implementing robust JWT would consume ~20% of the allocated time. This simple session hack is sufficient to demonstrate role-based access for the MVP.
  * **Security note:** Passwords are never stored in plaintext and password hashes are never returned in API responses.
  * **Migration impact:** Existing SQLite users created before password hashes were introduced cannot log in until an admin recreates or resets their account with a password.
  * **The "Future":** In production, this must be replaced with OAuth2/OIDC (or equivalent IdP), signed tokens, HTTP-only Secure cookies, refresh rotation, and proper revocation/logout handling.
* **Next Steps (24h Roadmap):**
  1. Refactor authentication to JWT/SSO.
  2. ...

---

## AI Development Log

### Tooling
* **Architecture & Planning:** Google Gemini 3.1 Pro
* **Implementation & Coding:** Cursor AI (...)

### The "Correction"

During this task, an initial implementation idea used direct string comparison between stored and incoming passwords in the login flow. That approach is insecure because it implies storing plaintext passwords or reversible secrets. I caught the issue when validating the security requirements (`password_hash` only, generic 401 responses, and no secret leakage) and replaced it with `passlib[bcrypt]` hashing plus `verify_password()`.

I also corrected the login error behavior: a first draft differentiated "email not found" from "wrong password". That leaks account existence. The final behavior always returns a generic `401 Invalid credentials` for unknown emails, wrong passwords, and legacy users missing a hash.

**Bootstrap task (admin bootstrap):** During implementation of the admin bootstrap routine, the first draft read `BOOTSTRAP_ADMIN_PASSWORD` from the environment and wrote a confirmation log line of the form `"Bootstrap password set to: <value>"` to make the startup output easy to read during development. That approach would have exposed the plaintext admin credential in container logs — a critical security issue in any environment where stdout is collected (Docker, cloud log aggregators, CI). The issue was caught before commit by reviewing what the log line would contain. The fix was straightforward: log only the email address and the action taken (created / promoted / already exists), and never reference the password value at any point after it has been passed to `hash_password()`.

<details>
<summary><b>Bootstrap task Prompt</b></summary>

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
- In @README.md, in section ‘**AI Development Log’** include a subsection titled exactly:
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


**Seed import UX bug (frontend hardcoding):** An AI-generated frontend draft hardcoded the entire "legacy seed" JSON directly inside `AdminView.vue` and sent that embedded constant to `/api/ai/seed`. That was a design error: users could not upload their own seed file, and the shipped frontend bundle effectively became the source of truth for migration input. This was corrected by removing the hardcoded dataset and adding a JSON file picker (`.json` / `application/json`) in the Admin panel. The selected file is parsed client-side, validated to be a JSON array, previewed, and only then sent to the backend when the admin clicks the import button.

**Missing admin CRUD controls in the Hardware Dashboard (incomplete feature scope):** The original implementation of the Admin Panel was narrowly scoped to user creation and AI Seed Import. The AI agent did not produce any UI for the hardware CRUD operations (`POST /api/hardware`, `DELETE /api/hardware/{id}`) that were explicitly required by the specification ("manage hardware — add new items, delete old ones"). The `POST` endpoint and a corresponding `createHardware` API client function were generated correctly, but they were never wired up to any UI component. Deletion was not even implemented at the API level — the `DELETE` endpoint was missing entirely.

The gap was identified when validating the Admin Panel against the original requirements checklist. The fix spans the full stack:
- **Backend (`routers/hardware.py`):** Added `DELETE /api/hardware/{id}` (admin only, HTTP 204) that removes the item and cascade-deletes all linked rental records in a single transaction.
- **Frontend (`api/client.js`):** Added `deleteHardware(id)` wrapper.
- **Frontend (`DashboardView.vue`):** Admin users now see a red ✕ button on every table row. Clicking it triggers a native `confirm()` dialog (with item name and a warning about rental history). On confirmation the row is removed optimistically from the local list. Admin users also see a "+ Add Hardware" button in the dashboard header. Clicking it opens an animated popover bubble containing a form (name, brand, purchase date, status, notes). Non-admin users see neither control.

**AI seed importer as a black box (lack of auditability):** The original AI seed pipeline had a fundamental auditability gap that was not caught during initial design. The importer correctly cleaned the data — fixing typos, normalizing dates, resolving duplicate IDs — but the changes made by the AI were completely invisible to the operator. The admin had no way to know *what* was actually corrected: whether a brand name was silently changed from `"Appel"` to `"Apple"`, whether a date was reformatted, or whether a status was inferred from the notes field. Trusting an AI to mutate company asset records without any audit trail is not an acceptable production behaviour, regardless of how accurate the AI tends to be.

This was identified as a limitation after the initial implementation was complete. The fix spans the full stack:
- **Backend (`schemas.py`):** Added `SeedFieldChange` and `SeedRecordChange` models to represent per-record, per-field corrections.
- **Backend (`ai_service.py`):** `sanitize_with_gemini` now computes a field-level diff between each raw input record and the corresponding cleaned output, collecting every changed field (name, brand, status, purchase date, notes) into a structured `SanitizeResult`.
- **Backend (`routers/ai.py`):** The `POST /api/ai/seed` response now includes a `changes` array alongside the inserted records.
- **Frontend (`AdminView.vue`):** After a successful import, the Admin panel renders an "AI corrected N records" diff panel. Each modified record shows a collapsible list of field-level before/after changes (e.g. `Brand: "Appel" → "Apple"`), with auto-expand so corrections are immediately visible.

The result is a fully auditable import: the admin can verify every decision the AI made before navigating away.

**Admin could create other admins (privilege escalation via UI):** The original implementation of the "Add User" form in the Admin Panel included a role selector with two options — `User` and `Admin`. This meant that any admin could freely promote a newly created account to admin status through the UI, bypassing any intent to restrict privileged access. From a security standpoint, this is a privilege-escalation vector: a compromised admin account could silently mint additional admin accounts, and there was no architectural decision or requirement that justified allowing it. The `POST /api/admin/users` endpoint likewise accepted a `role` field of either `"admin"` or `"user"` in its request schema, so the backend offered no defence either.

The fix spans both layers:
- **Backend (`schemas.py`):** Removed the `role` field from `UserCreate` entirely. The endpoint now unconditionally assigns `role="user"` to every account it creates.
- **Backend (`routers/admin.py`):** `create_user` hardcodes `role="user"` when constructing the ORM object, independent of any client-supplied value.
- **Frontend (`views/AdminView.vue`):** Removed the role `<select>` element and the associated `newRole` reactive ref. The form now only collects email and password.
- **Frontend (`api/client.js`):** Removed the `role` parameter from `createUser()`.

Admin accounts can only be provisioned through the bootstrap mechanism (environment variables at startup), which is an intentional, auditable, ops-level action.

**Semantic Search returning wrong results (Text-to-SQL schema blindness):** The original semantic search implementation translated natural-language queries into SQL `SELECT` statements via the Gemini API. The LLM was given the exact database schema DDL and instructed to generate a safe, read-only query. This worked correctly for queries that map directly to schema columns — e.g. *"show all items in Repair"* correctly produced `WHERE status = 'Repair'`. However, the implementation broke silently for use-case queries like *"I need something to test a mobile app on"* or *"all gear from US companies"*: the `hardware` table has no `category`, `country_of_origin`, or `use_case` column. The LLM had no column to filter on, so it fell back on its own world knowledge to guess brand names — and guessed wrong, returning Samsung (a South Korean company) as a US company. The failure was entirely silent: the endpoint returned HTTP 200 with plausible-looking but factually incorrect results.

This was identified by manually testing the feature against the requirement: *"I need something to test a mobile app on" → returns iPhones/Androids"* (from the original specification). The root cause was not a bug in the SQL generation logic itself, but a fundamental mismatch between what Text-to-SQL can express and what the feature actually needs to support: semantic, intent-based retrieval that is independent of schema structure.

The fix replaces the Text-to-SQL pipeline with an **LLM-as-filter** approach:
- **Backend (`ai_service.py`):** Removed `text_to_sql()`, `sanitize_sql()`, `_SEARCH_SYSTEM_PROMPT`, `_HARDWARE_SCHEMA_DDL`, and `_FORBIDDEN_KEYWORDS`. Added `llm_filter_hardware(query, records)`: fetches all hardware records, serializes them to JSON, and sends them to the LLM with a prompt instructing it to return only the IDs of records that semantically match the query. The response is parsed as a JSON integer array; any non-conforming response raises HTTP 502.
- **Backend (`routers/ai.py`):** Updated `POST /api/ai/search` to fetch all rows first, pass them to `llm_filter_hardware`, and return only the matched rows. Short-circuits with an empty list if the database is empty.
- **Frontend:** Zero changes — the API contract (`SearchRequest` in, `list[HardwareRead]` out) is identical.

**Why this is a hack and what to do next:**
This approach trades scalability for correctness. Token usage is now O(n) in the number of hardware records: every search sends the full dataset to the LLM. For a small company inventory (tens to low hundreds of items) this is entirely acceptable. As the dataset grows into the thousands, the approach will hit model context-window limits, incur significant per-query costs, and introduce noticeable latency.

The production-grade replacement is **embedding-based vector search**:
1. When a hardware record is created or updated, generate a vector embedding of its fields (name, brand, notes, etc.) using the Gemini Embedding API or equivalent.
2. Store the embedding alongside the record — either in a dedicated vector store (Qdrant, Chroma, Weaviate) or in Postgres with the `pgvector` extension.
3. At search time, embed the user's query into the same vector space and retrieve the top-k nearest neighbours by cosine similarity.
4. This reduces per-query token usage to a single embedding call (O(1) in dataset size) and enables sub-second retrieval even over millions of records.

Until that infrastructure is in place, the LLM-as-filter approach is a pragmatic and correct MVP solution.

---

### The Prompt Trail

<details>
<summary><b>Phase 0 Planning Prompt (Gemini 3.1 Pro)</b></summary>

``````text
**# Role**

Act as a Senior Software Architect and AI Implementation Specialist.

**# Context**
I am building “Hardware Hub”, an internal tool for employees to manage, rent, and maintain company equipment. The project must be delivered as a high-quality MVP in a 4-5 hours.

I have to deliver a solution focusing on three pillars:

**1. Admin & Users (The Management Engine):**

- A dedicated Admin Panel where the Admin can: manage hardware (add new items, delete old ones, toggle the “Repair” status) and manage accounts (create new user accounts; this is the only way to gain access to the system).
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

**Seed Data:**

```json
[
{ "id": 1, "name": "Apple iPhone 13 Pro Max", "brand": "Apple",
"purchaseDate": "2021-11-23", "status": "Available" },
{ "id": 2, "name": "Apple MacBook Pro 13", "brand": "Apple",
"purchaseDate": "2021-12-20", "status": "In Use" },
{ "id": 3, "name": "Razer Basilisk V2", "brand": "Razer",
"purchaseDate": "2021-06-05", "status": "Repair" },
{ "id": 4, "name": "SAMSUNG Galaxy S21", "brand": "Samsung",
"purchaseDate": "2021-11-23", "status": "Available" },
{ "id": 5, "name": "Dell XPS 15 9510", "brand": "Dell",
"purchaseDate": "2022-03-15", "status": "Available", "notes":
"Battery swelling, do not issue without service." },
{ "id": 6, "name": "Logitech MX Master 3", "brand": "Logitech",
"purchaseDate": "2027-10-10", "status": "Available" },
{ "id": 7, "name": "Sony WH-1000XM4", "brand": "Sony",
"purchaseDate": "2022-01-12", "status": "In Use", "assignedTo":
"j.doe@booksy.com" },
{ "id": 4, "name": "Duplicate ID Test Laptop", "brand": "Lenovo",
"purchaseDate": "2023-01-01", "status": "Repair" },
{ "id": 9, "name": "iPad Pro 12.9", "brand": "Appel",
"purchaseDate": "22-05-2023", "status": "Available" },
{ "id": 10, "name": "Unknown Device", "brand": "",
"purchaseDate": null, "status": "Unknown" },
{ "id": 11, "name": "MacBook Air M2", "brand": "Apple",
"purchaseDate": "2023-08-01", "status": "Available", "history":
"Returned by user with liquid damage. Keyboard sticky." }
]
```

**# Tech Stack & Constraints:**

- **Backend:** Python 3.12 with FastAPI.
- **Frontend:** Vue.js.
- **Database:** File-based SQLite.
- Dependency Management: POETRY (Strictly enforced, no requirements.txt).
- Coding Standards (CRITICAL): ALL Python code must include strict type-hints (PEP 484) and comprehensive docstrings (Google style). The code must be clean, modular, and DRY.
- Docker: The project MUST be fully containerized. We need a `docker-compose.yml` to orchestrate the Vue frontend and FastAPI backend. CRITICAL: The backend Dockerfile must utilize Poetry, and the `docker-compose.yml` MUST mount a Docker Volume for the SQLite database to prevent data loss upon container restart.
- **Testing:** 3 core, critical tests (e.g., "Cannot rent broken hardware").
- **CI/CD Pipeline:** The project must include a GitHub Actions workflow. On every `push` from ‘develop’ into the ‘main’ branch, it should spin up a Python environment, install Poetry, install dependencies, run black+ruff+mypy, and run the Pytest suite to ensure the business logic is never broken.
- **Dashboards:** 3 main views (Hardware list, My Rentals, Admin Panel).
- **Shortcuts & Hacks:** Use local storage for sessions instead of a proper JWT flow to save time (explicitly document this as an MVP hack).

**# Your Task:**
Analyze my technical context and produce two markdown files:
1. **`ARCHITECTURE.md`**: Technical documentation of the system. It must include the database schema, API endpoint structure, and a clear explanation of how the Semantic Search (Text-to-SQL) and AI Seed Import pipeline will work.
2. **`INSTRUCTIONS_FOR_AGENTS.md`**: A step-by-step, prompt-ready guide that I will use with an AI coding agent (Cursor) to build the project. Break the implementation down into 5-6 logical, iterative "Steps" (e.g., Step 1: FastAPI Init & Models, Step 2: Vue.js UI & Auth Hack, Step 3: AI Seed Importer, etc.) so I can use them with Cursor sequentially.
``````

</details>

<details>
<summary><b>Phase 1 Agent Prompts (Cursor Agent with Sonnet 4.6)</b></summary>

```text
@INSTRUCTIONS_FOR_AGENTS.md @ARCHITECTURE.md Analyze the instructions and strictly execute Step 1/2/.../7.
```

</details>

<details>
<summary><b>Semantic Search Rework — LLM-as-Filter (Cursor Agent with Sonnet 4.6)</b></summary>

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

Remove the following identifiers entirely (they are no longer used):
  - text_to_sql()
  - sanitize_sql()
  - _SEARCH_SYSTEM_PROMPT
  - _HARDWARE_SCHEMA_DDL
  - _FORBIDDEN_KEYWORDS

Add a new function with the signature:

  def llm_filter_hardware(query: str, records: list[dict[str, Any]]) -> list[int]:

Behaviour:
  - If GEMINI_API_KEY is not set, raise HTTPException 503 (same pattern as sanitize_with_gemini).
  - If records is empty, return [] immediately without calling the API.
  - Build a prompt that contains:
      a) A system instruction telling the LLM it is a hardware search assistant. It must read
         the provided JSON array of hardware records and return ONLY a valid JSON array of
         integer IDs of the records that semantically match the user's query.
         It must not include explanations, markdown fences, or any other text.
         If no records match, it must return an empty JSON array: []
      b) The full records list serialised with json.dumps.
      c) The user's natural-language query.
  - Call the Gemini API (same client/model pattern as the rest of the file).
  - Strip markdown fences from the response using _strip_markdown_fences.
  - Parse the response with json.loads. If parsing fails, or if the result is not a list, or
    if any element is not an integer, raise HTTPException 502 with a descriptive detail message.
  - Log: query text, number of records sent, and returned IDs (all at INFO level).
  - If the Gemini call itself raises an exception, log it and raise HTTPException 502.
  - Full PEP 484 type hints and a Google-style docstring are required.

### 2. backend/routers/ai.py

Update the POST /api/ai/search endpoint:
  - Remove the import of text_to_sql (and sanitize_sql if imported).
  - Import llm_filter_hardware from backend.services.ai_service.
  - New pipeline inside search_hardware():
      1. Query the database for all rows: db.execute(text("SELECT * FROM hardware")).
      2. Serialise rows to list[dict] using column names as keys (same pattern already used
         for the search result serialisation at the bottom of the function).
      3. If the list is empty, return [] immediately.
      4. Call llm_filter_hardware(payload.query, all_records) to get matching_ids.
      5. If matching_ids is empty, return [].
      6. Query the database for only those IDs:
           SELECT * FROM hardware WHERE id IN (<matching_ids>)
         Use SQLAlchemy's text() with a bindparam or inline the IDs safely (they are
         validated integers, so interpolation is safe).
      7. Serialise and return the result rows.
  - Do not change the function signature, response_model, or any HTTP status codes.

### 3. tests/test_ai_service.py

Remove any tests that specifically cover text_to_sql() or sanitize_sql().

Add tests for llm_filter_hardware() — mock the Gemini client (same mocking pattern already
used in the file):

  - test_llm_filter_hardware_returns_matching_ids:
      Mock Gemini response text = "[1, 3]". Call with a two-record list and a query string.
      Assert return value == [1, 3].

  - test_llm_filter_hardware_empty_records_short_circuits:
      Call with records=[]. Assert return value == [] and that the Gemini client was never
      instantiated.

  - test_llm_filter_hardware_empty_llm_result:
      Mock Gemini response text = "[]". Assert return value == [].

  - test_llm_filter_hardware_invalid_json_raises_502:
      Mock Gemini response text = "not valid json". Assert HTTPException with status_code 502.

  - test_llm_filter_hardware_non_array_raises_502:
      Mock Gemini response text = '{"ids": [1]}'. Assert HTTPException with status_code 502.

  - test_llm_filter_hardware_missing_api_key_raises_503:
      Patch os.getenv to return None for GEMINI_API_KEY. Assert HTTPException status_code 503.

### 4. Constraints

  - Do NOT modify the SearchRequest or HardwareRead schemas.
  - Do NOT modify the frontend in any way.
  - Do NOT modify the seed importer pipeline (sanitize_with_gemini, _SEED_SYSTEM_PROMPT, etc.).
  - All new code must have full type hints and Google-style docstrings.
  - After editing, run: poetry run ruff check backend/ tests/ and poetry run mypy backend/
    and fix any reported issues before finishing.

## Deliverables

  - Updated backend/services/ai_service.py
  - Updated backend/routers/ai.py
  - Updated tests/test_ai_service.py
  - A short summary of which functions were removed, which were added, and the exact
    runtime behaviour of the new search endpoint.
```

</details>
