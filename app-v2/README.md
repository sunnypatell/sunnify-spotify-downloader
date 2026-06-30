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

## Quick Start

### Backend

```bash
cd backend-python
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

API available at: http://127.0.0.1:8000
Docs at: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend-react
pnpm i
pnpm dev
```

App available at: http://localhost:3000
