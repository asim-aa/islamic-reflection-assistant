import json

from .llm_client import get_client, get_model

VALID_INTENTS = ["comfort", "forgiveness", "gratitude", "guidance", "patience", "protection"]

SYSTEM_PROMPT = """You are an intent classifier for an Islamic reflection app.
Given a short piece of text describing how someone feels, output ONLY a JSON object with:
- "emotion": the single primary emotion word (e.g. "anxiety", "sadness", "gratitude", "anger", "loneliness", "guilt", "confusion", "hope", "stress", "fear")
- "secondary_emotions": a list of 0-2 additional emotion words, or an empty list
- "intent": exactly one of {intents} -- pick the closest match for what kind of Islamic reminder would help
- "themes": a list of 2-5 short lowercase theme keywords describing what the person needs (e.g. "trust in allah", "patience", "hope", "forgiveness")

Do not include any Quran verse, hadith, or dua text. Do not add commentary.
Output valid JSON only, with no markdown code fences.""".format(intents=", ".join(VALID_INTENTS))

DEFAULT_CLASSIFICATION = {
    "emotion": "uncertain",
    "secondary_emotions": [],
    "intent": "comfort",
    "themes": [],
}


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[: -3]
    return raw.strip()


def classify_feeling(text: str) -> dict:
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        raw = _strip_fences(resp.choices[0].message.content or "")
        data = json.loads(raw)
    except Exception:
        return dict(DEFAULT_CLASSIFICATION)

    intent = data.get("intent", "comfort")
    if intent not in VALID_INTENTS:
        intent = "comfort"

    emotion = str(data.get("emotion", "")).strip().lower() or "uncertain"
    secondary = [str(e).strip().lower() for e in data.get("secondary_emotions", []) if str(e).strip()]
    themes = [str(t).strip().lower() for t in data.get("themes", []) if str(t).strip()]

    return {
        "emotion": emotion,
        "secondary_emotions": secondary,
        "intent": intent,
        "themes": themes,
    }
