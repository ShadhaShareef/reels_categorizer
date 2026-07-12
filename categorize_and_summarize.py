"""
Step 3: Ask Gemini (free API tier) to categorize each reel and produce a
short summary + main points, based on its transcript.

Get a free API key at https://aistudio.google.com/apikey (no credit card needed),
then:
    export GEMINI_API_KEY=your-key-here

Usage:
    python categorize_and_summarize.py
"""
import json
import os
import re
import time
from pathlib import Path

import requests
from tqdm import tqdm

MANIFEST_PATH = Path("output/manifest.json")
MODEL = "gemini-3.1-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

PROMPT_TEMPLATE = """You analyze Instagram reels using their transcript and caption. Given the \
content below, respond with ONLY a JSON object (no markdown fences, no extra text before or after) \
with these fields:

{{
  "category": "short category name, e.g. Fitness, Recipes, Finance Tips, Comedy, Travel, Productivity",
  "summary": "1-2 sentence summary of what this reel is about",
  "main_points": ["short bullet point", "short bullet point"]
}}

Pick the category based on the actual content, don't force it into a generic bucket.
main_points should be 2-5 short, concrete takeaways (not vague restatements of the summary).
If the transcript is too short/unclear, rely more on the caption. If both are sparse, still make your best guess.
If any links are given, go there and give a summary of that too, also attach the link.
If the caption/transcript tells us to comment for any details, then attach their id/reel link.

If it is a cooking video, give the recipe and the reel link

Caption: {caption}

Transcript:
{transcript}
"""


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(match.group(0))


def call_gemini(api_key: str, transcript: str, caption: str, rid: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(transcript=transcript[:6000], caption=caption[:500] or "(none)")
    for attempt in range(5):
        resp = requests.post(
            f"{API_URL}?key={api_key}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=60,
        )
        if resp.status_code != 429:
            break
        wait = 2 ** attempt * 5
        print(f"  Rate limited, retrying in {wait}s (attempt {attempt+1}/5)...")
        time.sleep(wait)
    else:
        print(f"  Still rate limited after 5 retries — hit daily quota or key is exhausted.")
        print(f"  Get a new free key at https://aistudio.google.com/apikey, then restart.")
        print(f"  Sleeping 300s before continuing in case quota resets...")
        time.sleep(300)
    resp.raise_for_status()
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return extract_json(raw_text)


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set GEMINI_API_KEY first. Get a free key at https://aistudio.google.com/apikey\n"
            "  export GEMINI_API_KEY=your-key-here"
        )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    pending = [
        (rid, entry) for rid, entry in manifest.items()
        if entry.get("transcribed") and not entry.get("categorized")
    ]
    print(f"Categorizing {len(pending)} reels using Gemini ({MODEL})...")

    for rid, entry in tqdm(pending):
        transcript_path = Path(entry["transcript_path"])
        transcript = transcript_path.read_text(encoding="utf-8")
        caption = entry.get("caption", "")
        if not transcript.strip() and not caption.strip():
            entry["category"] = "Uncategorized"
            entry["summary"] = "No speech or caption text detected in this reel."
            entry["main_points"] = []
            entry["categorized"] = True
            continue

        try:
            result = call_gemini(api_key, transcript, caption, rid)
        except Exception as e:
            print(f"  Failed on {rid}: {e}")
            continue

        entry["category"] = result.get("category", "Uncategorized")
        entry["summary"] = result.get("summary", "")
        entry["main_points"] = result.get("main_points", [])
        entry["categorized"] = True
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        time.sleep(4)

    print("Done.")


if __name__ == "__main__":
    main()
