"""Card templates for the ankispiel notetype.

The "Lexikon" card design: dictionary-paper serif, sentences always visible,
translations behind a tap-to-reveal (zero JavaScript). Slots must match the number of
example fields on the notetype; empty slots render nothing via the {{#exN}} conditionals.

XCharter (Bitstream Charter, freely licensed) ships via collection.media (FONT_FILES)
so all clients render the identical face.
"""

from importlib.resources import files

from ankispiel.config import ExtraField

_FONTS = files("ankispiel") / "fonts"
FONT_FILES = {
    _FONTS / "XCharter-Regular.otf": "_ankispiel-charter-regular.otf", _FONTS / "XCharter-Bold.otf": "_ankispiel-charter-bold.otf",
    _FONTS / "XCharter-Italic.otf": "_ankispiel-charter-italic.otf", _FONTS / "XCharter-BoldItalic.otf": "_ankispiel-charter-bolditalic.otf"}

STYLING = """\
/* Charter (XCharter OTFs, shipped via collection.media) so every client renders
   the identical face; falls back to system serif if missing. */
@font-face { font-family: "Charter"; src: url("_ankispiel-charter-regular.otf"); font-weight: 400; }
@font-face { font-family: "Charter"; src: url("_ankispiel-charter-bold.otf"); font-weight: 700; }
@font-face { font-family: "Charter"; src: url("_ankispiel-charter-italic.otf"); font-style: italic; font-weight: 400; }
@font-face { font-family: "Charter"; src: url("_ankispiel-charter-bolditalic.otf"); font-style: italic; font-weight: 700; }
.card {
  --bg: #faf6ee; --fg: #211c15; --muted: #4c453a; --faint: #8d8371;
  --rule: #c9bfa9; --accent: #8a5a2a;
  font-family: Charter, "Iowan Old Style", Palatino, Georgia, serif;
  background: var(--bg); color: var(--fg);
  padding: 2rem 1.25rem; text-align: left; line-height: 1.55;
}
/* Anki/AnkiDroid night mode adds .night_mode to the card body. */
.night_mode .card {
  --bg: #221e18; --fg: #e9e2d2; --muted: #bfb39c; --faint: #93896f;
  --rule: #4a4234; --accent: #d09a5c;
}
@media (prefers-color-scheme: dark) {
  .card {
    --bg: #221e18; --fg: #e9e2d2; --muted: #bfb39c; --faint: #93896f;
    --rule: #4a4234; --accent: #d09a5c;
  }
}
.word { font-size: 1.9rem; line-height: 1.25; }
.translation { font-style: italic; font-size: 1.25rem; color: var(--muted); margin-top: .4rem; }
.extra { font-style: italic; font-size: 1.25rem; color: var(--muted); margin-top: .4rem; }
hr.rule { border: 0; border-top: 3px double var(--rule); margin: 1.6rem 0 1.4rem; }
.ex { margin-bottom: 1.1rem; }
.sentence { font-size: 1.08rem; }
details.fn { font-size: .88rem; color: var(--muted); margin-top: .25rem; }
details.fn summary { display: inline; list-style: none; cursor: pointer; color: var(--accent); }
details.fn summary::-webkit-details-marker { display: none; }
details.fn summary::before { content: "※ "; font-size: .8rem; }
details.fn[open] summary { display: none; }
"""


def _examples(n_slots: int) -> str:
    return "\n".join(
        f"{{{{#ex{i}}}}}<div class=\"ex\"><div class=\"sentence\">{{{{ex{i}}}}} {{{{ex{i}a}}}}</div>"
        f"<details class=\"fn\"><summary>translation</summary>{{{{ex{i}t}}}}</details></div>{{{{/ex{i}}}}}"
        for i in range(1, n_slots + 1)
    )


def _extra_gloss(extra: list[ExtraField]) -> str:
    "Extra fields as translation-style lines; empty fields render nothing."
    return "".join(
        f'{{{{#{e.name}}}}}<div class="extra">{{{{{e.name}}}}}</div>\n{{{{/{e.name}}}}}'
        for e in extra
    )


def templates(n_slots: int, extra: list[ExtraField]) -> list[dict]:
    "Card templates in notetype ord order: original (target→source), reverse (source→target)."
    examples = _examples(n_slots)
    gloss = _extra_gloss(extra)
    original = dict(name="original",
        # Audio only on the back (answer), so gender/forms are heard on reveal, not before.
        qfmt='<div class="word">{{target_word}}</div>',
        afmt=(
            '<div class="word">{{target_word}} {{target_word_audio}}</div>\n'
            '<div class="translation">{{source_word}}</div>\n'
            f'{gloss}'
            '<hr class="rule">\n'
            f'<div class="examples">\n{examples}\n</div>'))
    reverse = dict(name="reverse",
        qfmt='<div class="word">{{source_word}}</div>',
        afmt=(
            '<div class="word">{{source_word}}</div>\n'
            '<div class="translation">{{target_word}} {{target_word_audio}}</div>\n'
            f'{gloss}'
            '<hr class="rule">\n'
            f'<div class="examples">\n{examples}\n</div>'))
    return [original, reverse]
