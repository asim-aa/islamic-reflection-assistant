import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

import src.retrieval as retrieval


class _DeterministicHashEmbedding:
    """Same no-network stand-in used elsewhere in the test suite (see
    tests/test_retrieval.py and tests/test_video_index.py)."""

    DIM = 64

    def __init__(self, model_name=None, **kwargs):
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
def client(monkeypatch):
    import fastembed

    monkeypatch.setattr(retrieval, "TextEmbedding", _DeterministicHashEmbedding)
    monkeypatch.setattr(fastembed, "TextEmbedding", _DeterministicHashEmbedding)

    import backend.main as main

    with TestClient(main.app) as test_client:
        yield test_client


def test_corpus_and_video_index_share_one_embedding_model(client):
    """Regression test: CorpusIndex and VideoIndex used to each construct
    their own TextEmbedding, loading two full copies of the ONNX model into
    memory -- this is what caused an out-of-memory crash on a 512MB hosting
    tier. backend/main.py's lifespan now passes corpus_index.model into
    VideoIndex so only one copy is ever loaded."""
    import backend.main as main

    assert main.state["video_index"].model is main.state["corpus_index"].model


def test_health_endpoint_reports_corpus_loaded(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["corpus_loaded"] is True


def test_reflect_rejects_blank_feeling_text(client):
    resp = client.post("/api/reflect", json={"feeling_text": "   "})
    assert resp.status_code == 400


def test_reflect_returns_expected_shape(client):
    resp = client.post("/api/reflect", json={"feeling_text": "I feel anxious about the future"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"classification", "sources", "reflection", "videos"}
    assert isinstance(body["sources"], list)
    assert isinstance(body["videos"], list)
    assert "emotion" in body["classification"]
    assert "opening" in body["reflection"]
    assert "explanations" in body["reflection"]


def test_reflect_excludes_previously_shown_ids(client):
    first = client.post("/api/reflect", json={"feeling_text": "I feel anxious about the future"}).json()
    shown_ids = [s["id"] for s in first["sources"]]
    if not shown_ids:
        pytest.skip("no sources returned for this query with the fake embedder")

    second = client.post(
        "/api/reflect",
        json={"feeling_text": "I feel anxious about the future", "exclude_ids": shown_ids},
    ).json()
    assert set(s["id"] for s in second["sources"]).isdisjoint(shown_ids)


def test_reflect_includes_videos_when_index_is_populated(client, monkeypatch):
    import backend.main as main
    from src.video_index import VideoIndex

    main.state["video_index"] = VideoIndex(
        [
            {
                "video_id": "vid1",
                "title": "anxiety worry fear",
                "description": "",
                "channel_id": "UCA",
                "channel_title": "Test Channel",
                "url": "https://www.youtube.com/watch?v=vid1",
            }
        ]
    )
    resp = client.post("/api/reflect", json={"feeling_text": "anxiety worry fear"})
    assert resp.status_code == 200
    assert len(resp.json()["videos"]) == 1
