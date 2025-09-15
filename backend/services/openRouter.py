import os
import requests
from dotenv import load_dotenv
import logging
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def chat_with_openrouter(prompt: str,model_id:str):
    # logging.info(f"Sending prompt to OpenRouter: {prompt}")
    logging.info(f"Model ID: {model_id}")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://127.0.0.1:8000",  # required by OpenRouter
        "X-Title": "My FastAPI App"
    }

    data = {
        "model": model_id, 
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=data
    )
    #.json().get("choices", [])[0].get("message", {}).get("content", "")
    logging.info(f"OpenRouter response content at open code: {response.text}")
    return response.json().get("choices", [])[0].get("message", {}).get("content", "")
