"""
Step 1+2: Download reels and transcribe them in one pass.

Usage:
    python download_transcribe_cleanup.py --input saved_posts.json --format meta
    python download_transcribe_cleanup.py --input links.txt --format links
"""
import os
os.environ["PATH"] = r"C:\ffmpeg\bin" + os.pathsep + os.environ["PATH"]

import argparse
import json
import re
import subprocess
from pathlib import Path

import whisper
from tqdm import tqdm

VIDEOS_DIR = Path("videos")
TRANSCRIPTS_DIR = Path("transcripts")
MANIFEST_PATH = Path("output/manifest.json")
WHISPER_MODEL = "base"

URL_RE = re.compile(r"https?://(?:www\.)?instagram\.com/\S+")
REEL_PATH_RE = re.compile(r"instagram\.com/(?:reel|reels|p)/[\w-]+")


def is_reel_url(url: str) -> bool:
    return bool(url and REEL_PATH_RE.search(url))


def extract_entries_from_meta_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = []
    seen_urls = set()

    def walk(node):
        if isinstance(node, dict):
            label_values = node.get("label_values")
            if isinstance(label_values, list):
                url, caption = None, ""
                for lv in label_values:
                    if not isinstance(lv, dict):
                        continue
                    label = lv.get("label")
                    if label == "URL" and is_reel_url(lv.get("value")):
                        url = lv["value"]
                    elif label == "Caption":
                        caption = lv.get("value") or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    entries.append({"url": url, "caption": caption})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)

    if entries:
        return entries

    urls = set()

    def walk_loose(node):
        if isinstance(node, dict):
            for v in node.values():
                walk_loose(v)
        elif isinstance(node, list):
            for v in node:
                walk_loose(v)
        elif isinstance(node, str):
            for match in URL_RE.findall(node):
                match = match.rstrip('",)')
                if is_reel_url(match):
                    urls.add(match)

    walk_loose(data)
    return [{"url": u, "caption": ""} for u in sorted(urls)]


def extract_entries_from_links_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        {"url": line.strip(), "caption": ""}
        for line in lines if line.strip() and is_reel_url(line.strip())
    ]


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict):
    MANIFEST_PATH.parent.mkdir(exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def download_video(url: str, out_path: Path) -> bool:
    result = subprocess.run(
        ["yt-dlp", "-f", "mp4", "-o", str(out_path), url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  FAILED: {url}\n    {result.stderr.strip()[-300:]}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to saved_posts.json or links.txt")
    parser.add_argument("--format", choices=["meta", "links"], default="meta")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N reels")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    entries_in = (
        extract_entries_from_meta_json(input_path)
        if args.format == "meta"
        else extract_entries_from_links_file(input_path)
    )
    print(f"Found {len(entries_in)} reel URLs.")

    if args.limit is not None:
        entries_in = entries_in[:args.limit]
        print(f"Limiting to first {len(entries_in)} reels.")

    VIDEOS_DIR.mkdir(exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    manifest = load_manifest()

    print(f"Loading Whisper model '{WHISPER_MODEL}'...")
    model = whisper.load_model(WHISPER_MODEL)

    for i, item in enumerate(entries_in):
        url, caption = item["url"], item["caption"]
        reel_id = f"reel_{i:04d}"

        if reel_id in manifest and manifest[reel_id].get("downloaded") and manifest[reel_id].get("transcribed"):
            continue

        video_path = VIDEOS_DIR / f"{reel_id}.mp4"

        if reel_id not in manifest or not manifest[reel_id].get("downloaded"):
            print(f"[{i+1}/{len(entries_in)}] Downloading {url}")
            ok = download_video(url, video_path)
            manifest[reel_id] = {
                "url": url,
                "caption": caption,
                "downloaded": ok,
                "video_path": str(video_path) if ok else None,
            }
            save_manifest(manifest)
        else:
            ok = True

        if not ok or not manifest[reel_id].get("downloaded"):
            continue

        if manifest[reel_id].get("transcribed"):
            continue

        print(f"  Transcribing {reel_id}...")
        try:
            result = model.transcribe(str(video_path))
            text = result["text"].strip()
        except Exception as e:
            print(f"  Failed to transcribe {reel_id}: {e}")
            continue

        transcript_path = TRANSCRIPTS_DIR / f"{reel_id}.txt"
        transcript_path.write_text(text, encoding="utf-8")
        manifest[reel_id]["transcript_path"] = str(transcript_path)
        manifest[reel_id]["transcribed"] = True
        save_manifest(manifest)

    print("Done. See output/manifest.json and transcripts/")


if __name__ == "__main__":
    main()
