from src.corpus import load_corpus, validate_corpus


def test_corpus_loads_and_validates():
    entries = load_corpus()
    assert len(entries) > 0
    validate_corpus(entries)


def test_no_duplicate_ids():
    entries = load_corpus()
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))


def test_quran_entries_have_surah_and_ayah():
    entries = load_corpus()
    for entry in entries:
        if entry["source_type"] == "quran":
            assert entry.get("surah") is not None
            assert entry.get("ayah") is not None


def test_hadith_entries_have_collection():
    entries = load_corpus()
    for entry in entries:
        if entry["source_type"] == "hadith":
            assert entry.get("hadith_collection") is not None


def test_every_entry_has_at_least_one_theme_and_intent():
    entries = load_corpus()
    for entry in entries:
        assert entry["themes"], f"{entry['id']} has no themes"
        assert entry["intents"], f"{entry['id']} has no intents"
