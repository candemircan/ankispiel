import argparse, os, shutil, sys, time
from pathlib import Path

import openai, requests

from ankispiel import __version__
from ankispiel.anki import AnkiConnect
from ankispiel.config import CONFIG_PATH, EXAMPLE_CONFIG_TOML, load_config
from ankispiel.migrate import migrate
from ankispiel.run import run
from ankispiel.templates import FONT_FILES
from ankispiel.tts import KokoroVoice


def init() -> None:
    if CONFIG_PATH.exists(): raise SystemExit(f"{CONFIG_PATH} already exists")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(EXAMPLE_CONFIG_TOML, encoding="utf-8")
    print(f"Wrote {CONFIG_PATH}")


def doctor(config_path: Path) -> int:
    cfg = load_config(config_path)
    failures = 0

    def report(ok: bool, label: str, detail: str) -> None:
        nonlocal failures
        failures += not ok
        print(f"[{(' ok ' if ok else 'FAIL')}] {label}: {detail}")

    # Anki
    try:
        anki = AnkiConnect(cfg.anki.url)
        version = anki.invoke("version")
        report(True, "anki", f"AnkiConnect {version} at {cfg.anki.url}")
        deck_ok = cfg.anki.deck in anki.invoke("deckNames")
        report(deck_ok, "anki", f"deck {cfg.anki.deck!r} " + ("found" if deck_ok else "missing"))
        models = anki.invoke("modelNames")
        legacy_ok = cfg.migrate.legacy_notetype in models
        report(legacy_ok, "anki", f"legacy notetype {cfg.migrate.legacy_notetype!r} "
               + ("found" if legacy_ok else "missing"))
        new_ok = cfg.migrate.new_notetype in models
        report(new_ok, "anki", f"notetype {cfg.migrate.new_notetype!r} "
               + ("found" if new_ok else "missing (run migrate)"))
        report(True, "anki", f"media dir {anki.invoke('getMediaDirPath')}")
    except requests.RequestException as e: report(False, "anki", f"unreachable at {cfg.anki.url} ({e})")

    # LLM provider
    try: key = os.environ[cfg.provider.api_key_env]
    except KeyError:
        key = None
        report(False, "provider", f"env var {cfg.provider.api_key_env} not set")
    if key is not None:
        try:
            client = openai.OpenAI(base_url=cfg.provider.base_url, api_key=key, default_headers=cfg.provider.headers)
            client.chat.completions.create(model=cfg.provider.model,
                messages=[{"role": "user", "content": "ping"}], max_tokens=2)
            report(True, "provider", f"{cfg.provider.model} responds at {cfg.provider.base_url}")
        except openai.APIError as e: report(False, "provider", f"{cfg.provider.model} failed ({e})")

    # TTS voice for the target language
    voice_cfg = cfg.tts.get(cfg.languages.target)
    if voice_cfg is None: report(False, "tts", f"no voice configured for {cfg.languages.target!r}")
    else:
        try:
            t0 = time.perf_counter()
            samples, sr = KokoroVoice(voice_cfg).create("Test.")
            report(True, "tts", f"{voice_cfg.voice!r} ready in {time.perf_counter() - t0:.1f}s "
                   f"({len(samples) / sr:.1f}s clip, {sr} Hz)")
        except Exception as e: report(False, "tts", f"{voice_cfg.voice!r} failed ({e})")

    # Fonts + ffmpeg
    for src, media_name in FONT_FILES.items(): report(src.is_file(), "fonts", f"{src} -> {media_name}")
    report(shutil.which("ffmpeg") is not None, "ffmpeg", shutil.which("ffmpeg") or "not found")

    if cfg.notify.ntfy_url: print(f"[info] ntfy: reporting to {cfg.notify.ntfy_url}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(prog="ankispiel",
        description="Daily fresh example sentences with audio for an Anki vocabulary deck.")
    parser.add_argument("--version", action="version", version=f"ankispiel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="write a starter config file")
    migrate_parser = sub.add_parser("migrate", help="one-time deck port")
    migrate_parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    migrate_parser.add_argument("--sample", type=int, help="port only the first N notes (trial run)")
    migrate_parser.add_argument("--all", action="store_true", help="port every note in the deck")
    doctor_parser = sub.add_parser("doctor", help="preflight checks")
    doctor_parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    run_parser = sub.add_parser("run", help="the nightly job")
    run_parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    run_parser.add_argument("--quiet", action="store_true", help="suppress per-note progress")
    args = parser.parse_args()

    if args.command == "init": init()
    elif args.command == "run": run(load_config(args.config), quiet=args.quiet)
    elif args.command == "migrate":
        if not args.all and not args.sample: raise SystemExit("pass --sample N for a trial run or --all to port the whole deck")
        migrate(load_config(args.config), None if args.all else args.sample)
    elif args.command == "doctor": return doctor(args.config)


if __name__ == "__main__": sys.exit(main())
