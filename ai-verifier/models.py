from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class Classification(str, Enum):
    LIKELY_SPAM = "likely_spam"
    NEEDS_REVIEW = "needs_review"
    LIKELY_LEGITIMATE = "likely_legitimate"

class ReportInput(BaseModel):
    location: str
    description: str
    image_url: Optional[str] = None
    timestamp: str

class VerificationResult(BaseModel):
    legitimacy_score: int
    classification: Classification
    reasoning: List[str]
