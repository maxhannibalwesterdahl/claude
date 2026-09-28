# Madplan

Ugentlig madplan til eget brug: opskrifter importeret fra danske
opskriftssider, samlet indkøbsliste på tværs af ugen og Bilka-tilbud.

- [Specifikation](docs/SPEC.md)
- [Byggeplan](docs/PLAN.md) – fase 1 (opskrifter) er bygget
- [Drift](docs/drift.md) – brugere, opdatering, backup og udvikling

| Mappe | Indhold |
|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy, Alembic, SQLite. Ingredienslæser og -matcher, import, API |
| `frontend/` | SvelteKit (statisk SPA), TypeScript, PWA |
| `deploy/` | Docker Compose med Tailscale Funnel |
| `Dockerfile` | Ét image: bygger frontend og serverer den fra backend |
