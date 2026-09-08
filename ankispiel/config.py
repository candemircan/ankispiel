import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

CONFIG_PATH = Path.home() / ".config/ankispiel/config.toml"
STATE_DIR = Path.home() / ".local/share/ankispiel"


class ProviderConfig(BaseModel):
    "Any OpenAI-compatible chat endpoint."

    base_url: str
    model: str
    api_key_env: str = "ANKISPIEL_API_KEY"
    headers: dict[str, str] = {}  # extra request headers (e.g. a gateway session header)
    request_delay: float = 0.0  # seconds to pause after each request, for rate-limited tiers
    input_price_per_mtok: float | None = None  # USD per 1M tokens, for the run report
    output_price_per_mtok: float | None = None

    @model_validator(mode="after")
    def _prices_paired(self) -> "ProviderConfig":
        if (self.input_price_per_mtok is None) != (self.output_price_per_mtok is None):
            raise ValueError("set both input_price_per_mtok and output_price_per_mtok, or neither")
        return self


class AnkiConfig(BaseModel):
    url: str = "http://localhost:8765"
    deck: str
    new_notes_per_night: int = 20


class LanguagePair(BaseModel):
    source: str  # BCP-47 code of the language the user knows, e.g. "en"
    target: str  # BCP-47 code of the language being learned, e.g. "de"
    level: str = "B1"  # CEFR level for generated sentences


class ExamplesConfig(BaseModel):
    "Example slots filled per note each night; min == max means a fixed number."

    min: int = 2
    max: int = 2


class HistoryConfig(BaseModel):
    k: int = 3


class TtsVoiceConfig(BaseModel):
    """One language's voice. For official Kokoro voices, model is hexgrad/Kokoro-82M
    and voice the official name; community voices point model/model_file/voices_file
    at their repos."""

    engine: Literal["kokoro"]
    voice: str
    lang: str  # espeak code, e.g. "de"
    speed: float = 1.125
    model: str
    model_file: str
    voices_file: str


class NotifyConfig(BaseModel):
    ntfy_url: str | None = None


class MigrateConfig(BaseModel):
    legacy_notetype: str
    source_word_field: str
    target_word_field: str
    new_notetype: str = "ankispiel"
    full_form_field: str | None = None  # spoken audio source, up to first comma ("die Bitte")


class ExtraField(BaseModel):
    "A legacy field carried over and shown under the translation on the answer."

    name: str  # field name on the ankispiel note type
    legacy_field: str  # field in the legacy note type it copies from
    strip_word: bool = False  # remove the target word ("die Bitte, -n" -> "die, -n")


class AppConfig(BaseModel):
    provider: ProviderConfig
    anki: AnkiConfig
    languages: LanguagePair
    examples: ExamplesConfig = ExamplesConfig()
    history: HistoryConfig = HistoryConfig()
    tts: dict[str, TtsVoiceConfig]
    notify: NotifyConfig = NotifyConfig()
    migrate: MigrateConfig
    extra: list[ExtraField] = []


def load_config(path: Path) -> AppConfig: return AppConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


EXAMPLE_CONFIG_TOML = """\
# ankispiel configuration. Written by `ankispiel init`, validated by `ankispiel doctor`.

[provider]
# Any OpenAI-compatible chat endpoint.
base_url = "https://your-provider/v1"
model = "your-model"
api_key_env = "ANKISPIEL_API_KEY"
# Optional: pause N seconds after each request, to respect a rate-limited free tier.
# request_delay = 4.0
# Optional: USD per 1M tokens, shown as the run cost in the report. Set both or neither.
# input_price_per_mtok = 0.15
# output_price_per_mtok = 0.60
# Optional: extra request headers, e.g. a gateway that requires a session header.
# [provider.headers]
# x-opencode-session = "ankispiel"

[anki]
# AnkiConnect on the headless Anki instance.
url = "http://localhost:8765"
deck = "B1 Goethe"
# Beyond cards due tomorrow, how many notes deep into the new-card queue to fill.
new_notes_per_night = 20

[languages]
source = "en"  # the language you know
target = "de"  # the language you are learning

[examples]
# Fixed number (min == max) or a range the model may choose within.
min = 2
max = 2

[history]
# Last-k fresh sentences per note passed to the prompt as "avoid these".
k = 3

[tts.de]
# Kokoro-ONNX with the community German voice "Martin"
# (https://huggingface.co/Godelaune/Kokoro-82M-ONNX-German-Martin).
engine = "kokoro"
voice = "martin"
lang = "de"
speed = 1.125
model = "Godelaune/Kokoro-82M-ONNX-German-Martin"
model_file = "kokoro-martin.onnx"
voices_file = "voices-martin.npz"

[notify]
# Optional ntfy topic for the nightly report. Leave empty to disable.
# ntfy_url = "https://ntfy.sh/ankispiel-mytopic"

[migrate]
# One-time port of the existing deck: field mapping from the legacy notetype.
legacy_notetype = "B1 goethe"
source_word_field = "english"
target_word_field = "german"
new_notetype = "ankispiel"
# Optional: field to speak as the word audio (played on reveal), taken up to the first
# comma so "die Bitte, -n" is spoken as "die Bitte". Unset -> the target word is spoken.
# full_form_field = "german_full"

# Optional: legacy fields carried over, each shown under the translation on the answer
# (same style as the translation). Repeat the block for more fields. strip_word removes
# the target word from the value, e.g. a "die Bitte, -n" field becomes "die, -n".
# [[extra]]
# name = "forms"
# legacy_field = "full_form"
# strip_word = true
"""
