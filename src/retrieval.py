import numpy as np
import faiss
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"


class CorpusIndex:
    def __init__(self, entries: list[dict], model_name: str = MODEL_NAME, model: TextEmbedding | None = None):
        """`model` lets a caller pass in an already-constructed TextEmbedding
        to share with another index (see src/video_index.py's VideoIndex) --
        each instance otherwise loads its own full copy of the ONNX model,
        which roughly doubles memory use when both indices run in the same
        process (this is what caused an out-of-memory crash on Render's
        512MB free tier when CorpusIndex and VideoIndex each built their own)."""
        self.entries = entries
        self.model = model or TextEmbedding(model_name=model_name)
        texts = [self._entry_text(e) for e in entries]
        embeddings = np.array(list(self.model.embed(texts)), dtype="float32")
        faiss.normalize_L2(embeddings)
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    @staticmethod
    def _entry_text(entry: dict) -> str:
        parts = [
            entry.get("translation", ""),
            entry.get("notes", ""),
            " ".join(entry.get("themes", [])),
            " ".join(entry.get("intents", [])),
        ]
        return " ".join(p for p in parts if p)

    def search(self, query: str, themes: list[str] | None = None, top_k: int = 3, min_score: float = 0.3):
        """Return up to top_k (score, entry) pairs above min_score, best first.

        Searches the *entire* corpus (not just the top few by raw semantic
        similarity) before applying the theme-tag boost below. With a corpus
        this size there's no real cost to that, and truncating first would
        let a correctly-themed entry get excluded before the boost -- which
        exists specifically to promote it -- ever had a chance to apply.
        """
        query_vec = np.array(list(self.model.embed([query])), dtype="float32")
        faiss.normalize_L2(query_vec)
        k = len(self.entries)
        if k == 0:
            return []
        scores, idxs = self.index.search(query_vec, k)

        theme_set = {t.lower() for t in themes} if themes else set()
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:
                continue
            entry = self.entries[idx]
            overlap = theme_set & {t.lower() for t in entry.get("themes", [])}
            boost = 0.15 * len(overlap)
            results.append((float(score) + boost, entry))

        results.sort(key=lambda pair: pair[0], reverse=True)
        return [pair for pair in results if pair[0] >= min_score][:top_k]
