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

### 2. Semantic Search via Text-to-SQL
**The Problem:** Passing the entire database to an LLM to find specific items is a bad architectural pattern. It doesn't scale, violates token limits, and causes significant latency.
**The AI Solution:** Instead of sending data to the AI, we send the *schema* and the user's natural language query to the AI to generate a raw `SELECT` SQL statement. The backend securely validates this (preventing prompt injection) and executes it against a read-only connection.
**Result:** O(1) token usage regardless of database size, extremely low latency, infinite scalability, and an intuitive UI with distinct "Standard" and "AI-Mode" states.

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

**Seed import UX bug (frontend hardcoding):** An AI-generated frontend draft hardcoded the entire "legacy seed" JSON directly inside `AdminView.vue` and sent that embedded constant to `/api/ai/seed`. That was a design error: users could not upload their own seed file, and the shipped frontend bundle effectively became the source of truth for migration input. This was corrected by removing the hardcoded dataset and adding a JSON file picker (`.json` / `application/json`) in the Admin panel. The selected file is parsed client-side, validated to be a JSON array, previewed, and only then sent to the backend when the admin clicks the import button.

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

<details>
<summary><b>Phase 1 Agent Prompts (Cursor Agent with Sonnet 4.6)</b></summary>

```text
@INSTRUCTIONS_FOR_AGENTS.md @ARCHITECTURE.md Analyze the instructions and strictly execute Step 1/2/.../7.
```
