# Railway (frontend + backend)

## Frontend service

**Build:** set the service root directory to `frontend`, Dockerfile `frontend/Dockerfile`.

**Networking:** generate a public domain; when Railway asks for the app port, use **80** (nginx listens on `$PORT`, default 80).

**Single variable: `BACKEND_UPSTREAM`**

Use **one** of these:

| Value | When to use |
|--------|-------------|
| `https://your-backend-xxxx.up.railway.app` | Easiest: the same public URL as your backend service (no trailing `/`). |
| `your-backend-service.railway.internal:8000` | Private networking; `your-backend-service` must match the **exact** backend service name in the Railway project. Use port **8000** if Uvicorn listens on 8000. |

Locally and with Docker Compose you **do not need to set** anything—the image defaults to `backend:8000`.

Remove the legacy variable **`BACKEND_PUBLIC_URL`** if you added it earlier; everything goes through **`BACKEND_UPSTREAM`**.

## Backend service

- Build from the repository **root** `Dockerfile`; set the public port in the dashboard to **8000** (or match whatever `PORT` the container uses).
- Variables: `GEMINI_*`, admin bootstrap, etc., as in `.env.example`.
- SQLite: consider attaching a **volume** at `/app/data` so the database survives redeploys.

## Backend service name

The public hostname `…up.railway.app` is **not** the same as `something.railway.internal`. For private DNS, the hostname segment must match the **service name** shown in the Railway dashboard.
