# Sunnify Redesign

Modern React + Python FastAPI rewrite of Sunnify with type-safe APIs.

## Architecture

```
┌──────────────────────────────┐
│   React + TypeScript         │
│   (Frontend) - Port 3000     │
└────────────────┬─────────────┘
                 │ HTTP REST API
┌────────────────▼─────────────┐
│   FastAPI (Backend)          │
│   (Python) - Port 8000       │
└──────────────────────────────┘
```
