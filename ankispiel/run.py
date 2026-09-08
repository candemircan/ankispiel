"""The nightly job: fresh example sentences for the upcoming day.

Selection (per the agreed plan): review cards due today or tomorrow (overdue included,
so a failed note from last night is retried), plus the next new notes in new-card
order. A note is skipped when it has not been reviewed since its last refresh (its
example sentences are still unseen), so unreviewed cards are not regenerated day after
day. Each note is all-or-nothing; failures are counted and reported, never silent.
"""

import base64, hashlib, json, time
from datetime import date

from ankispiel.anki import AnkiConnect
from ankispiel.config import STATE_DIR, AppConfig
from ankispiel.llm import generate
from ankispiel.notify import notify
from ankispiel.tts import KokoroVoice


def _pick_notes(anki: AnkiConnect, cfg: AppConfig) -> list[int]:
    deck = f'deck:"{cfg.anki.deck}" note:"{cfg.migrate.new_notetype}"'
    review_cards = anki.invoke("findCards", query=f"{deck} is:review prop:due<=1")
    review_notes = sorted(anki.invoke("cardsToNotes", cards=review_cards))

    window = max(50, cfg.anki.new_notes_per_night * 5)
    new_cards = anki.invoke("findCards", query=f"{deck} is:new prop:due<={window}")
    infos = anki.invoke("cardsInfo", cards=new_cards)
    by_due = sorted(infos, key=lambda c: c["due"])
    new_notes = []
    for card in by_due:
        if card["note"] not in new_notes: new_notes.append(card["note"])
        if len(new_notes) == cfg.anki.new_notes_per_night: break
    return review_notes + [n for n in new_notes if n not in review_notes]


def _media_name(text: str, cfg: AppConfig) -> str:
    digest = hashlib.sha256(f"{cfg.tts[cfg.languages.target].voice}|{text}".encode()).hexdigest()[:16]
    return f"_ankispiel-{digest}.mp3"


def _note_reps(anki: AnkiConnect, note_id: int) -> int:
    "Total reviews across a note's cards; increases only when the note is reviewed."
    cards = anki.invoke("findCards", query=f"nid:{note_id}")
    return sum(c["reps"] for c in anki.invoke("cardsInfo", cards=cards))


def run(cfg: AppConfig, quiet: bool = False) -> None:
    anki = AnkiConnect(cfg.anki.url)
    anki.invoke("sync")

    history_path = STATE_DIR / "history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {}
    today = date.today().isoformat()
    voice = KokoroVoice(cfg.tts[cfg.languages.target])
    n_slots = cfg.examples.max
    k = cfg.history.k

    refreshed, failed, skipped = 0, [], 0
    prompt_tokens = completion_tokens = 0
    started = time.perf_counter()

    notes = _pick_notes(anki, cfg)
    total = len(notes)
    for idx, note_id in enumerate(notes, 1):
        entry = history.get(str(note_id))
        reps = _note_reps(anki, note_id)
        if entry and entry.get("reps") == reps:
            skipped += 1
            if not quiet: print(f"[{idx}/{total}] {note_id} skipped (unreviewed)", flush=True)
            continue
        try:
            fields = anki.invoke("notesInfo", notes=[note_id])[0]["fields"]
            target_word = fields["target_word"]["value"]
            source_word = fields["source_word"]["value"]
            if not target_word.strip(): raise ValueError("target_word is empty")
            word_audio_text = fields["target_word_full"]["value"] or target_word
            generated, pt, ct = generate(cfg, target_word, source_word, (entry or {}).get("sentences", [])[-k:])
            prompt_tokens += pt
            completion_tokens += ct

            audio = {}
            for text in [word_audio_text, *generated.sentences]:
                name = _media_name(text, cfg)
                if not anki.invoke("getMediaFilesNames", pattern=name):
                    anki.invoke("storeMediaFile", filename=name, data=base64.b64encode(voice.create_mp3(text)).decode())
                audio[text] = name

            new_fields = {"target_word_audio": f"[sound:{audio[word_audio_text]}]"}
            for i in range(1, n_slots + 1):
                if i <= len(generated.sentences):
                    new_fields[f"ex{i}"] = generated.sentences[i - 1]
                    new_fields[f"ex{i}t"] = generated.translations[i - 1]
                    new_fields[f"ex{i}a"] = f"[sound:{audio[generated.sentences[i - 1]]}]"
                else: new_fields[f"ex{i}"] = new_fields[f"ex{i}t"] = new_fields[f"ex{i}a"] = ""
            anki.invoke("updateNoteFields", note={"id": note_id, "fields": new_fields})

            history[str(note_id)] = dict(date=today, reps=reps, sentences=((entry or {}).get("sentences", []) + generated.sentences)[-k:])
            refreshed += 1
            if not quiet: print(f"[{idx}/{total}] {target_word}  ({pt}+{ct} tok)", flush=True)
            if cfg.provider.request_delay: time.sleep(cfg.provider.request_delay)
        except Exception as e:
            failed.append(f"{note_id}: {e}")
            if not quiet: print(f"[{idx}/{total}] {note_id} FAILED: {e}", flush=True)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=1))

    anki.invoke("sync")

    seconds = time.perf_counter() - started
    body = (
        f"refreshed: {refreshed}, failed: {len(failed)}, skipped: {skipped}\n"
        f"tokens: {prompt_tokens} in / {completion_tokens} out"
    )
    if cfg.provider.input_price_per_mtok is not None:
        cost = (prompt_tokens * cfg.provider.input_price_per_mtok
                + completion_tokens * cfg.provider.output_price_per_mtok) / 1e6
        body += f"\ncost: ${cost:.4f}"
    body += f"\nduration: {seconds:.0f}s"
    if failed: body += "\nfailed notes:\n" + "\n".join(failed[:10])
    notify(cfg, "ankispiel run", body, tags="white_check_mark" if not failed else "warning")
    print(body)
    if failed: raise SystemExit(1)
