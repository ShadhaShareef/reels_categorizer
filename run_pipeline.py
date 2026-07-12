"""
Runs the full pipeline: download -> transcribe -> categorize -> generate docs.

Usage:
    python run_pipeline.py --input saved_posts.json --format meta
"""
import argparse
import subprocess
import sys


def run(cmd: list[str]):
    print(f"\n=== Running: {' '.join(cmd)} ===")
    result = subprocess.run([sys.executable] + cmd)
    if result.returncode != 0:
        raise SystemExit(f"Step failed: {' '.join(cmd)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=["meta", "links"], default="meta")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N reels")
    args = parser.parse_args()

    download_cmd = ["download_transcribe_cleanup.py", "--input", args.input, "--format", args.format]
    if args.limit is not None:
        download_cmd += ["--limit", str(args.limit)]
    run(download_cmd)
    run(["categorize_and_summarize.py"])
    run(["generate_word_docs.py"])

    print("\nAll done! Check the output/ folder for your category Word docs.")


if __name__ == "__main__":
    main()
