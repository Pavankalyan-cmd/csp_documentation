import os
import requests
from dotenv import load_dotenv
import logging
import time
import json
import re
import google.generativeai as genai
from utils.llm_utils import log_to_excel

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def chat_with_llm(prompt: str, model_id: str, input_filename: str,file_size=None, page_count=None) -> str:
    logging.info(f"Model ID: {model_id}")

    if model_id.startswith("gemini"):
        start_time = time.time()
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        genai.configure(api_key=gemini_api_key)
        gemini_model = genai.GenerativeModel(model_id)
        response = gemini_model.generate_content(prompt)
        response_text = response.text

        model_dir = os.path.join(os.path.dirname(__file__),"model_ouput", model_id)
        os.makedirs(model_dir, exist_ok=True)
        file_path = os.path.join(model_dir, f"{input_filename}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(response_text)

        # logger.info(f"Gemini Response: {response_text}")
        usage = getattr(response, "usage_metadata", None)
        logging.info(
            f"Gemini usage for {input_filename} | file_size={file_size} | page_count={page_count}: {usage} | "
            f"time taken: {time.time() - start_time:.2f} seconds"
        )
        log_to_excel(
            filename=input_filename,
            page_count=page_count,
            file_size=file_size,
            usage=usage,
            time_taken=time.time() - start_time
        )
        return response_text

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

        start_time = time.time()
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response_text = response.text

        model_dir = os.path.join(os.path.dirname(__file__),"model_output" ,model_id)
        os.makedirs(model_dir, exist_ok=True)
        file_path = os.path.join(model_dir, f"{input_filename}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(response_text)

        # logger.info(f"OpenRouter Response: {response_text}")

        data = json.loads(response_text)

        assistant_content = data.get("choices", [])[0].get("message", {}).get("content", "")
        if assistant_content.startswith("```"):
            assistant_content = assistant_content.strip("`").split("json\n", 1)[-1].rstrip("`").strip()

        try:
            inner_data = json.loads(assistant_content)
            filename = inner_data.get("filename", "unknown")
        except json.JSONDecodeError:
            match = re.search(r'"filename"\s*:\s*"([^"]+)"', assistant_content)
            filename = match.group(1) if match else "unknown"

        usage = data.get("usage")
        logging.info(
            f"OpenRouter usage for {filename} | file_size={file_size} | page_count={page_count}: {usage} | "
            f"time taken: {time.time() - start_time:.2f} seconds"
        )
        log_to_excel(
            filename=input_filename,
            page_count=page_count,
            file_size=file_size,
            usage=usage,
            time_taken=time.time() - start_time
        )

        return data.get("choices", [])[0].get("message", {}).get("content", "")
    
    