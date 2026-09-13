import json
import os

import numpy as np
import faiss

from .retrieval import MODEL_NAME
from .youtube import fetch_all_trusted_videos, get_api_key, load_trusted_channels, resolve_all_channel_ids

VIDEO_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "video_index.json")


def refresh_video_index(path: str = VIDEO_INDEX_PATH, per_channel_max: int = 50) -> list[dict]:
    """Fetch the current video list for every trusted channel and write it
    to disk. Meant to be run periodically (cron / scheduled job), never per
    user request -- see scripts/refresh_video_index.py. Raises if no API
    key is configured or no channel resolves, since a silent no-op refresh
    would leave a stale index in place without saying so."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not set; cannot refresh the video index")
    channel_id_map = resolve_all_channel_ids(load_trusted_channels(), api_key)
    if not channel_id_map:
        raise RuntimeError("No trusted channel handles resolved; refusing to overwrite the video index")
    videos = fetch_all_trusted_videos(channel_id_map, api_key, per_channel_max=per_channel_max)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    return videos


def load_video_index(path: str = VIDEO_INDEX_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class VideoIndex:
    """Semantic search over a locally cached video list -- no live YouTube
    API call per lookup, unlike src.youtube.search_trusted_videos. Mirrors
    src.retrieval.CorpusIndex's approach (fastembed + faiss, score the
    whole set before truncating) for the same reasons: this index is small
    (one refresh cycle's worth of trusted-channel uploads), so there's no
    cost to scoring everything, and truncating first risks the same class
    of bug fixed in CorpusIndex.search."""

    def __init__(self, videos: list[dict], model_name: str = MODEL_NAME):
        self.videos = videos
        self.model = None
        self.index = None
        if not videos:
            return
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name)
        texts = [self._video_text(v) for v in videos]
        embeddings = np.array(list(self.model.embed(texts)), dtype="float32")
        faiss.normalize_L2(embeddings)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    @staticmethod
    def _video_text(video: dict) -> str:
        parts = [video.get("title", ""), video.get("description", "")]
        return " ".join(p for p in parts if p)

    def search(self, query: str, top_k: int = 6, per_channel_limit: int = 2, min_score: float = 0.0) -> list[dict]:
        """Return up to top_k videos best matching query, capping how many
        can come from any single channel (per_channel_limit) so the results
        aren't dominated by one channel's especially on-topic back-catalog."""
        if not self.videos or self.index is None:
            return []
        query_vec = np.array(list(self.model.embed([query])), dtype="float32")
        faiss.normalize_L2(query_vec)
        scores, idxs = self.index.search(query_vec, len(self.videos))

        ranked = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or score < min_score:
                continue
            ranked.append((float(score), self.videos[idx]))
        ranked.sort(key=lambda pair: pair[0], reverse=True)

        results = []
        per_channel_count: dict[str, int] = {}
        for score, video in ranked:
            channel_id = video.get("channel_id") or video.get("source_handle") or ""
            if per_channel_count.get(channel_id, 0) >= per_channel_limit:
                continue
            per_channel_count[channel_id] = per_channel_count.get(channel_id, 0) + 1
            results.append(video)
            if len(results) >= top_k:
                break
        return results
