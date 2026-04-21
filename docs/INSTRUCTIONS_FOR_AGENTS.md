# Cursor Agent System Prompts: Hardware Hub MVP

*Note to Developer: Feed these steps sequentially into Cursor's chat or composer. Wait for full implementation and testing of each step before proceeding to the next.*

### Step 1: Foundation, Poetry, and Docker
**Context:** Initialize the project repository, set up the backend framework, and configure containerization.
**Prompt:**
> "Act as a Senior Python Developer. Initialize a FastAPI project using Python 3.12. 
> 1. Use `poetry init` and define dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `pytest`, `google-generativeai`. Strictly NO `requirements.txt`.
> 2. Create a basic FastAPI `main.py` with a health check endpoint.
> 3. Create a `Dockerfile` for the backend that uses Poetry to install dependencies.
> 4. Create a `docker-compose.yml` that sets up the backend and a placeholder for the Vue frontend. **CRITICAL:** Define a Docker Volume mapped to `/app/data` in the backend container to persist our SQLite database. 
> Ensure all Python code includes strict PEP 484 type hints and Google-style docstrings."

### Step 2: Database Schema & Business Logic Guards
**Context:** Implement the SQLite models and the strict rules governing rentals.
**Prompt:**
> "Using SQLAlchemy, build the database models for `User`, `Hardware`, and `Rental` based on standard relational mappings.
> 1. Set up an SQLite connection pointing to `/app/data/hardware.db`.
> 2. Implement the Pydantic schemas for data validation.
> 3. Write a service function for 'Renting' hardware. This function MUST include strict database-level or transaction-level guards: It must raise a ValueError or HTTPException if the requested hardware's status is 'Repair' or 'In Use'.
> 4. Write a service function for 'Returning' hardware.
> 5. Create a `tests/test_logic.py` file and write 3 core Pytest functions: test successful rent, test failure when renting 'Repair' gear, test failure when renting 'In Use' gear. Ensure these pass."

### Step 3: Core API Endpoints & Auth Hack
**Context:** Expose the CRUD operations and implement the MVP login workaround.
**Prompt:**
> "Create the FastAPI routers for Users, Hardware, and Rentals.
> 1. Create a `POST /api/auth/login` endpoint. As an MVP hack, this will just accept an email, check if it exists in the `users` table, and return the user object (no JWT, no hashing). We will rely on the frontend to store this in `localStorage`. Add docstrings noting this is a security hack for MVP speed.
> 2. Create CRUD endpoints for Hardware (List, Create, Update/Toggle Status).
> 3. Expose the Rent and Return service functions as `POST` endpoints.
> 4. Create an endpoint to fetch 'My Rentals' based on a provided user ID."

### Step 4: AI Seed Importer (Gemini)
**Context:** Build the AI data sanitization pipeline.
**Prompt:**
> "Integrate the `google-generativeai` SDK. Create an endpoint `POST /api/ai/seed`.
> 1. The endpoint should accept a raw JSON payload (representing messy legacy data).
> 2. Write a function that sends this JSON to the Gemini API (gemini-1.5-pro or flash) with a strict system prompt. The prompt must instruct the AI to: Fix typos (e.g., 'Appel' to 'Apple'), standardize date formats to YYYY-MM-DD, map invalid statuses to 'Available' (or 'Repair' if notes indicate damage), and resolve duplicate integer IDs. It must return pure JSON.
> 3. Take the LLM's JSON response, parse it through our `Hardware` Pydantic model to guarantee type safety, and bulk insert it into the SQLite database.
> 4. Add comprehensive docstrings explaining this flow."

### Step 5: Semantic Search (Text-to-SQL)
**Context:** Build the natural language search capability.
**Prompt:**
> "Create an endpoint `POST /api/ai/search` that accepts a string query (e.g., 'Show me broken Apple laptops').
> 1. Send a prompt to Gemini that includes the exact SQLite schema for the `hardware` table. Instruct it to act as a SQL translator and return ONLY a valid SQLite `SELECT` statement.
> 2. **CRITICAL SECURITY:** Write a sanitization function that takes the LLM output, strips any markdown formatting (like ```sql), and strictly verifies the string begins with `SELECT` and does NOT contain keywords like `DROP`, `DELETE`, `UPDATE`, `INSERT`, `PRAGMA`, or `ALTER`.
> 3. Execute the sanitized SQL query against the SQLite database.
> 4. Map the resulting rows to JSON and return them to the client."

### Step 6: Vue.js Frontend & UI Logic
**Context:** Build the client application.
**Prompt:**
> "Initialize a Vue.js (Composition API) application in a `frontend` folder. Update the `docker-compose.yml` to build and serve it.
> 1. Implement a simple Login view that hits the backend and stores the user object in `localStorage`.
> 2. Build the Admin Panel: A view to add new users and a button to trigger the 'AI Seed Import' (send hardcoded raw JSON to the backend).
> 3. Build the Main Hardware Dashboard: A table listing hardware. Implement a search bar. Add an 'AI Search Toggle'. 
>   - When AI is OFF, the search filters locally or via standard query params.
>   - When AI is ON, the search input sends natural language to `/api/ai/search` and populates the table with the results. Keep the search input grayed out while showing AI results, with an 'X' to clear.
> 4. Build a 'My Rentals' dashboard showing items currently checked out by the logged-in user, with a 'Return' button next to each."

### Step 7: CI/CD Pipeline (GitHub Actions)
**Context:** Ensure code quality and logic protection.
**Prompt:**
> "Create a `.github/workflows/main.yml` file.
> 1. Trigger the workflow on `push` to the `main` branch, but only if the PR comes from `develop` (or simulate this restriction).
> 2. The job should set up Python 3.12.
> 3. Install Poetry (`pip install poetry`).
> 4. Install dependencies (`poetry install`).
> 5. Run formatting and linting checks using `black` and `ruff`.
> 6. Run static type checking with `mypy`.
> 7. Run the Pytest suite to ensure the business logic (rental guards) is intact. If any step fails, the action must fail."