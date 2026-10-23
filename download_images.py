#!/usr/bin/env python3
"""
ATSLite Task 2 Image & File Downloader
-------------------------------------
Downloads all 467 receipt images and assignment files from the ATSLite platform.

Features:
  1. Fast Direct API Downloader (Default & Recommended):
     - Uses the platform's S3 resolution API to download all 467 images in ~15 seconds.
     - Saves files directly into the project's 'images/' folder and/or your 'Downloads' folder.
     - Automatically cleans UUID prefixes so filenames match claims_train.csv and claims_test.csv.
     - Downloads missing assignment files (README.txt, sample_submission.csv).
     - Skips already downloaded images for instant resume.
  2. Screen Control Mode (--screen):
     - Uses PyAutoGUI to physically control your mouse and screen to click through the
       Chrome list if you prefer GUI-level automation.

Usage:
  python download_images.py                   # Interactive selection (defaults to Fast API)
  python download_images.py --api             # Fast direct download without prompt
  python download_images.py --screen          # PyAutoGUI screen control clicker
"""

import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


DEFAULT_URL = (
    "https://atslite.interviewgod.ai/track/"
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJwdXJwb3NlIjoidHJhY2tpbmciLCJpbnN0YW5jZUlkIjoiMmU1YzRkZTEtOTFjMS00OTU3LThiMTMtOTFiNWZmNzRlMDQ4IiwiaWF0IjoxNzkyNTI2ODUyLCJleHAiOjE4MDgwNzg4NTJ9."
    "Q0eb-uAc-w-rxY0bVam60WhGWQtcTBkUta6m38zGSuw"
)

API_BASE = "https://atslite.interviewgod.ai/api"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def extract_token_from_url(url: str) -> str:
    """Extracts JWT token from full URL or returns string if already a token."""
    if "/track/" in url:
        return url.split("/track/")[1].split("?")[0].strip("/")
    return url.strip()


def fetch_task_data(token: str) -> dict:
    """Fetches candidate tracking metadata from ATSLite API."""
    api_url = f"{API_BASE}/track/{token}"
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_s3_url(token: str, key: str) -> str:
    """Resolves an S3 pre-signed download URL for a given attachment key."""
    resolve_url = f"{API_BASE}/track/{token}/uploads/resolve?key={urllib.parse.quote(key)}"
    req = urllib.request.Request(resolve_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["url"]


def download_single_file(s3_url: str, dest_paths: list[Path]) -> int:
    """Downloads content from S3 URL and saves to target paths."""
    req = urllib.request.Request(s3_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read()
    
    for path in dest_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
    return len(content)


def run_direct_api_downloader(
    token: str,
    output_dir: Path,
    downloads_dir: Path = None,
    max_workers: int = 10,
    download_all: bool = True
):
    """
    Direct high-speed parallel downloader using ATSLite's API.
    Downloads all images and files cleanly into output_dir and downloads_dir.
    """
    print("\n" + "=" * 65)
    print("🚀 ATSLite Fast Parallel Image Downloader")
    print("=" * 65)
    print(f"Fetching task attachments from platform...")
    
    try:
        data = fetch_task_data(token)
    except Exception as e:
        print(f"❌ Failed to fetch task metadata: {e}")
        return

    task = data.get("current", {}).get("task", {})
    attachments = task.get("attachments", [])
    if not attachments:
        print("❌ No attachments found for this task!")
        return

    # Categorize attachments
    image_attachments = []
    other_attachments = []
    for att in attachments:
        label = att.get("label", "").lower()
        if label.endswith((".jpg", ".jpeg", ".png", ".webp")):
            image_attachments.append(att)
        else:
            other_attachments.append(att)

    print(f"✅ Found {len(image_attachments)} images and {len(other_attachments)} assignment files.")
    print(f"📁 Destination Folder 1: {output_dir.resolve()}")
    if downloads_dir:
        print(f"📁 Destination Folder 2: {downloads_dir.resolve()} (System Downloads)")

    # Prepare download queue
    targets_to_download = list(image_attachments)
    if download_all:
        targets_to_download.extend(other_attachments)

    output_dir.mkdir(parents=True, exist_ok=True)
    if downloads_dir:
        downloads_dir.mkdir(parents=True, exist_ok=True)

    # Process items
    to_process = []
    already_done = 0

    for item in targets_to_download:
        raw_key = item["key"]
        raw_label = item.get("label", "")
        # Raw file name from S3 key (e.g. 95627cb0-361c-4599-93f9-79473d6d1a35-IMG-20260610-WA0001.jpg)
        key_filename = raw_key.split("/")[-1]
        
        # Clean label filename (e.g. IMG-20260610-WA0001.jpg)
        clean_filename = raw_label.replace("images/", "").strip("/")
        
        # We save under both clean name (to match CSVs directly) and UUID name (if different)
        dest_paths = [output_dir / clean_filename]
        if key_filename != clean_filename:
            dest_paths.append(output_dir / key_filename)
            
        if downloads_dir:
            dest_paths.append(downloads_dir / key_filename)

        # Check if already downloaded
        if all(p.exists() and p.stat().st_size > 0 for p in dest_paths):
            already_done += 1
            continue

        to_process.append((item, dest_paths))

    print(f"\nStatus: {already_done} files already downloaded. {len(to_process)} remaining to download.")
    if not to_process:
        print("🎉 All files are already up-to-date!")
        return

    print(f"⚡ Downloading {len(to_process)} files using {max_workers} parallel workers...\n")

    completed = 0
    total = len(to_process)
    errors = []

    def _worker(item_info):
        att, paths = item_info
        k = att["key"]
        try:
            url = resolve_s3_url(token, k)
            sz = download_single_file(url, paths)
            return True, att.get("label"), sz
        except Exception as exc:
            return False, att.get("label"), str(exc)

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_worker, item): item for item in to_process}
        for fut in as_completed(futures):
            success, label, result = fut.result()
            completed += 1
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / speed if speed > 0 else 0

            status_str = f"[{completed}/{total}] ({completed*100//total}%) | {speed:.1f} files/s | ETA: {int(eta)}s"
            if success:
                print(f"\r{status_str} - Downloaded: {label[:40]:<40}", end="", flush=True)
            else:
                errors.append((label, result))
                print(f"\n⚠️ Error downloading {label}: {result}")

    total_time = time.time() - start_time
    print(f"\n\n{'=' * 65}")
    print(f"🎉 Download complete in {total_time:.1f} seconds!")
    print(f"✅ Successfully downloaded {completed - len(errors)} files.")
    if errors:
        print(f"⚠️ {len(errors)} errors encountered.")
    print(f"📁 Files saved to: {output_dir.resolve()}")
    if downloads_dir:
        print(f"📁 Files also copied to: {downloads_dir.resolve()}")
    print("=" * 65 + "\n")


def run_screen_control_clicker():
    """
    PyAutoGUI Screen Automation Mode:
    Takes control of the screen to click image items in the Chrome browser.
    """
    try:
        import pyautogui
    except ImportError:
        print("❌ 'pyautogui' package is required for screen control mode.")
        print("Run: pip install pyautogui")
        return

    pyautogui.FAILSAFE = True
    print("\n" + "=" * 65)
    print("🖥️ ATSLite PyAutoGUI Screen Control Mode")
    print("=" * 65)
    print("IMPORTANT SAFETY RULE:")
    print("  To emergency stop at ANY TIME, slam your mouse into ANY CORNER of your screen!")
    print("-" * 65)
    print("Instructions:")
    print("  1. Make sure Chrome is open to the tracking page.")
    print("  2. Scroll down until the '467 photos' section is visible.")
    print("  3. Click to open the dropdown so the list of image links is visible.")
    print("  4. You have 5 seconds to switch to your Chrome window...")
    print("-" * 65)

    for i in range(5, 0, -1):
        print(f"Switch to Chrome in {i} seconds...", end="\r", flush=True)
        time.sleep(1)

    print("\n🚀 Starting screen control automation!")
    print("Moving mouse to current pointer position and clicking...")
    
    # Starting coordinate: user places mouse on the first image link
    current_x, current_y = pyautogui.position()
    print(f"Using mouse start position: ({current_x}, {current_y})")
    
    # Each item button has a height of ~44px
    item_height = 44
    clicks = 0
    max_clicks = 467

    try:
        for i in range(max_clicks):
            print(f"Clicking item #{i+1} at ({current_x}, {current_y})...")
            pyautogui.click(current_x, current_y)
            clicks += 1
            
            # Wait for S3 resolve and Chrome download trigger
            time.sleep(1.0)
            
            # Scroll down slightly inside container
            pyautogui.scroll(-70)
            time.sleep(0.2)
            
    except pyautogui.FailSafeException:
        print("\n🛑 Fail-safe triggered! Mouse moved to screen corner. Stopping.")
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user.")

    print(f"\nFinished screen clicks. Total clicks: {clicks}.")


def main():
    parser = argparse.ArgumentParser(description="Download images and files from ATSLite")
    parser.add_argument("--url", default=DEFAULT_URL, help="ATSLite tracking URL or JWT token")
    parser.add_argument("--api", action="store_true", help="Run high-speed API downloader directly")
    parser.add_argument("--screen", action="store_true", help="Run PyAutoGUI screen control clicker")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "images"), help="Folder to save images")
    parser.add_argument("--downloads", action="store_true", default=True, help="Also save to user Downloads folder")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent download threads")

    args = parser.parse_args()

    token = extract_token_from_url(args.url)
    output_dir = Path(args.output_dir)
    downloads_dir = Path.home() / "Downloads" if args.downloads else None

    if args.screen:
        run_screen_control_clicker()
    elif args.api:
        run_direct_api_downloader(
            token=token,
            output_dir=output_dir,
            downloads_dir=downloads_dir,
            max_workers=args.workers,
            download_all=True
        )
    else:
        # If run directly without flags, ask user or default to Fast API
        print("\nChoose Download Method:")
        print("  [1] Fast Parallel API Downloader (Recommended - all 467 images in ~20s, 0 mouse hijacking)")
        print("  [2] PyAutoGUI Screen Control Clicker (Takes control of mouse & clicks inside Chrome)")
        try:
            choice = input("Enter choice [1 or 2] (default 1): ").strip()
            if not choice:
                choice = "1"
        except (EOFError, KeyboardInterrupt):
            choice = "1"

        if choice == "2":
            run_screen_control_clicker()
        else:
            run_direct_api_downloader(
                token=token,
                output_dir=output_dir,
                downloads_dir=downloads_dir,
                max_workers=args.workers,
                download_all=True
            )



if __name__ == "__main__":
    main()
