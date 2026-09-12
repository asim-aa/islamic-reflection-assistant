import json
import os

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "corpus.json")

REQUIRED_FIELDS = ["id", "source_type", "citation", "translation", "themes", "intents"]
VALID_SOURCE_TYPES = ("quran", "hadith", "dua")


def load_corpus(path: str = CORPUS_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_corpus(entries: list[dict]) -> None:
    seen_ids = set()
    for entry in entries:
        for field in REQUIRED_FIELDS:
            if field not in entry:
                raise ValueError(f"Corpus entry missing required field '{field}': {entry.get('id', '?')}")
        entry_id = entry["id"]
        if entry_id in seen_ids:
            raise ValueError(f"Duplicate corpus id: {entry_id}")
        seen_ids.add(entry_id)
        if entry["source_type"] not in VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type for {entry_id}: {entry['source_type']}")
        if entry["source_type"] == "quran" and (entry.get("surah") is None or entry.get("ayah") is None):
            raise ValueError(f"Qur'an entry missing surah/ayah: {entry_id}")
        if entry["source_type"] == "hadith" and entry.get("hadith_collection") is None:
            raise ValueError(f"Hadith entry missing hadith_collection: {entry_id}")
