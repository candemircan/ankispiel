"""One-time port of the legacy deck to the ankispiel notetype.

Per ADR-0002: apkg backup (with scheduling) and a sidecar archive of all original
fields plus the old notetype definition, then per-note updateNoteModel keeping
note ids (hence card ids and scheduling). Example slots start empty; the nightly
run fills them as notes come due.
"""

import base64, json, re, time

from ankispiel.anki import AnkiConnect
from ankispiel.config import STATE_DIR, AppConfig
from ankispiel.notify import notify
from ankispiel.templates import FONT_FILES, STYLING, templates


def migrate(cfg: AppConfig, sample: int | None) -> None:
    anki = AnkiConnect(cfg.anki.url)
    deck = cfg.anki.deck
    if deck not in anki.invoke("deckNames"): raise SystemExit(f"deck {deck!r} not found")
    if cfg.migrate.legacy_notetype not in anki.invoke("modelNames"):
        raise SystemExit(f"legacy notetype {cfg.migrate.legacy_notetype!r} not found")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = STATE_DIR / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    apkg = backup_dir / f"{deck.replace(' ', '-')}-{stamp}.apkg"
    anki.invoke("exportPackage", deck=deck, path=str(apkg), includeSched=True)
    print(f"backup: {apkg}")

    note_ids = anki.invoke("findNotes", query=f'note:"{cfg.migrate.legacy_notetype}" deck:"{deck}"')
    notes = anki.invoke("notesInfo", notes=note_ids)
    legacy_name = cfg.migrate.legacy_notetype
    legacy = dict(fields=anki.invoke("modelFieldNames", modelName=legacy_name),
        templates=anki.invoke("modelTemplates", modelName=legacy_name), styling=anki.invoke("modelStyling", modelName=legacy_name))
    archive = dict(deck=deck, legacy_notetype=legacy, notes=[
        dict(id=n["noteId"], tags=n["tags"], fields={k: v["value"] for k, v in n["fields"].items()}) for n in notes])
    archive_dir = STATE_DIR / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{deck.replace(' ', '-')}-{stamp}.json"
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"archived {len(notes)} notes + old notetype: {archive_path}")

    if sample: notes = notes[:sample]
    _create_notetype(anki, cfg)
    for src, media_name in FONT_FILES.items():
        anki.invoke("storeMediaFile", filename=media_name, data=base64.b64encode(src.read_bytes()).decode())
    print(f"uploaded {len(FONT_FILES)} fonts to collection.media")

    migrated = 0
    not_stripped = []
    for n in notes:
        fields = {k: v["value"] for k, v in n["fields"].items()}
        target = fields[cfg.migrate.target_word_field]
        new_fields = {"source_word": fields[cfg.migrate.source_word_field], "target_word": target}
        if cfg.migrate.full_form_field: new_fields["target_word_full"] = fields[cfg.migrate.full_form_field].split(",")[0].strip()
        for e in cfg.extra:
            value = fields[e.legacy_field]
            if e.strip_word:
                if target and target not in value: not_stripped.append(n["noteId"])
                value = _strip_word(value, target)
            new_fields[e.name] = value
        anki.invoke("updateNoteModel", note=dict(
            id=n["noteId"], modelName=cfg.migrate.new_notetype, fields=new_fields, tags=n["tags"]))
        migrated += 1

    if not_stripped: print(f"{len(not_stripped)} notes kept the full form (word not found to strip): {not_stripped[:10]}")
    scope = f"sample of {sample}" if sample else "all"
    message = f"Migrated {migrated}/{len(note_ids)} notes ({scope}); backup {apkg.name}"
    print(message)
    notify(cfg, "ankispiel migrate", message)


def _strip_word(value: str, word: str) -> str:
    "Remove the first occurrence of `word` from `value` and tidy separators."
    stripped = value.replace(word, "", 1) if word else value
    return re.sub(r"\s+", " ", stripped).replace(" ,", ",").strip(" ,")


def _create_notetype(anki: AnkiConnect, cfg: AppConfig) -> None:
    name = cfg.migrate.new_notetype
    if name in anki.invoke("modelNames"): return  # created by an earlier (sample) run
    n_slots = cfg.examples.max
    fields = ["source_word", "target_word", "target_word_full", "target_word_audio"]
    fields += [e.name for e in cfg.extra]
    fields += [f"ex{i}{suffix}" for i in range(1, n_slots + 1) for suffix in ("", "t", "a")]
    anki.invoke("createModel", modelName=name, inOrderFields=fields, css=STYLING, isCloze=False,
        cardTemplates=[dict(Name=t["name"], Front=t["qfmt"], Back=t["afmt"]) for t in templates(n_slots, cfg.extra)])
