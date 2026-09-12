import streamlit as st

from src.classify import classify_feeling
from src.corpus import load_corpus, validate_corpus
from src.generate import generate_reflection
from src.retrieval import CorpusIndex
from src.youtube import (
    get_api_key as get_youtube_api_key,
    load_trusted_channels,
    resolve_all_channel_ids,
    search_trusted_videos,
)

st.set_page_config(page_title="Reflection & Reminders", page_icon="\U0001F319", layout="centered")

EMOTIONS = [
    "Anxious", "Sad", "Grateful", "Angry", "Lonely",
    "Guilty", "Confused", "Hopeful", "Stressed", "Afraid",
]


@st.cache_resource(show_spinner="Loading the reminder library...")
def get_index() -> CorpusIndex:
    entries = load_corpus()
    validate_corpus(entries)
    return CorpusIndex(entries)


@st.cache_resource(show_spinner=False)
def get_channel_id_map(api_key: str) -> dict:
    return resolve_all_channel_ids(load_trusted_channels(), api_key)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def cached_search_trusted_videos(query: str, channel_id_map: dict, api_key: str, max_total: int) -> list[dict]:
    # Cached for a few hours: each trusted channel costs its own API quota
    # unit per search (see src/youtube.py), so repeated identical queries
    # within a session -- or across users hitting the same emotion button --
    # shouldn't re-spend it.
    return search_trusted_videos(query, channel_id_map, api_key, per_channel=2, max_total=max_total)


def find_related_videos(classification: dict, max_total: int = 6):
    """Returns None if the video feature isn't configured (no API key), a
    possibly-empty list otherwise. A trusted-channel search failing or
    finding nothing is not an error -- the text reminder above still stands
    on its own -- so any exception here is swallowed rather than surfaced."""
    api_key = get_youtube_api_key()
    if not api_key:
        return None
    try:
        channel_id_map = get_channel_id_map(api_key)
        if not channel_id_map:
            return []
        query_terms = classification.get("themes") or [classification.get("emotion", "")]
        query = "islamic reminder " + " ".join(t for t in query_terms if t)
        return cached_search_trusted_videos(query, channel_id_map, api_key, max_total)
    except Exception:
        return []


def render_videos(videos: list[dict]) -> None:
    st.subheader("Related videos from trusted channels")
    for video in videos:
        with st.container(border=True):
            st.video(video["url"])
            st.caption(f"{video['title']} — {video['channel_title']}")


def render_source(entry: dict, explanation: str) -> None:
    with st.container(border=True):
        caption = entry["citation"]
        if entry.get("authenticity"):
            caption += f" — {entry['authenticity']}"
        st.caption(caption)
        if entry.get("arabic"):
            st.markdown(
                f"<div style='font-size:1.4rem;text-align:right;direction:rtl;line-height:2;'>{entry['arabic']}</div>",
                unsafe_allow_html=True,
            )
        if entry.get("transliteration"):
            st.markdown(f"*{entry['transliteration']}*")
        st.write(entry["translation"])
        if explanation:
            st.markdown(f"**Why this may help:** {explanation}")
        if not entry.get("verified_against_source", False):
            st.caption("⚠️ Wording pending verification against Quran.com / Sunnah.com -- see README.")


def run_pipeline(feeling_text: str, exclude_ids: set | None = None):
    index = get_index()
    classification = classify_feeling(feeling_text)
    hits = index.search(feeling_text, themes=classification["themes"], top_k=6)
    if exclude_ids:
        hits = [(score, entry) for score, entry in hits if entry["id"] not in exclude_ids]
    top_hits = hits[:3]
    sources = [entry for _, entry in top_hits]
    reflection = generate_reflection(feeling_text, classification, sources)
    return classification, sources, reflection


st.title("How are you feeling?")
st.write(
    "Share a feeling and receive a grounded reminder from the Qur'an, authentic hadith, "
    "and du'a -- never invented, always cited from a curated library."
)

if "result" not in st.session_state:
    st.session_state.result = None
if "shown_ids" not in st.session_state:
    st.session_state.shown_ids = set()

cols = st.columns(5)
picked_emotion = None
for i, emo in enumerate(EMOTIONS):
    if cols[i % 5].button(emo, use_container_width=True, key=f"emo_{emo}"):
        picked_emotion = emo

free_text = st.text_area(
    "Or describe it in your own words",
    placeholder="e.g. I feel anxious about whether I'll succeed...",
)
submitted = st.button("Reflect", type="primary")

feeling_text = None
if picked_emotion:
    feeling_text = f"I feel {picked_emotion.lower()}."
elif submitted and free_text.strip():
    feeling_text = free_text.strip()
elif submitted:
    st.warning("Please choose a feeling or describe it first.")

if feeling_text:
    try:
        with st.spinner("Finding a grounded reminder..."):
            classification, sources, reflection = run_pipeline(feeling_text)
        st.session_state.result = (feeling_text, classification, sources, reflection)
        st.session_state.shown_ids = {s["id"] for s in sources}
    except Exception:
        st.error(
            "Something went wrong while looking for a reminder (the reminder "
            "library or the AI model may be temporarily unreachable). Please try again shortly."
        )

if st.session_state.result:
    feeling_text, classification, sources, reflection = st.session_state.result
    st.divider()
    if reflection.get("opening"):
        st.write(reflection["opening"])

    if not sources:
        theme_list = ", ".join(classification["themes"]) or "none identified"
        st.info(
            "I couldn't find a verified reminder in the library for exactly this feeling. "
            f"Closest themes identified: {theme_list}. "
            "The library is still small -- try describing it a bit differently, or explore "
            "sabr (patience) and tawakkul (trust in Allah)."
        )
    else:
        st.subheader(f"A reminder for {classification['emotion']}")
        for entry in sources:
            render_source(entry, reflection["explanations"].get(entry["id"], ""))

        if st.button("Give me another reminder"):
            try:
                with st.spinner("Looking for another angle..."):
                    classification2, sources2, reflection2 = run_pipeline(
                        feeling_text, exclude_ids=st.session_state.shown_ids
                    )
                if sources2:
                    st.session_state.result = (feeling_text, classification2, sources2, reflection2)
                    st.session_state.shown_ids |= {s["id"] for s in sources2}
                    st.rerun()
                else:
                    st.info("No further verified reminders found in the current library for this feeling.")
            except Exception:
                st.error("Something went wrong while looking for another reminder. Please try again shortly.")

    videos = find_related_videos(classification)
    if videos:
        st.divider()
        render_videos(videos)
    elif videos is None:
        st.caption(
            "Set YOUTUBE_API_KEY in your .env to also see related videos from a curated "
            "list of trusted Islamic channels -- see README.md."
        )

st.divider()
st.caption(
    "This tool only ever presents Qur'an verses, hadith, and du'a already stored in its "
    "curated, cited library -- it never asks the AI model to generate scripture from memory. "
    "See README.md for the corpus's current verification status."
)
