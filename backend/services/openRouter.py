import os
import requests
from dotenv import load_dotenv
import logging
import time
import json
import re

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def chat_with_openrouter(prompt: str, model_id: str,input_filename: str, file_size=None, page_count=None) -> str:
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
        ],
        "reasoning": { "enabled": False }
    }

    start_time = time.time()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=data
    )
    # logger.info(f"OpenRouter raw text : {response.text}")
    
    # Create directory based on model_id
    model_dir = os.path.join(os.path.dirname(__file__), model_id)
    os.makedirs(model_dir, exist_ok=True)

    file_path = os.path.join(model_dir, f"{input_filename}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(response.text)

    # Use JSON-parsed response
    resp_json = response.json()
    usage = resp_json.get("usage")

   
    generation_time = round(time.time() - start_time, 2)
    log_dict = {
        "filename": input_filename,
        "model_id": model_id,
        "file_size": file_size,
        "page_count": page_count,
        "usage": usage,
        "generation_time": generation_time
    }
    logging.info(f"OpenRouter generation info: {log_dict}")

    # logging.debug(f"Returning assistant content: {response.json().get('choices', [])[0].get('message', {}).get('content', '')}")

    return response.json().get("choices", [])[0].get("message", {}).get("content", "")










    # Extract filename from assistant content
    # assistant_content = resp_json.get("choices", [])[0].get("message", {}).get("content", "")
    # if assistant_content.startswith("```"):
    #     assistant_content = assistant_content.strip("`").split("json\n", 1)[-1].rstrip("`").strip()

    # try:
    #     inner_data = json.loads(assistant_content)
    #     filename = inner_data.get("filename", "unknown")
    # except json.JSONDecodeError:
    #     match = re.search(r'"filename"\s*:\s*"([^"]+)"', assistant_content)
    #     filename = match.group(1) if match else "unknown"