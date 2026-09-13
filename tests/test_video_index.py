import hashlib

import numpy as np
import pytest

import src.video_index as video_index
from src.video_index import VideoIndex


class _DeterministicHashEmbedding:
    """Same no-network stand-in used in tests/test_retrieval.py, so these
    tests don't depend on downloading the real embedding model."""

    DIM = 64

    def __init__(self, model_name=None):
        pass

    def embed(self, texts):
        vectors = []
        for text in texts:
            vec = np.zeros(self.DIM, dtype="float32")
            for word in text.lower().split():
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vec[h % self.DIM] += 1.0
            if vec.sum() == 0:
                vec[0] = 1.0
            vectors.append(vec)
        return vectors


@pytest.fixture
def patch_embedder(monkeypatch):
    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", _DeterministicHashEmbedding)


def test_empty_video_list_returns_no_results(patch_embedder):
    index = VideoIndex([])
    assert index.search("anything") == []


def test_search_ranks_by_title_and_description_similarity(patch_embedder):
    # The fake embedder is exact bag-of-words hashing (no real semantics),
    # so the query must share literal words with the intended match and
    # none with the distractor for this to be a meaningful assertion.
    videos = [
        {"video_id": "v1", "title": "loneliness isolation comfort", "description": "", "channel_id": "UCA"},
        {"video_id": "v2", "title": "fasting ramadan rules", "description": "", "channel_id": "UCB"},
    ]
    index = VideoIndex(videos)
    results = index.search("loneliness isolation comfort", top_k=2, min_score=0.0)
    assert results[0]["video_id"] == "v1"


def test_search_caps_results_per_channel(patch_embedder):
    videos = [
        {"video_id": f"v{i}", "title": "anxiety worry fear stress", "description": "", "channel_id": "UCA"}
        for i in range(5)
    ]
    videos += [{"video_id": "other", "title": "anxiety worry fear stress", "description": "", "channel_id": "UCB"}]
    index = VideoIndex(videos)
    results = index.search("anxiety worry fear stress", top_k=6, per_channel_limit=2, min_score=0.0)
    channel_counts = {}
    for video in results:
        channel_counts[video["channel_id"]] = channel_counts.get(video["channel_id"], 0) + 1
    assert channel_counts["UCA"] <= 2
    assert channel_counts.get("UCB", 0) == 1


def test_load_video_index_returns_empty_list_when_file_missing(tmp_path):
    missing_path = str(tmp_path / "does-not-exist.json")
    assert video_index.load_video_index(missing_path) == []
