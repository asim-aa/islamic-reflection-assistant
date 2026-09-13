import numpy as np
from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class CorpusIndex:
    def __init__(self, entries: list[dict], model_name: str = MODEL_NAME, model: TextEmbedding | None = None):
        """`model` lets a caller pass in an already-constructed TextEmbedding
        to share with another index (see src/video_index.py's VideoIndex) --
        each instance otherwise loads its own full copy of the ONNX model,
        which roughly doubles memory use when both indices run in the same
        process (this is what caused an out-of-memory crash on Render's
        512MB free tier when CorpusIndex and VideoIndex each built their own).

        Cosine similarity is computed directly with numpy rather than faiss:
        at this corpus size (tens of entries), a full similarity search
        library buys nothing over a single matrix-vector product, and
        faiss-cpu is a genuinely heavy compiled dependency whose own runtime
        overhead was part of the same out-of-memory crash.
        """
        self.entries = entries
        self.model = model or TextEmbedding(model_name=model_name, threads=1)
        texts = [self._entry_text(e) for e in entries]
        embeddings = np.array(list(self.model.embed(texts)), dtype="float32")
        self.embeddings = l2_normalize(embeddings)

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

        Always scores the *entire* corpus (not just a truncated candidate
        pool) before applying the theme-tag boost below -- this is now
        structural (the similarity matrix-vector product below covers every
        entry unconditionally), not something that could regress the way a
        library-level top-k cutoff once did.
        """
        if not self.entries:
            return []
        query_vec = np.array(list(self.model.embed([query])), dtype="float32")
        query_vec = l2_normalize(query_vec)
        scores = self.embeddings @ query_vec[0]

        theme_set = {t.lower() for t in themes} if themes else set()
        results = []
        for idx, score in enumerate(scores):
            entry = self.entries[idx]
            overlap = theme_set & {t.lower() for t in entry.get("themes", [])}
            boost = 0.15 * len(overlap)
            results.append((float(score) + boost, entry))

        results.sort(key=lambda pair: pair[0], reverse=True)
        return [pair for pair in results if pair[0] >= min_score][:top_k]
