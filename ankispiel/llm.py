"Fresh example sentences from any OpenAI-compatible chat endpoint."

import json, os

from openai import OpenAI
from pydantic import BaseModel, field_validator

from ankispiel.config import AppConfig

LANG_NAMES = dict(en="English", de="German", es="Spanish", fr="French", it="Italian", pt="Portuguese", ru="Russian",
    ja="Japanese", zh="Chinese", ko="Korean", nl="Dutch", pl="Polish", tr="Turkish", hi="Hindi", ar="Arabic")


class Generated(BaseModel):
    sentences: list[str]
    translations: list[str]

    @field_validator("sentences", "translations")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v or not all(s.strip() for s in v): raise ValueError("empty sentence in LLM output")
        return v

    def validate_shape(self, n_min: int, n_max: int) -> None:
        if len(self.sentences) != len(self.translations): raise ValueError("sentence/translation count mismatch")
        if not n_min <= len(self.sentences) <= n_max:
            raise ValueError(f"expected {n_min}..{n_max} sentences, got {len(self.sentences)}")


def _lang(code: str) -> str: return LANG_NAMES.get(code.split("-")[0], code)

PROMPT = """\
You write example sentences for a vocabulary learner.

Write {n} example sentences in {target} that use the word "{word}" (meaning: {meaning}).
Each sentence must contain the word in a natural inflected form, stay at CEFR level
{level}, and be a standalone sentence a B1 learner can understand from context.
Do not reuse or closely paraphrase these earlier sentences: {avoid}.

Reply with JSON only, no markdown fences:
{{"sentences": ["...", ...], "translations": ["...", ...]}}
The translations are in {source}, one per sentence, same order.
"""


def generate(cfg: AppConfig, target_word: str, source_word: str, avoid: list[str]) -> tuple[Generated, int, int]:
    "Returns (generated, prompt_tokens, completion_tokens)."
    n_min, n_max = cfg.examples.min, cfg.examples.max
    n = n_min if n_min == n_max else f"{n_min} to {n_max}"
    client = OpenAI(base_url=cfg.provider.base_url, api_key=os.environ[cfg.provider.api_key_env],
        default_headers=cfg.provider.headers)
    prompt = PROMPT.format(n=n, target=_lang(cfg.languages.target), source=_lang(cfg.languages.source),
        word=target_word, meaning=source_word, level=cfg.languages.level, avoid=", ".join(avoid) or "none")
    response = client.chat.completions.create(model=cfg.provider.model, messages=[{"role": "user", "content": prompt}])
    content = response.choices[0].message.content
    if content.startswith("```"):  # strip a single markdown fence if present
        content = content.split("```")[1]
        content = content.removeprefix("json")
    generated = Generated.model_validate(json.loads(content))
    generated.validate_shape(n_min, n_max)
    usage = response.usage
    return generated, usage.prompt_tokens, usage.completion_tokens
