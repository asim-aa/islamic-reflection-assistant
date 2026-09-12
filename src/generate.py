import json

from .llm_client import get_client, get_model

SYSTEM_PROMPT = """You are a warm, concise reflection assistant for a Muslim audience.
You will be given the user's feeling and a list of ALREADY-VERIFIED Islamic sources
(Qur'an verses, hadith, or dua), each with an id, citation, and translation that were
retrieved from a curated library -- you did not choose them and must not alter them.

Write a JSON object with:
- "opening": 1-2 warm, empathetic sentences acknowledging the feeling. Do not include
  any religious quote here -- just a human acknowledgment.
- "explanations": an object mapping each given source id to a 1-2 sentence explanation
  of why that specific source may be relevant to the feeling described.

Rules:
- You must NOT quote, paraphrase as a quote, or introduce any Qur'an verse, hadith, or
  dua that is not already given to you below.
- You must NOT invent a citation, surah, ayah number, or hadith reference.
- Only reference sources by the ids given to you; do not add new ids.
- If you are unsure how a source relates, still write a brief honest connection, but
  never fabricate wording attributed to Allah or the Prophet.
- Output valid JSON only, with no markdown code fences."""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[: -3]
    return raw.strip()


def generate_reflection(feeling_text: str, classification: dict, sources: list[dict]) -> dict:
    """Generate an empathetic wrapper around already-retrieved sources.

    The sacred text itself (arabic/transliteration/translation/citation) is never
    produced by the LLM -- it is rendered straight from the corpus. The LLM only
    writes connective explanation text, and any id it returns that isn't in
    `sources` is dropped rather than trusted.
    """
    if not sources:
        return {"opening": "", "explanations": {}}

    payload = {
        "feeling": feeling_text,
        "classification": classification,
        "sources": [
            {"id": s["id"], "citation": s["citation"], "translation": s["translation"]}
            for s in sources
        ],
    }

    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        raw = _strip_fences(resp.choices[0].message.content or "")
        data = json.loads(raw)
    except Exception:
        return {"opening": "", "explanations": {}}

    valid_ids = {s["id"] for s in sources}
    explanations = data.get("explanations", {})
    if not isinstance(explanations, dict):
        explanations = {}
    explanations = {k: v for k, v in explanations.items() if k in valid_ids and isinstance(v, str)}

    opening = data.get("opening", "")
    if not isinstance(opening, str):
        opening = ""

    return {"opening": opening, "explanations": explanations}
