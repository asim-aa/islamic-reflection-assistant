"""Reflection pipeline shared by the Streamlit app (app.py) and the FastAPI
backend (backend/main.py), so the two front ends can't drift out of sync on
retrieval or video-query logic the way app.py's video query construction
once did before it was fixed."""

from .classify import classify_feeling
from .generate import generate_reflection


def build_video_query(classification: dict) -> str:
    """Lead with the specific classified emotion, not just the themes: the
    classifier prompt asks for cause-specific themes, but on a short input
    the model can still fall back toward generic overlapping words across
    different emotions. Without the emotion word anchoring the query, two
    different feelings could search with near-identical terms and surface
    the same evergreen videos for both."""
    emotion = classification.get("emotion", "")
    themes = classification.get("themes") or []
    terms = [emotion] + [t for t in themes if t and t != emotion]
    return "islamic reminder " + " ".join(t for t in terms if t)


def run_reflection(feeling_text: str, corpus_index, exclude_ids: set | None = None) -> dict:
    """Classify the feeling, retrieve up to 3 corpus sources (excluding any
    ids already shown), and generate the connective explanation text.
    Returns {"classification", "sources", "reflection"}."""
    classification = classify_feeling(feeling_text)
    hits = corpus_index.search(feeling_text, themes=classification["themes"], top_k=6)
    if exclude_ids:
        hits = [(score, entry) for score, entry in hits if entry["id"] not in exclude_ids]
    sources = [entry for _, entry in hits[:3]]
    reflection = generate_reflection(feeling_text, classification, sources)
    return {"classification": classification, "sources": sources, "reflection": reflection}
