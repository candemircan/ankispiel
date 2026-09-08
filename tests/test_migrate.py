"""Smoke test for migrate() against a live AnkiConnect, on a throwaway deck.

Skips when AnkiConnect is not reachable. Deletes the throwaway deck in a finally;
the two `ankispiel-test-*` notetypes remain (AnkiConnect cannot delete notetypes).
"""

import json

import pytest, requests

from ankispiel.anki import AnkiConnect
from ankispiel.config import AppConfig, AnkiConfig, ExtraField, LanguagePair, MigrateConfig, ProviderConfig, TtsVoiceConfig
from ankispiel.migrate import migrate

URL = "http://localhost:8765"
DECK = "ankispiel-test"
LEGACY = "ankispiel-test-legacy"
NEW = "ankispiel-test-new"
FIELDS = ["english", "german", "german_full", "full_form"]
# english, german, german_full ("die Bitte, -en" style)
NOTES = [("request", "die Bitte", "die Bitte, -en"), ("answer", "die Antwort", "die Antwort, -en")]


def _anki() -> AnkiConnect:
    anki = AnkiConnect(URL)
    try: anki.invoke("version")
    except requests.RequestException: pytest.skip(f"AnkiConnect not reachable at {URL}")
    return anki


def _add_note(anki: AnkiConnect, word: str, german: str, german_full: str) -> int:
    "Add one legacy note to the throwaway deck."
    fields = dict(english=word, german=german, german_full=german_full, full_form=german_full)
    note = dict(deckName=DECK, modelName=LEGACY, fields=fields, tags=["ankispiel-test"])
    return anki.invoke("addNote", note=note)


def _config() -> AppConfig:
    tts = {"de": TtsVoiceConfig(engine="kokoro", voice="unused", lang="de", speed=1.0,
        model="unused", model_file="unused.onnx", voices_file="unused.npz")}
    mig = MigrateConfig(legacy_notetype=LEGACY, source_word_field="english", target_word_field="german",
        new_notetype=NEW, full_form_field="german_full")
    return AppConfig(provider=ProviderConfig(base_url="http://unused/v1", model="unused"),
        anki=AnkiConfig(url=URL, deck=DECK), languages=LanguagePair(source="en", target="de"),
        tts=tts, migrate=mig, extra=[ExtraField(name="forms", legacy_field="full_form", strip_word=True)])


def test_migrate_sample(tmp_path, monkeypatch):
    monkeypatch.setattr("ankispiel.migrate.STATE_DIR", tmp_path)
    anki = _anki()
    if DECK in anki.invoke("deckNames"): anki.invoke("deleteDecks", decks=[DECK], cardsToo=True)  # leftovers of a crashed run
    anki.invoke("createDeck", deck=DECK)
    if LEGACY not in anki.invoke("modelNames"):
        anki.invoke("createModel", modelName=LEGACY, css="", isCloze=False, inOrderFields=FIELDS,
            cardTemplates=[dict(Name="card", Front="{{german}}", Back="{{english}}")])
    note_ids = [_add_note(anki, *row) for row in NOTES]

    try:
        migrate(_config(), sample=1)

        assert anki.invoke("findNotes", query=f'note:"{NEW}" deck:"{DECK}"') == note_ids[:1]
        assert anki.invoke("findNotes", query=f'note:"{LEGACY}" deck:"{DECK}"') == note_ids[1:]

        note = anki.invoke("notesInfo", notes=note_ids[:1])[0]
        assert note["fields"]["source_word"]["value"] == "request"
        assert note["fields"]["target_word"]["value"] == "die Bitte"
        assert note["fields"]["target_word_full"]["value"] == "die Bitte"
        assert note["fields"]["forms"]["value"] == "-en"
        assert "ankispiel-test" in note["tags"]

        apkgs = list((tmp_path / "backup").glob("*.apkg"))
        assert len(apkgs) == 1
        archives = list((tmp_path / "archive").glob("*.json"))
        assert len(archives) == 1
        archive = json.loads(archives[0].read_text(encoding="utf-8"))
        assert archive["legacy_notetype"]["fields"] == FIELDS
        assert [n["fields"]["german"] for n in archive["notes"]] == ["die Bitte", "die Antwort"]
    finally: anki.invoke("deleteDecks", decks=[DECK], cardsToo=True)
