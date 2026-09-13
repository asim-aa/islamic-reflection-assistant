"""FastAPI backend for the Islamic reflection assistant.

Wraps the same src/ modules the Streamlit app (../app.py) uses -- corpus
retrieval, classification, reflection generation, and the local video
index -- behind a small JSON API, so a separately-deployed frontend (see
../frontend) can drive the same logic. No business logic lives here beyond
request/response shaping; see src/pipeline.py for the actual pipeline,
shared by both front ends so they can't drift out of sync.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from src.corpus import load_corpus, validate_corpus  # noqa: E402
from src.pipeline import build_video_query, run_reflection  # noqa: E402
from src.retrieval import CorpusIndex  # noqa: E402
from src.video_index import VideoIndex, load_video_index  # noqa: E402

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    entries = load_corpus()
    validate_corpus(entries)
    corpus_index = CorpusIndex(entries)
    state["corpus_index"] = corpus_index
    # Loads whatever scripts/refresh_video_index.py last wrote to disk --
    # never a live YouTube call per request. An empty/missing index (e.g.
    # the refresh script hasn't been run yet) just means no videos in the
    # response, not an error. Shares corpus_index's embedding model instead
    # of loading a second copy of the ONNX model -- see CorpusIndex's model
    # parameter docstring; running two copies in one process is what
    # exceeded Render's free-tier 512MB memory limit.
    state["video_index"] = VideoIndex(load_video_index(), model=corpus_index.model)
    yield
    state.clear()


app = FastAPI(title="Islamic Reflection Assistant API", lifespan=lifespan)

_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReflectRequest(BaseModel):
    feeling_text: str = Field(..., min_length=1, max_length=2000)
    exclude_ids: list[str] = Field(default_factory=list)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "corpus_loaded": "corpus_index" in state,
        "video_count": len(state.get("video_index").videos) if state.get("video_index") else 0,
    }


@app.post("/api/reflect")
def reflect(payload: ReflectRequest) -> dict:
    feeling_text = payload.feeling_text.strip()
    if not feeling_text:
        raise HTTPException(status_code=400, detail="feeling_text must not be blank")

    try:
        result = run_reflection(
            feeling_text,
            state["corpus_index"],
            exclude_ids=set(payload.exclude_ids) if payload.exclude_ids else None,
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Something went wrong while looking for a reminder (the reminder library or the AI model may be temporarily unreachable). Please try again shortly.",
        )

    video_index: VideoIndex = state["video_index"]
    videos = video_index.search(build_video_query(result["classification"]), top_k=6) if video_index.videos else []

    return {
        "classification": result["classification"],
        "sources": result["sources"],
        "reflection": result["reflection"],
        "videos": videos,
    }
