#!/usr/bin/env python3
"""
Test OpenAI API endpoint and .env loading.
Run from sailcast/ with venv active: python scripts/test_openai.py
(Or: pip install -r requirements.txt then python scripts/test_openai.py)
"""
import os
import sys
from pathlib import Path

# Load .env from sailcast/ (parent of scripts/)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
ENDPOINT = "https://api.openai.com/v1/chat/completions"


def main():
    if not OPENAI_API_KEY or OPENAI_API_KEY.strip() in ("", "your-key-here"):
        print("ERROR: OPENAI_API_KEY not set or still placeholder.")
        print("  In sailcast/.env set: OPENAI_API_KEY=sk-proj-...")
        return 1
    print(f"OPENAI_API_KEY loaded (length {len(OPENAI_API_KEY)})")
    print(f"OPENAI_MODEL={OPENAI_MODEL}")
    print(f"Calling {ENDPOINT} ...")

    try:
        resp = httpx.post(
            ENDPOINT,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENAI_MODEL,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 10,
            },
            timeout=30.0,
        )
    except Exception as e:
        print(f"ERROR: Request failed: {e}")
        return 1

    if resp.status_code != 200:
        print(f"ERROR: HTTP {resp.status_code}")
        print(resp.text[:500])
        return 1

    data = resp.json()
    content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    print(f"SUCCESS: API returned: {content!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
