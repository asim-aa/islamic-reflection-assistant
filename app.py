import html

import streamlit as st

from src.corpus import load_corpus, validate_corpus
from src.pipeline import build_video_query, run_reflection
from src.retrieval import CorpusIndex
from src.video_index import VideoIndex, load_video_index

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
def get_video_index() -> VideoIndex:
    # Searches a local index built by scripts/refresh_video_index.py --
    # never a live YouTube API call per request. Live search.list costs 100
    # quota units per channel per call; with 5 trusted channels that's 500
    # units per single user submission, exhausting a default 10,000-unit
    # daily quota after roughly 20 uses total. See src/video_index.py.
    #
    # Shares get_index()'s embedding model rather than loading a second
    # copy of the ONNX model into memory -- get_index() is itself cached by
    # st.cache_resource, so this doesn't reload anything.
    return VideoIndex(load_video_index(), model=get_index().model)


def find_related_videos(classification: dict, max_total: int = 6):
    """Returns None if the video index hasn't been built yet (see
    scripts/refresh_video_index.py), a possibly-empty list otherwise."""
    video_index = get_video_index()
    if not video_index.videos:
        return None
    return video_index.search(build_video_query(classification), top_k=max_total)


VIDEO_GRID_CSS = """
<style>
.yt-thumb-wrap {
    position: relative;
    width: 100%;
    padding-top: 56.25%;
    border-radius: 12px;
    overflow: hidden;
    background: #202020;
    margin-bottom: 8px;
}
.yt-thumb-wrap img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.yt-play {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 46px;
    height: 32px;
    background: rgba(0, 0, 0, 0.75);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.yt-play::after {
    content: "";
    border-style: solid;
    border-width: 7px 0 7px 12px;
    border-color: transparent transparent transparent #ffffff;
    margin-left: 3px;
}
.yt-meta {
    display: flex;
    gap: 10px;
    align-items: flex-start;
}
.yt-avatar {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #cc0000;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 13px;
}
.yt-title {
    font-weight: 600;
    font-size: 14px;
    line-height: 1.3;
    margin: 0 0 2px 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.yt-channel {
    font-size: 12px;
    opacity: 0.65;
}
.yt-card-link {
    display: block;
    text-decoration: none;
    color: inherit;
    margin-bottom: 20px;
}
</style>
"""


def render_videos(videos: list[dict]) -> None:
    st.subheader("Related videos from trusted channels")
    st.markdown(VIDEO_GRID_CSS, unsafe_allow_html=True)
    columns = st.columns(3)
    for i, video in enumerate(videos):
        title = html.escape(video.get("title") or "")
        channel_title = html.escape(video.get("channel_title") or "")
        url = html.escape(video.get("url") or "", quote=True)
        thumbnail = video.get("thumbnail")
        initial = html.escape((video.get("channel_title") or "?")[:1].upper())

        thumb_html = (
            f'<img src="{html.escape(thumbnail, quote=True)}" alt="">' if thumbnail else ""
        )

        with columns[i % 3]:
            st.markdown(
                f"""
                <a class="yt-card-link" href="{url}" target="_blank" rel="noopener">
                    <div class="yt-thumb-wrap">
                        {thumb_html}
                        <div class="yt-play"></div>
                    </div>
                    <div class="yt-meta">
                        <div class="yt-avatar">{initial}</div>
                        <div>
                            <p class="yt-title">{title}</p>
                            <p class="yt-channel">{channel_title}</p>
                        </div>
                    </div>
                </a>
                """,
                unsafe_allow_html=True,
            )


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
    result = run_reflection(feeling_text, get_index(), exclude_ids=exclude_ids)
    return result["classification"], result["sources"], result["reflection"]


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
