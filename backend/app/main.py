from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import Base, engine, SessionLocal
from app.data.generate import generate_dataset
from app.models.failed_payment import FailedPayment
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.api.payments import router as payments_router
from app.api.policy import router as policy_router
from app.api.eval import router as eval_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist and database has initial dataset
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(FailedPayment).count() == 0:
            generate_dataset(seed=settings.RANDOM_SEED, wipe_db=False)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    description="""
# Razorpay AI Revenue Recovery Agent — API Documentation
**Track 3 (AI Revenue Recovery) — Razorpay AI Buildathon**

### Core Architectural Features:
- **LLM Classification & Drafter**: Empathic, context-aware recovery copy with zero ground-truth data leakage.
- **Deterministic Policy Engine**: 7 hard gates enforcing customer protection, fatigue stopping rules, and anti-spam restraint.
- **Razorpay Test Mode Integration**: Automated 1-click test payment link creation with idempotency guards.
- **Real-Time Streaming**: Server-Sent Events (SSE) broadcasting live recovery transitions to the dashboard.
- **What-If Policy Simulation**: Instant parameter tuning without re-calling LLM endpoints.
- **Honest Benchmarking**: Seed-locked counterfactual comparison against zero-intervention baseline.
""",
    openapi_tags=[
        {"name": "System Health", "description": "Liveness and system status probes"},
        {"name": "Recovery Runs & Live Decision Stream", "description": "Trigger batches, stream live SSE transitions, and inspect exceptions"},
        {"name": "Payment Audit Trails", "description": "Tamper-evident audit records and full attempt histories"},
        {"name": "Deterministic Policy Engine & What-If Simulation", "description": "Live thresholds and what-if parameter simulation"},
        {"name": "Evaluation & Benchmark Metrics", "description": "Pitch metrics, uplift tables, and honest limitations"},
    ]
)

# Configure CORS for frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health_router)
app.include_router(runs_router)
app.include_router(payments_router)
app.include_router(policy_router)
app.include_router(eval_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Razorpay AI Revenue Recovery Agent API",
        "docs": "/docs",
        "health": "/health"
    }
