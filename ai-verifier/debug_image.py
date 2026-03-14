import asyncio
import google.generativeai as genai
from PIL import Image
import httpx
from io import BytesIO

async def test():
    api_key = "AIzaSyAKBukgd6-ZuMIBLXVeYYxhLcbAG5tQBUM"
    genai.configure(api_key=api_key)
    model_name = "gemini-1.5-flash"
    image_url = "https://images.unsplash.com/photo-1584483766114-2cea6f969eb2?q=80&w=1000"
    
    print(f"Downloading image from {image_url}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)
        response.raise_for_status()
    
    print("Opening image...")
    img = Image.open(BytesIO(response.content))
    
    print(f"Calling Gemini ({model_name})...")
    model = genai.GenerativeModel(model_name)
    prompt = "Analyze this image. What do you see?"
    response = await model.generate_content_async([prompt, img])
    print(f"Response: {response.text}")

if __name__ == '__main__':
    asyncio.run(test())
