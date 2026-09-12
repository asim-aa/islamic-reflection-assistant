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


def test_search_scores_the_whole_corpus_regardless_of_top_k(monkeypatch):
    """Regression test for a bug where search() narrowed to the top few
    nearest neighbors by raw embedding similarity (top_k*3) *before*
    applying the theme-tag boost, so a correctly-themed entry with a
    semantically dissimilar query could never be promoted -- the boost only
    ever saw whatever that raw similarity search had already let through.
    Fixed by always scoring the whole corpus (cheap at this corpus size)
    before boosting and truncating to top_k.

    Tests the actual behavioral contract directly (every entry gets scored,
    independent of top_k) rather than relying on boost-vs-raw-similarity
    arithmetic against a toy embedder, which is too fragile to assert on
    reliably.
    """
    monkeypatch.setattr(retrieval, "TextEmbedding", _DeterministicHashEmbedding)
    entries = [{"id": f"entry-{i}", "translation": f"word{i}", "notes": "", "themes": [], "intents": []} for i in range(50)]
    index = CorpusIndex(entries)

    real_index_search = index.index.search
    seen_k = {}

    def spying_search(query_vec, k):
        seen_k["k"] = k
        return real_index_search(query_vec, k)

    monkeypatch.setattr(index.index, "search", spying_search)
    index.search("word7", top_k=3, min_score=0.0)

    assert seen_k["k"] == len(entries), (
        f"search() only scored {seen_k['k']} of {len(entries)} entries for top_k=3 -- "
        "the theme boost can't promote an entry that was never scored"
    )
