from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.health import router as health_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic Revenue Recovery System for Failed and Abandoned Post-Checkout Transactions"
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


@app.get("/")
def root():
    return {
        "message": "Welcome to Razorpay AI Revenue Recovery Agent API",
        "docs": "/docs",
        "health": "/health"
    }
