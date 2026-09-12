import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        api_key=os.environ.get("LLM_API_KEY", "dummy-key"),
        timeout=float(os.environ.get("LLM_TIMEOUT_SECONDS", "120")),
    )


def get_model() -> str:
    return os.environ.get("LLM_MODEL", "openai/gpt-oss-20b")
