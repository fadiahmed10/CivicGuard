import asyncio
import google.generativeai as genai
from PIL import Image
import httpx
from io import BytesIO
import traceback

async def test():
    api_key = "AIzaSyAKBukgd6-ZuMIBLXVeYYxhLcbAG5tQBUM"
    genai.configure(api_key=api_key)
    model_name = "models/gemini-1.5-flash"
    image_url = "https://picsum.photos/600/400"
    
    print(f"Downloading image from {image_url}...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
        
        print("Opening image...")
        img = Image.open(BytesIO(response.content))
        
        print(f"Calling Gemini ({model_name})...")
        model = genai.GenerativeModel(model_name)
        prompt = "Analyze this image. What do you see?"
        response = await model.generate_content_async([prompt, img])
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
