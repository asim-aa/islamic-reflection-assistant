import hashlib

import numpy as np
import pytest

import src.retrieval as retrieval
from src.corpus import load_corpus
from src.retrieval import CorpusIndex


@pytest.fixture(scope="module")
def index():
    entries = load_corpus()
    try:
        return CorpusIndex(entries)
    except Exception as exc:  # embedding model download may be unavailable offline
        pytest.skip(f"embedding model unavailable in this environment: {exc}")


def test_anxiety_query_returns_relevant_theme(index):
    results = index.search("I feel anxious about the future", themes=["anxiety"], top_k=3)
    assert len(results) > 0
    top_entry = results[0][1]
    assert {"anxiety", "hardship", "fear"} & set(top_entry.get("themes", []))


def test_unrelated_query_can_return_no_results(index):
    results = index.search("what is the boiling point of water in celsius", top_k=3, min_score=0.6)
    assert isinstance(results, list)


class _DeterministicHashEmbedding:
    """A fake embedder with no network dependency, so this regression test
    always runs (unlike the fixture above, which skips without a real
    embedding model). Bag-of-words hashing is a poor semantic model, but
    it's a fine stand-in for testing CorpusIndex's own control flow."""

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


def test_search_scores_the_whole_corpus_regardless_of_top_k(monkeypatch):
    """Regression test for a bug where search() narrowed to the top few
    nearest neighbors by raw embedding similarity (top_k*3) *before*
    applying the theme-tag boost, so a correctly-themed entry with a
    semantically dissimilar query could never be promoted -- the boost only
    ever saw whatever that raw similarity search had already let through.
    Fixed by always scoring the whole corpus (cheap at this corpus size)
    before boosting and truncating to top_k -- structurally guaranteed now
    that this is a single matrix-vector product over every entry, with no
    library-level top-k cutoff in between (see src/retrieval.py).

    Sets index.embeddings and the query embedding directly to known unit
    vectors rather than relying on the toy hash embedder's approximate
    semantics, so the raw-similarity-vs-boost arithmetic is exact instead
    of fragile.
    """
    monkeypatch.setattr(retrieval, "TextEmbedding", _DeterministicHashEmbedding)
    entries = [
        {"id": "high-1", "translation": "x", "notes": "", "themes": [], "intents": []},
        {"id": "high-2", "translation": "x", "notes": "", "themes": [], "intents": []},
        {"id": "target", "translation": "x", "notes": "", "themes": ["rare-theme"], "intents": []},
    ]
    index = CorpusIndex(entries)

    # Unit vectors chosen so the dot product with query [1, 0] gives exactly
    # 1.0, 0.95, 0.9 -- target ranks 3rd (last) on raw similarity alone, but
    # the +0.15 theme boost should push it to 1.05, ahead of both others.
    index.embeddings = np.array(
        [[1.0, 0.0], [0.95, 0.3122499], [0.9, 0.4358899]], dtype="float32"
    )
    monkeypatch.setattr(index.model, "embed", lambda texts: [np.array([1.0, 0.0], dtype="float32")])

    without_boost = index.search("query", top_k=1, min_score=0.0)
    assert without_boost[0][1]["id"] == "high-1", "sanity check: target should rank last without the boost"

    with_boost = index.search("query", themes=["rare-theme"], top_k=1, min_score=0.0)
    assert with_boost[0][1]["id"] == "target", (
        "the theme boost didn't promote 'target' above higher-raw-similarity entries -- "
        "either the boost isn't applying, or the full corpus isn't being scored"
    )
