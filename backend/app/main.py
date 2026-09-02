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


from fastapi.responses import HTMLResponse

@app.get("/")
def root():
    return {
        "message": "Welcome to Razorpay AI Revenue Recovery Agent API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/pay/{link_id}", response_class=HTMLResponse)
def razorpay_test_checkout(link_id: str):
    """
    Renders an authentic Razorpay Test Mode Checkout Page for simulated recovery payment links.
    """
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Razorpay Payment Checkout (Test Mode)</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background-color: #0c1524;
      color: #1e293b;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }}
    .checkout-card {{
      background: #ffffff;
      width: 100%;
      max-width: 440px;
      border-radius: 12px;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
      overflow: hidden;
    }}
    .header {{
      background: linear-gradient(135deg, #0c2340 0%, #173660 100%);
      color: #ffffff;
      padding: 1.5rem;
      position: relative;
    }}
    .badge-test {{
      position: absolute;
      top: 1rem;
      right: 1rem;
      background: rgba(239, 68, 68, 0.2);
      border: 1px solid #ef4444;
      color: #fca5a5;
      font-size: 0.65rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
    }}
    .merchant-row {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}
    .merchant-avatar {{
      width: 40px;
      height: 40px;
      background: #2563eb;
      color: white;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 1.1rem;
    }}
    .merchant-name {{
      font-weight: 600;
      font-size: 0.95rem;
      color: #f8fafc;
    }}
    .merchant-sub {{
      font-size: 0.75rem;
      color: #94a3b8;
    }}
    .amount-box {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 8px;
      padding: 0.85rem 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .amount-label {{
      font-size: 0.8rem;
      color: #cbd5e1;
    }}
    .amount-val {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.25rem;
      font-weight: 700;
      color: #ffffff;
    }}
    .body {{
      padding: 1.5rem;
    }}
    .section-title {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      margin-bottom: 0.75rem;
    }}
    .method-btn {{
      width: 100%;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      padding: 0.85rem 1rem;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.5rem;
      cursor: pointer;
      transition: all 0.15s ease;
      font-size: 0.875rem;
      font-weight: 500;
      color: #1e293b;
    }}
    .method-btn:hover {{
      background: #f1f5f9;
      border-color: #cbd5e1;
    }}
    .method-btn.selected {{
      background: #eff6ff;
      border-color: #3b82f6;
      color: #1d4ed8;
    }}
    .pay-button {{
      width: 100%;
      background: #2563eb;
      color: white;
      border: none;
      padding: 0.9rem;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      margin-top: 1rem;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      transition: background 0.15s ease;
    }}
    .pay-button:hover {{
      background: #1d4ed8;
    }}
    .footer-note {{
      text-align: center;
      font-size: 0.7rem;
      color: #64748b;
      margin-top: 1.25rem;
      font-family: 'JetBrains Mono', monospace;
    }}
    .success-screen {{
      display: none;
      padding: 2.5rem 1.5rem;
      text-align: center;
    }}
    .check-icon {{
      width: 64px;
      height: 64px;
      background: #dcfce7;
      color: #16a34a;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
      margin: 0 auto 1.25rem;
    }}
  </style>
</head>
<body>
  <div class="checkout-card">
    <div class="header">
      <div class="badge-test">TEST MODE</div>
      <div class="merchant-row">
        <div class="merchant-avatar">R</div>
        <div>
          <div class="merchant-name">Razorpay Recovery Merchant</div>
          <div class="merchant-sub">Verified Business Account</div>
        </div>
      </div>
      <div class="amount-box">
        <span class="amount-label">Recovery Payment</span>
        <span class="amount-val">INR 4,499.00</span>
      </div>
    </div>

    <div class="body" id="checkout-body">
      <div class="section-title">Select Payment Option</div>
      <button class="method-btn selected" onclick="selectMethod(this)">
        <span>⚡ UPI (Google Pay, PhonePe, Paytm)</span>
        <span style="font-size: 0.75rem; color: #16a34a; font-weight: 600;">INSTANT</span>
      </button>
      <button class="method-btn" onclick="selectMethod(this)">
        <span>💳 Debit / Credit Card (Visa, Mastercard)</span>
      </button>
      <button class="method-btn" onclick="selectMethod(this)">
        <span>🏦 Netbanking (All Major Indian Banks)</span>
      </button>

      <button class="pay-button" onclick="completePayment()">
        Simulate Successful Payment (Test Mode)
      </button>

      <div class="footer-note">
        Secured by Razorpay · Link ID: {link_id}
      </div>
    </div>

    <div class="success-screen" id="success-screen">
      <div class="check-icon">✓</div>
      <h2 style="font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-bottom: 0.5rem;">Payment Successful</h2>
      <p style="font-size: 0.85rem; color: #64748b; margin-bottom: 1.5rem;">
        Your checkout recovery transaction has been captured in Razorpay Test Mode.
      </p>
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.85rem; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #334155; margin-bottom: 1.5rem; text-align: left;">
        <div><strong>Payment ID:</strong> pay_test_{link_id[-8:]}</div>
        <div style="margin-top: 0.25rem;"><strong>Status:</strong> Captured (Test Mode)</div>
        <div style="margin-top: 0.25rem;"><strong>Timestamp:</strong> Just now</div>
      </div>
      <button class="pay-button" style="background: #0f172a;" onclick="window.close()">
        Close Window
      </button>
    </div>
  </div>

  <script>
    function selectMethod(el) {{
      document.querySelectorAll('.method-btn').forEach(b => b.classList.remove('selected'));
      el.classList.add('selected');
    }}
    function completePayment() {{
      document.getElementById('checkout-body').style.display = 'none';
      document.getElementById('success-screen').style.display = 'block';
    }}
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
