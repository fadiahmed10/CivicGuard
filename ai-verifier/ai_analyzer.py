import google.generativeai as genai
import json
import httpx
import traceback
from io import BytesIO
from typing import Optional
from PIL import Image
from config import settings
from models import Classification, VerificationResult

# Initialize Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# Use the latest text and multimodal models
TEXT_MODEL_NAME = 'gemini-1.5-flash'
VISION_MODEL_NAME = 'gemini-1.5-flash'

def _get_classification(score: int) -> Classification:
    if score < 40:
        return Classification.LIKELY_SPAM
    elif score < 70:
        return Classification.NEEDS_REVIEW
    else:
        return Classification.LIKELY_LEGITIMATE

async def analyze_text(location: str, description: str) -> dict:
    prompt = f"""
    You are an AI analyst for an anonymous drug-reporting system.
    Evaluate the following report for legitimacy.
    
    Location: {location}
    Description: {description}
    
    Assign a legitimacy score from 0 to 100 based on:
    - Detail: Is the description specific and meaningful? (Higher score)
    - Vagueness: Is it too short or lacking context? (Lower score)
    - Spam/Trolling: Is it obvious spam, gibberish, or completely unrelated to illegal drug activity? (Score < 20)
    
    Return EXACTLY a JSON object with this structure (no markdown fences, no extra text):
    {{
        "text_score": <int between 0 and 100>,
        "reasoning": [
            "<Point 1 - e.g., 'Description lacks specific details'>",
            "<Point 2>"
        ]
    }}
    """
    
    model = genai.GenerativeModel(TEXT_MODEL_NAME)
    response = await model.generate_content_async(prompt)
    
    try:
        # Strip potential markdown formatting if model didn't listen
        clean_text = response.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        return json.loads(clean_text)
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return {"text_score": 30, "reasoning": ["Failed to analyze text using AI model."]}

async def analyze_image(image_url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            
        img = Image.open(BytesIO(response.content))
        
        prompt = """
        Analyze this image for an anonymous drug reporting system.
        Does it contain evidence of illegal drug activity, suspicious exchanges, or related paraphernalia?
        Return EXACTLY a JSON object with this structure (no extra text):
        {
            "image_score": <int between 0 and 100>,
            "reasoning": ["<Point 1>"]
        }
        """
        
        model = genai.GenerativeModel(VISION_MODEL_NAME)
        response = await model.generate_content_async([prompt, img])
        
        clean_text = response.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        return json.loads(clean_text)
        
    except Exception as e:
        print(f"Image analysis failed: {e}")
        traceback.print_exc()
        return {"image_score": 50, "reasoning": ["Failed to analyze image or image was inaccessible."]}


async def verify_report(location: str, description: str, image_url: Optional[str] = None) -> VerificationResult:
    # 1. Pre-flight checks (fast rejections)
    if len(description.strip()) < settings.MIN_DESCRIPTION_LENGTH:
        return VerificationResult(
            legitimacy_score=10,
            classification=Classification.LIKELY_SPAM,
            reasoning=[f"Description is too short (under {settings.MIN_DESCRIPTION_LENGTH} characters)."]
        )
        
    # 2. AI Text Analysis
    text_result = await analyze_text(location, description)
    final_score = text_result.get("text_score", 30)
    reasons = text_result.get("reasoning", [])
    
    # 3. AI Image Analysis (if provided)
    if image_url:
        image_result = await analyze_image(image_url)
        img_score = image_result.get("image_score", 50)
        reasons.extend(image_result.get("reasoning", []))
        
        # Weighted score: 70% text, 30% image
        final_score = int((final_score * 0.7) + (img_score * 0.3))
        
    # Cap score boundaries
    final_score = max(0, min(100, final_score))
    
    return VerificationResult(
        legitimacy_score=final_score,
        classification=_get_classification(final_score),
        reasoning=reasons
    )
