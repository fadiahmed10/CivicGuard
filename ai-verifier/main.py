from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from models import ReportInput, VerificationResult
from config import settings
from ai_analyzer import verify_report
import traceback

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="AnonSentra AI Verifier", description="AI Legitimacy check microservice")

# Add Rate Limiter Exception Handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - Fixed: cannot use allow_origins=["*"] with allow_credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add SlowAPI middleware
app.add_middleware(SlowAPIMiddleware)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AnonSentra AI Verifier"}

@app.post("/verify-report", response_model=VerificationResult)
@limiter.limit(settings.RATE_LIMIT)
async def verify(request: Request, report: ReportInput):
    """
    Analyzes an incoming report using Google Gemini to determine legitimacy.
    Returns a score 0-100, classification, and reasoning.
    """
    try:
        # Pass data to the AI analyzer
        result = await verify_report(
            location=report.location, 
            description=report.description, 
            image_url=report.image_url
        )
        return result
    except Exception as e:
        print(f"Error processing report: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error during AI verification")
