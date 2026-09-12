"""Cross-check this project's Qur'an entries in data/corpus.json against the
public Quran.com API (no API key required).

This is a *helper*, not an automatic fixer: it prints the stored text next to
the freshly-fetched text for each Qur'an entry so a human can compare them and
update data/corpus.json by hand. It intentionally never overwrites the corpus
file itself -- corpus wording should only ever change via a reviewed edit.

Run this locally where you have normal internet access. The sandbox this
project was originally scaffolded in restricts outbound network access to an
allowlist that does not include api.quran.com, so this script could not be
run or verified during initial scaffolding -- treat every corpus entry's
`verified_against_source` field as `false` until you have run this (and, for
hadith entries, checked https://sunnah.com by hand) and updated that field.

Usage:
    python scripts/verify_corpus.py
"""
import json
import os
import ssl
import sys
import urllib.request

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "corpus.json")
QURAN_API = "https://api.quran.com/api/v4/verses/by_key/{key}?fields=text_uthmani&translations=20"


def _ssl_context() -> ssl.SSLContext:
    # Some Python installs (notably python.org builds on macOS) don't wire up
    # the system CA trust store by default, which makes urlopen() fail with
    # CERTIFICATE_VERIFY_FAILED even though the connection itself is fine.
    # certifi ships a CA bundle and is already a transitive dependency here
    # (via requests/urllib3), so use it explicitly instead of relying on
    # whatever the interpreter defaults to.
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_verse(surah: int, ayah: str):
    key = f"{surah}:{ayah}"
    # Quran.com's API rejects requests carrying Python's default urllib
    # User-Agent (returns a bare 403), so send a normal browser-style one.
    req = urllib.request.Request(
        QURAN_API.format(key=key),
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; islamic-reflection-assistant-corpus-verifier/1.0)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    verse = data["verse"]
    arabic = verse["text_uthmani"]
    translations = verse.get("translations") or []
    translation = translations[0]["text"] if translations else None
    return arabic, translation


def main() -> None:
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    checked = 0
    for entry in entries:
        if entry["source_type"] != "quran" or not entry.get("surah"):
            continue
        # For multi-ayah ranges (e.g. "5-6") this only spot-checks the first ayah.
        first_ayah = str(entry.get("ayah", "")).split("-")[0]
        if not first_ayah:
            continue
        try:
            arabic, translation = fetch_verse(entry["surah"], first_ayah)
        except Exception as exc:
            print(f"[skip] {entry['id']}: could not fetch ({exc})")
            continue
        checked += 1
        print(f"\n{entry['id']} ({entry['citation']})")
        print(f"  stored arabic:      {entry.get('arabic')}")
        print(f"  fetched arabic:     {arabic}")
        print(f"  fetched translation (Saheeh International, via quran.com): {translation}")

    print(f"\nChecked {checked} Qur'an entries against api.quran.com.")
    print(
        "For hadith entries, cross-check hadith_collection + hadith_number by hand "
        "against https://sunnah.com -- there is no equivalent no-auth public API used here."
    )
    print(
        "After reviewing, update each verified entry's \"verified_against_source\" field "
        "to true in data/corpus.json."
    )


if __name__ == "__main__":
    sys.exit(main())
