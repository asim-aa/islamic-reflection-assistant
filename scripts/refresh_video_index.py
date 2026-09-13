"""Refresh data/video_index.json with each trusted channel's current
uploads, using the cheap playlistItems.list endpoint (~1 quota unit per
channel) instead of a live search.list call (100 units) per user request.

Run this periodically (cron, or a scheduled CI job) so the running app's
"related videos" feature searches a local, pre-built index rather than
calling the YouTube API on every single user submission -- at 100 quota
units per search.list call across 5 channels, live per-request search
would exhaust a default 10,000-unit daily quota after roughly 20 total
uses across all users.

Usage:
    python scripts/refresh_video_index.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402

from src.video_index import VIDEO_INDEX_PATH, refresh_video_index  # noqa: E402

load_dotenv()


def main() -> int:
    try:
        videos = refresh_video_index()
    except RuntimeError as exc:
        print(f"[error] {exc}")
        return 1

    by_channel: dict[str, int] = {}
    for video in videos:
        handle = video.get("source_handle", "?")
        by_channel[handle] = by_channel.get(handle, 0) + 1

    print(f"Wrote {len(videos)} videos to {VIDEO_INDEX_PATH}:")
    for handle, count in sorted(by_channel.items()):
        print(f"  {handle}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
