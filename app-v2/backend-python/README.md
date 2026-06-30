# Sunnify Backend (Python)

FastAPI backend for Sunnify - Spotify & YouTube music downloader.

## Setup

### First Time Setup

**1. Install Binaries Dependencies**  

```bash
chmod +x ./scripts/*.sh
./scripts/01-setup.sh
```

**2. Create Python Virtual Environment**  

```bash
# create virtual environment
python3 -m venv .venv
# activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
# install dev dependencies
pip install pip-tools
# install dependencies
pip-sync requirements.txt
```

**3. Configure Environment Variables**
Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

<!-- Edit `.env` with your Spotify API credentials:
- Get them from https://developer.spotify.com/dashboard -->

### Run Server

```bash
# activate virtual environment
source .venv/bin/activate
# launch main fil
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# to stop the server
# ctrl + c
# deactivate virtual environment
deactivate
```

The Server listens on `http://localhost:8000`.  
The Server expose OpenAPI docs at `http://localhost:8000/docs`.

### Update Dependencies

```bash
# activate virtual environment
source .venv/bin/activate
# update dependencies
# - single
pip-compile --upgrade-package fastapi # fastapi is the name of the package
# - all
pip-compile --upgrade
```

## Project Structure

```
backend-python/
├── main.py               # server entrypoint
├── routes/*.py           # FastAPI routes endpoints
├── models/*.py           # Pydantic models for API
├── core/classes/*.py     # Core classes
├── core/singleton/*.py   # Singleton instances
├── .env.example          # Environment variables example
├── requirements.in       # Dependencies definition
├── requirements.txt      # Dependencies lock file
└── README.md
```