"""Resolve every @handle in data/trusted_channels.json to its real YouTube
channel_id, and write the result back into that file.

Run this once after setting YOUTUBE_API_KEY, and again any time you add a
new channel to the list. Doing this ahead of time means the running app
never needs to spend API quota re-resolving handles on every session --
it just reads channel_id directly from the file.

A handle that fails to resolve (typo, channel renamed or deleted) is left
as channel_id: null and printed as a warning -- fix the handle by hand and
re-run, rather than guessing at the channel_id.

Usage:
    python scripts/resolve_channels.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402

from src.youtube import TRUSTED_CHANNELS_PATH, get_api_key, resolve_channel_id  # noqa: E402

load_dotenv()


def main() -> int:
    api_key = get_api_key()
    if not api_key:
        print("YOUTUBE_API_KEY is not set (check your .env). Nothing to do.")
        return 1

    with open(TRUSTED_CHANNELS_PATH, "r", encoding="utf-8") as f:
        channels = json.load(f)

    changed = False
    failures = []
    for channel in channels:
        handle = channel["handle"]
        print(f"Resolving {handle} ({channel.get('name', '?')})...")
        try:
            channel_id = resolve_channel_id(handle, api_key)
        except Exception as exc:
            print(f"  [error] {exc}")
            failures.append(handle)
            continue
        if channel_id:
            print(f"  -> {channel_id}")
            if channel.get("channel_id") != channel_id:
                channel["channel_id"] = channel_id
                changed = True
        else:
            print(f"  [not found] '{handle}' did not resolve to a channel -- check the handle is correct")
            failures.append(handle)

    if changed:
        with open(TRUSTED_CHANNELS_PATH, "w", encoding="utf-8") as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\nUpdated {TRUSTED_CHANNELS_PATH}.")
    else:
        print("\nNo changes needed.")

    if failures:
        print(f"\nCould not resolve: {', '.join(failures)}. Fix these handles by hand and re-run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
