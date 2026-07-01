"""Thin wrapper around the Firecrawl v1 API (search / scrape / extract)."""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("FIRECRAWL_API_KEY")
BASE_URL = "https://api.firecrawl.dev/v1"


def _headers():
    if not API_KEY:
        raise RuntimeError("FIRECRAWL_API_KEY not set (check .env)")
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _post(path, payload, retries=5):
    url = f"{BASE_URL}/{path}"
    for attempt in range(retries):
        resp = requests.post(url, headers=_headers(), json=payload, timeout=60)
        if resp.status_code == 429:
            time.sleep(min(2 ** attempt, 30))
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


def search(query: str, limit: int = 10):
    """Web search via Firecrawl's /search endpoint. Returns list of {url, title, description}."""
    data = _post("search", {"query": query, "limit": limit})
    return data.get("data", [])


def scrape(url: str, formats=None):
    """Scrape a single URL, returns markdown/html/links per requested formats."""
    formats = formats or ["markdown"]
    data = _post("scrape", {"url": url, "formats": formats})
    return data.get("data", {})


def extract(url: str, schema: dict, prompt: str = ""):
    """LLM-structured extraction from a page using a JSON schema."""
    payload = {"urls": [url], "schema": schema}
    if prompt:
        payload["prompt"] = prompt
    data = _post("extract", payload)
    return data
