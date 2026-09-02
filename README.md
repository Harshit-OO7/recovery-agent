# Razorpay AI Revenue Recovery Agent (Track 3)

An intelligent agent that recovers revenue from failed and abandoned one-time payments **after** the checkout session has ended.

## Core Architectural Principles
1. **LLM Classifies and Drafts; Policy Gates Decide**: LLM handles intent classification and message phrasing. Hard-coded deterministic rules decide when, how often, and whether to contact a customer.
2. **Comprehensive Audit Trails**: Every decision (action or restraint) writes a persistent audit record with the rationale.
3. **Restraint as a Feature**: Explicit stopping rules prevent spam and protect brand reputation.
4. **Honest Baseline Evaluation**: Recovery metrics are strictly benchmarked against an identical no-intervention baseline.
5. **Reproducible Simulation**: Customer behavior is simulated with transparent, seed-locked logic.

## Project Structure
```
recovery-agent/
  backend/
    app/
      main.py                FastAPI entrypoint
      config.py              Settings loaded from .env via pydantic-settings
      db.py                  SQLAlchemy engine, session, Base
      models/                Database models
      schemas/               Pydantic request/response schemas
      data/                  Synthetic dataset generation
      simulator/             Customer behaviour simulator
      llm/                   Provider interface + classifier + message drafting
      policy/                Deterministic policy engine
      executor/              Razorpay test-mode integration
      orchestrator/          Run loop orchestrator
      eval/                  Metrics & baseline comparison
      api/                   API route modules
    tests/                   Automated pytest suite
    requirements.txt         Pinned backend dependencies
    .env.example             Environment variable template
  frontend/                  React + TypeScript dashboard (WIP)
  docs/                      Architecture & system design documentation
  Makefile                   Task runner (install, dev, seed, run-batch, test)
  run.ps1                    PowerShell helper script for Windows
  run.sh                     Bash helper script for Unix/macOS
```

## Quickstart

### 1. Configure Environment
```bash
cd backend
cp .env.example .env
```

### 2. Install Dependencies
```bash
# Using Makefile
make install

# OR using PowerShell
.\run.ps1 install

# OR directly with pip
cd backend
pip install -r requirements.txt
```

### 3. Run FastAPI Dev Server
```bash
# Using Makefile
make dev

# OR using PowerShell
.\run.ps1 dev

# OR directly with uvicorn
cd backend
uvicorn app.main:app --reload --port 8000
```

### 4. Verify Health Check
Open your browser or run:
```bash
curl http://localhost:8000/health
```
Expected response:
```json
{"status": "ok", "app_name": "Razorpay AI Revenue Recovery Agent", "version": "0.1.0"}
```

### 5. Run Tests
```bash
make test
# OR
.\run.ps1 test
```
