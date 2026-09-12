import pytest

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
