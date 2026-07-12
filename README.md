# Instagram Saved Reels — Categorizer & Summarizer (100% free)

Turns your exported "Saved" reels list into:
1. Downloaded videos (yt-dlp — free)
2. Transcripts (OpenAI Whisper, running locally — free)
3. AI-generated category + summary per reel (Gemini API free tier — free)
4. One Word document per category, with the main points across all reels in that category

No paid subscriptions. The only "AI" cost is Gemini's API, which has a genuinely free
tier (no credit card required) — generous enough for personal use like this. Whisper
still runs locally on your machine for transcription (also free, just uses your CPU).

---

## 0. Requirements

**Python packages:**
```bash
pip install -r requirements.txt
```

**ffmpeg** (used by Whisper and yt-dlp):
- Mac: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: https://ffmpeg.org/download.html — download the build, extract, and **add
  the `bin\` folder to your system PATH** (e.g. `C:\ffmpeg\bin`). Then verify:
  ```powershell
  where ffmpeg
  ```

**Whisper model** (downloaded automatically on first run):
- By default, Whisper downloads the `base` model (~145 MB) from OpenAI's CDN. If DNS
  resolution fails (`getaddrinfo` / name resolution error), download it manually:
  1. Download https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt
  2. Place it in `%USERPROFILE%\.cache\whisper\base.pt`
  3. If the cache directory doesn't exist, create it first.

**Gemini API key (free):**
1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click "Create API key" — no credit card, no billing setup needed for the free tier.
3. Set it as an environment variable:
   ```bash
   export GEMINI_API_KEY=your-key-here
   ```
   In PowerShell:
   ```powershell
   $env:GEMINI_API_KEY="your-key-here"
   ```

The scripts use `gemini-3.1-flash-lite` by default (free tier, 15 req/min, 500 req/day).
If that changes or you prefer another model, edit `MODEL` in `categorize_and_summarize.py`
and `generate_word_docs.py`.

---

## 1. Export your saved reels from Instagram

Settings → Accounts Center → Your information and permissions → Download your information →
select **Saved**, format **JSON**, date range **All time**.

Unzip the download. You'll get a `saved_posts.json` file (exact name/location varies).
Put it in this project folder, or pass its path with `--input`.

If your export format doesn't parse cleanly (Meta changes this occasionally), you can
skip straight to a plain text file instead: create `links.txt` with one reel URL per line,
and pass `--input links.txt --format links`.

---

## 2. Run the pipeline

Run everything end to end:

```bash
python run_pipeline.py --input saved_posts.json --format meta
```

To only process the first N reels (useful for a quick test run before committing to
your whole saved collection):

```bash
python run_pipeline.py --input saved_posts.json --format meta --limit 100
```

Or run steps individually (useful if something fails partway and you want to resume):

```bash
python download_reels.py --input saved_posts.json --format meta
python transcribe_reels.py
python categorize_and_summarize.py
python generate_word_docs.py
```

Or use the combined download+transcribe script (skips already-done reels):

```bash
python download_transcribe_cleanup.py --input saved_posts.json --format meta
python categorize_and_summarize.py
python generate_word_docs.py
```

Outputs land in `output/`:
- `output/manifest.json` — every reel with URL, transcript, category, summary
- `output/<Category Name>.docx` — one Word doc per category with an overview of
  the main points plus a per-reel breakdown

---

## Notes / limitations

- Downloading reels via `yt-dlp` works for public and your-own-saved content, but can
  break if Instagram changes its site — if downloads start failing, run
  `pip install -U yt-dlp` (it's updated frequently to keep up with IG changes).
- Whisper's `base` model is used by default for speed; edit `WHISPER_MODEL` in
  `transcribe_reels.py` and `download_transcribe_cleanup.py` to `small` or `medium`
  for better accuracy on noisy audio (bigger = slower on CPU).
- Categories are decided by the model per reel (not a fixed list), then grouped —
  edit the prompt in `categorize_and_summarize.py` if you'd rather supply a fixed
  category list (e.g. Fitness, Recipes, Finance, Comedy, Travel...).
- If you hit the free tier's rate limit a lot (lots of "Failed on ..." errors
  mentioning 429), just rerun the script later — it skips reels already marked
  `categorized: true` in `output/manifest.json`, so it resumes instead of starting over.
- Google's free tier terms can change — if `GEMINI_API_KEY` requests start failing
  outright, check https://ai.google.dev/gemini-api/docs/pricing for current limits.
