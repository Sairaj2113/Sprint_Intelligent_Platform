# Sprint Management Platform — Backend Foundation

This is the first build step for a Jira-like Sprint Management Platform
that will later feed an AI-powered Employee Contribution and Sprint
Intelligence Platform.

**Scope of this step:** backend foundation only — FastAPI app, PostgreSQL
connectivity, SQLAlchemy models for the core entities, and Alembic
migrations wiring. No frontend, Kanban board, AI/RAG features, reports,
or full CRUD APIs are implemented yet.

## 1. Prerequisites

- Docker and Docker Compose (Docker Desktop or equivalent)
- (Optional, for local/non-Docker development) Python 3.11+

## 2. Configure environment variables

Copy the example env file and adjust values if needed:

```bash
cp backend/.env.example backend/.env
```

The default values work out of the box with the bundled `docker-compose.yml`:

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/sprint_intelligence
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=sprint_intelligence
```

No production secrets are hard-coded anywhere in the repo — everything
sensitive comes from this `.env` file, which is not committed to version
control.

## 3. Start PostgreSQL and the backend

From the `project-root` directory:

```bash
docker compose up --build
```

This starts two services:

- `db` — PostgreSQL 16
- `backend` — the FastAPI app, served by Uvicorn with auto-reload

The backend will be available at:

- API root: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 4. Run database migrations

The database starts empty — no tables exist until you run Alembic
migrations. With the containers running, open a second terminal and run:

```bash
docker compose exec backend alembic revision --autogenerate -m "initial schema"
docker compose exec backend alembic upgrade head
```

The first command inspects the SQLAlchemy models under `backend/app/models/`
and generates a migration script in `backend/alembic/versions/`. The
second command applies it to the `db` service.

For subsequent model changes, repeat the same two commands to generate
and apply new migrations.

## 5. Verify everything is working

Basic liveness check:

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

Database connectivity check (run this **after** applying migrations):

```bash
curl http://localhost:8000/health/db
# {"status": "ok", "database": "connected"}
```

You can also open http://localhost:8000/docs in a browser and try these
endpoints interactively via Swagger.

## 6. Stopping the stack

```bash
docker compose down
```

Add `-v` if you also want to drop the Postgres data volume:

```bash
docker compose down -v
```

## Project layout

```
project-root/
  backend/
    app/
      main.py            # FastAPI app + /health routes
      database.py         # engine, session, Base, get_db(), check_db_connection()
      core/
        config.py         # environment-based settings
      models/              # SQLAlchemy models (one file per entity)
        employee.py
        project.py
        sprint.py
        issue.py
        issue_history.py
        test_result.py
        deployment.py
        comment.py
      schemas/             # (placeholder — Pydantic schemas come in a later step)
      routers/
        health.py
      services/            # (placeholder — business logic comes in a later step)
    alembic/
      env.py
      script.py.mako
      versions/            # generated migration scripts land here
    alembic.ini
    requirements.txt
    Dockerfile
    .env.example
  docker-compose.yml
  README.md
```

## What's intentionally NOT in this step

- React frontend / Kanban UI / drag-and-drop
- KPI engine, reports
- RAG / vector DB / LLM integration
- Full CRUD REST APIs (only `/health` and `/health/db` exist so far)
- Jira API integration

These will be layered on top of this foundation in later steps.
