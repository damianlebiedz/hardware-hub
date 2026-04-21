# Hardware Hub: System Architecture & Technical Specification

## 1. System Overview
Hardware Hub is an internal, containerized web application designed for managing company equipment. Built as a rapid MVP, it prioritizes core business logic—specifically the state machine of renting and returning hardware—and introduces AI-native layers to streamline data ingestion and retrieval. 

**Core Stack:**
* **Backend:** Python 3.12, FastAPI
* **Frontend:** Vue.js (Composition API recommended)
* **Database:** SQLite (File-based)
* **Package Management:** Poetry
* **Containerization:** Docker & Docker Compose
* **AI Integration:** Google Gemini API

## 2. Database Schema (SQLite)

The database relies on strict constraints to enforce business logic at the data layer. 

| Table: `users` | Type | Constraints / Notes |
| :--- | :--- | :--- |
| `id` | Integer | Primary Key, Auto-increment |
| `email` | String | Unique, Not Null |
| `role` | String | 'admin' or 'user' |

| Table: `hardware` | Type | Constraints / Notes |
| :--- | :--- | :--- |
| `id` | Integer | Primary Key, Auto-increment |
| `name` | String | Not Null |
| `brand` | String | |
| `purchase_date` | Date | |
| `status` | String | 'Available', 'In Use', 'Repair' |
| `notes` | Text | |

| Table: `rentals` | Type | Constraints / Notes |
| :--- | :--- | :--- |
| `id` | Integer | Primary Key, Auto-increment |
| `user_id` | Integer | Foreign Key (`users.id`) |
| `hardware_id` | Integer | Foreign Key (`hardware.id`) |
| `rented_at` | DateTime | Default Current Timestamp |
| `returned_at` | DateTime | Nullable |

## 3. API Endpoint Structure

**Auth (MVP Hack)**
* `POST /api/auth/login` -> Returns user details to be stored in `localStorage` (No JWT verification for MVP).

**Hardware**
* `GET /api/hardware` -> List hardware (supports query params for sort/filter).
* `POST /api/hardware` -> Create new hardware (Admin only).
* `PUT /api/hardware/{id}` -> Update hardware / toggle "Repair" status (Admin only).

**Rentals**
* `POST /api/rentals/rent` -> Rent an item. **Strict Guard:** Fails if item status is not 'Available'. Updates hardware status to 'In Use'.
* `POST /api/rentals/return` -> Return an item. Updates hardware status to 'Available' and sets `returned_at`.
* `GET /api/rentals/my` -> Get active rentals for a specific user ID.

**Admin / AI**
* `POST /api/admin/users` -> Create a new user account.
* `POST /api/ai/seed` -> Accepts dirty JSON array. Returns cleaned data and triggers DB insert.
* `POST /api/ai/search` -> Accepts natural language string. Returns executed SQL results.

## 4. AI-Native Pipelines

### A. Semantic Search (Text-to-SQL)
**Goal:** Allow users to type "Find all broken Apple gear" and return structured table data.
**Flow:**
1.  **Input:** User toggles "Search with AI" on the UI and submits a natural language query.
2.  **Prompt Engineering:** FastAPI sends a system prompt to Gemini containing:
    * The explicit SQLite schema for the `hardware` table.
    * Strict instructions to *only* return a `SELECT` SQL statement.
    * The user's query.
3.  **Validation:** FastAPI intercepts the LLM response, strips markdown, and runs a regex/string match to ensure the query begins with `SELECT` and contains no `DROP`, `DELETE`, `UPDATE`, or `INSERT` commands.
4.  **Execution & Response:** The safe query is executed against SQLite. The resulting rows are serialized to JSON and sent back to the Vue frontend to populate the dashboard.

### B. AI-Assisted Seed Importer
**Goal:** Ingest messy, duplicate-prone legacy data and sanitize it for the DB.
**Flow:**
1.  **Input:** Admin uploads the raw JSON array to the `/api/ai/seed` endpoint.
2.  **Prompt Engineering:** FastAPI sends the raw JSON to Gemini with strict instructions to:
    * Format dates to `YYYY-MM-DD`.
    * Normalize statuses strictly to `Available`, `In Use`, or `Repair` (e.g., "Unknown" becomes "Available" with a note, or is flagged).
    * Fix typos in brands (e.g., "Appel" -> "Apple").
    * Re-index IDs to resolve collisions (e.g., the duplicate ID 4).
    * Output *only* a valid JSON array.
3.  **Pydantic Validation:** FastAPI parses the LLM's JSON response through a Pydantic model (`List[HardwareCreate]`) to guarantee schema compliance.
4.  **Database Insertion:** The validated list is bulk-inserted into the SQLite `hardware` table.