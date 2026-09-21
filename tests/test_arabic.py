"""Arabic regression tests: transcription endpoint, auto-detect, no translation."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pith.config import Settings
from pith.groq_client import GroqClient
from test_groq_client import make_settings, stub_client

ARABIC = "مرحبا كيف حالك"


class FakeAudioEndpoint:
    """Captures transcription kwargs; stands in for the OpenAI audio namespace."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.kwargs: dict = {}
        self.calls = 0

    @property
    def transcriptions(self):
        outer = self

        class Transcriptions:
            @staticmethod
            def create(**kwargs):
                outer.calls += 1
                outer.kwargs = dict(kwargs)
                return SimpleNamespace(text=outer.text)

        return Transcriptions()

    @property
    def translations(self):
        raise AssertionError("must never use the translations endpoint")


def transcribe_with(text: str, **setting_overrides):
    client = GroqClient(make_settings(**setting_overrides))
    endpoint = FakeAudioEndpoint(text)
    client._client = SimpleNamespace(audio=endpoint)
    try:
        result = client.transcribe(io.BytesIO(b"fake-audio"), "dictation.wav")
    finally:
        client.close()
    return result, endpoint


class TestArabicTranscription:
    def test_arabic_audio_returns_arabic_script_not_english(self):
        text, endpoint = transcribe_with(ARABIC, language="ar")
        assert text == ARABIC
        assert endpoint.kwargs["language"] == "ar"
        assert "مرحبا" in text

    def test_auto_detect_omits_language_so_whisper_detects_arabic(self):
        text, endpoint = transcribe_with(ARABIC, language="")
        assert text == ARABIC
        assert "language" not in endpoint.kwargs

    def test_explicit_english_still_passes_through(self):
        text, endpoint = transcribe_with("hello there", language="en")
        assert text == "hello there"
        assert endpoint.kwargs["language"] == "en"

    def test_translations_endpoint_is_never_used(self):
        _, endpoint = transcribe_with(ARABIC, language="ar")
        assert endpoint.calls == 1  # transcriptions.create, exactly once


class TestLanguageDefaults:
    def test_missing_language_defaults_to_auto_detect(self, monkeypatch):
        for name in ("PITH_LANGUAGE", "POLLENSCRIBE_LANGUAGE"):
            monkeypatch.delenv(name, raising=False)
        assert Settings.from_env().language == ""

    def test_auto_spelling_maps_to_auto_detect(self, monkeypatch):
        monkeypatch.setenv("PITH_LANGUAGE", "auto")
        assert Settings.from_env().language == ""

    def test_arabic_code_survives_env_parsing(self, monkeypatch):
        monkeypatch.setenv("PITH_LANGUAGE", "ar")
        assert Settings.from_env().language == "ar"


class TestCleanupNeverTranslates:
    def test_arabic_transcript_is_kept_as_arabic(self):
        client, _ = stub_client({"primary-model": ARABIC}, fix_min_words=1)
        try:
            assert client.fix_transcript(ARABIC) == ARABIC
        finally:
            client.close()
