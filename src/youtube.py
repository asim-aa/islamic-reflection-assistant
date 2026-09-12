import json
import os

import requests

TRUSTED_CHANNELS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trusted_channels.json")
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def load_trusted_channels(path: str = TRUSTED_CHANNELS_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_api_key() -> str | None:
    return os.environ.get("YOUTUBE_API_KEY") or None


def resolve_channel_id(handle: str, api_key: str, timeout: int = 10) -> str | None:
    """Resolve a @handle to its channel_id. Returns None if the handle doesn't
    resolve to a real channel -- callers should skip that channel rather than
    guess, since a wrong handle failing to resolve is a safe failure mode."""
    resp = requests.get(
        f"{YOUTUBE_API_BASE}/channels",
        params={"part": "id", "forHandle": handle.lstrip("@"), "key": api_key},
        timeout=timeout,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    return items[0]["id"] if items else None


def resolve_all_channel_ids(channels: list[dict], api_key: str) -> dict[str, str]:
    """Given trusted_channels.json entries, return {handle: channel_id} for
    every handle that resolves. Entries that already carry a channel_id are
    used as-is without another API call; entries whose handle fails to
    resolve (typo, renamed, deleted) are silently skipped."""
    resolved = {}
    for channel in channels:
        handle = channel["handle"]
        if channel.get("channel_id"):
            resolved[handle] = channel["channel_id"]
            continue
        try:
            channel_id = resolve_channel_id(handle, api_key)
        except Exception:
            continue
        if channel_id:
            resolved[handle] = channel_id
    return resolved


def search_channel_videos(query: str, channel_id: str, api_key: str, max_results: int = 2, timeout: int = 10) -> list[dict]:
    resp = requests.get(
        f"{YOUTUBE_API_BASE}/search",
        params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "channelId": channel_id,
            "maxResults": max_results,
            "order": "relevance",
            "safeSearch": "strict",
            "key": api_key,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    results = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        results.append(
            {
                "video_id": video_id,
                "title": snippet.get("title"),
                "channel_title": snippet.get("channelTitle"),
                "channel_id": snippet.get("channelId"),
                "thumbnail": (snippet.get("thumbnails", {}).get("medium") or {}).get("url"),
                "published_at": snippet.get("publishedAt"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return results


def search_trusted_videos(
    query: str,
    channel_id_map: dict[str, str],
    api_key: str,
    per_channel: int = 2,
    max_total: int = 6,
    timeout: int = 10,
) -> list[dict]:
    """Search only within the given {handle: channel_id} allowlist. Every
    trusted channel gets its own search.list call (channelId constrains
    results to that channel server-side, so a wrong or irrelevant video
    can't slip in from elsewhere) -- costs more quota than one broad search,
    but a channel that fails or returns nothing is simply skipped rather
    than silently backfilled from untrusted sources."""
    results = []
    for handle, channel_id in channel_id_map.items():
        try:
            hits = search_channel_videos(query, channel_id, api_key, max_results=per_channel, timeout=timeout)
        except Exception:
            continue
        for hit in hits:
            hit["source_handle"] = handle
            results.append(hit)
    return results[:max_total]
