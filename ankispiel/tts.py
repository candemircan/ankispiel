"""Kokoro (ONNX) synthesis for one configured voice.

Weights/voices are fetched from Hugging Face on first use and cached by huggingface-hub.
Output is converted to mp3 via ffmpeg so collection.media stays small.
"""

import subprocess, tempfile
from pathlib import Path

import soundfile as sf
from huggingface_hub import hf_hub_download
from kokoro_onnx import Kokoro

from ankispiel.config import TtsVoiceConfig


class KokoroVoice:
    def __init__(self, cfg: TtsVoiceConfig):
        self.cfg = cfg
        model = hf_hub_download(cfg.model, cfg.model_file)
        voices = hf_hub_download(cfg.model, cfg.voices_file)
        self._kokoro = Kokoro(model, voices)

    def create(self, text: str):
        "Synthesizes `text`; returns (samples (1-D float array), sample_rate)."
        samples, sr = self._kokoro.create(text, voice=self.cfg.voice, speed=self.cfg.speed, lang=self.cfg.lang)
        return samples, sr

    def create_mp3(self, text: str) -> bytes:
        "Synthesizes `text` and returns mp3 bytes (ffmpeg, 48 kbps mono)."
        samples, sr = self.create(text)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
            sf.write(wav_file, samples, sr, format="WAV")
            wav_path = wav_file.name
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file: mp3_path = mp3_file.name
        try:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
                "-codec:a", "libmp3lame", "-b:a", "48k", mp3_path], check=True)
            return Path(mp3_path).read_bytes()
        finally:
            Path(wav_path).unlink()
            Path(mp3_path).unlink()
