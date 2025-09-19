import os
import requests
import logging
import google.generativeai as genai

from config import settings
OPENROUTER_API_KEY = settings.openrouter_api_key
genai.configure(api_key=settings.google_api_key)



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def chat_with_llm(prompt: str, model_id: str,) -> str:

    if model_id.startswith("gemini"):


        gemini_model = genai.GenerativeModel(model_id)

        response = gemini_model.generate_content(prompt)
     

        return response.text

    else:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:8000",
            "X-Title": "My FastAPI App"
        }
        data = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}]
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )

        
        return response.json().get("choices", [])[0].get("message", {}).get("content", "")
    
    