"""Environment-backed configuration for Pith.

Every tunable lives here so the rest of the package can accept a `Settings`
object instead of reaching for `os.getenv` at call sites.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "Pith"

TOGGLE_HOTKEY = "ctrl+shift+space"
UI_HOTKEY = "ctrl+shift+p"
CANCEL_HOTKEY = "esc"
STOP_HOTKEY = "enter"

SAMPLE_RATE = 16_000
CHANNELS = 1
DTYPE = "int16"
BYTES_PER_SAMPLE = 2

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_STT_MODEL = "whisper-large-v3"
DEFAULT_STT_FALLBACK = "whisper-large-v3-turbo"
DEFAULT_FIX_MODEL = "qwen/qwen3.8-27b"
DEFAULT_FIX_FALLBACK = "qwen/qwen3.6-27b"

# Groq caps direct uploads at 25 MB on the free tier.
UPLOAD_LIMIT_BYTES = 25 * 1024 * 1024

ICON_FILE = "pith.ico"


def app_dir() -> Path:
    """Directory the app treats as home for `.env` and side-by-side assets."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_path(name: str) -> Path:
    """Locate a bundled asset, honouring PyInstaller's extraction directory."""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidate = Path(bundle) / name
        if candidate.is_file():
            return candidate
    return app_dir() / name


def load_env() -> None:
    """Load `.env` from beside the executable, then fall back to a cwd search.

    The most common support issue with the packaged build was a `.env` that
    `load_dotenv()` could not see because the working directory was elsewhere.
    """
    local = app_dir() / ".env"
    if local.is_file():
        load_dotenv(local)
    load_dotenv()


LEGACY_PREFIX = "POLLENSCRIBE_"


def _raw(name: str) -> str | None:
    """Read `name`, falling back to the pre-rename `POLLENSCRIBE_` spelling.

    The app was called PollenScribe until 2.0. Keeping the old prefix readable
    means an existing `.env` still configures the app it was written for, so the
    rename costs nobody a support ticket.
    """
    value = os.getenv(name)
    if value is None and name.startswith("PITH_"):
        value = os.getenv(LEGACY_PREFIX + name.removeprefix("PITH_"))
    return value


def _text(name: str, default: str) -> str:
    raw = _raw(name)
    return default if raw is None else raw.strip()


def _flag(name: str, default: bool) -> bool:
    raw = _raw(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int((_raw(name) or "").strip() or default))
    except ValueError:
        return default


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float((_raw(name) or "").strip() or default))
    except ValueError:
        return default


def _normalize_language(raw: str) -> str:
    """Blank (auto-detect) by default so Arabic is transcribed, not forced to English."""
    lang = (raw or "").strip().lower()
    if lang in ("", "auto", "auto-detect", "autodetect", "none", "null"):
        return ""
    return lang


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    stt_model: str
    stt_fallback: str
    language: str
    fix_enabled: bool
    fix_model: str
    fix_fallback: str
    fix_min_words: int
    fix_timeout: float
    stop_on_enter: bool
    keep_clipboard: bool
    clipboard_restore_ms: int
    leading_space: bool
    history_size: int
    silence_threshold: int
    trim_padding_ms: int
    flac_threshold_bytes: int
    max_seconds: int
    request_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            api_key=_text("GROQ_API_KEY", ""),
            base_url=_text("GROQ_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL,
            stt_model=_text("PITH_STT_MODEL", DEFAULT_STT_MODEL),
            stt_fallback=_text("PITH_STT_FALLBACK", DEFAULT_STT_FALLBACK),
            language=_normalize_language(_text("PITH_LANGUAGE", "")),
            fix_enabled=_flag("PITH_FIX", True),
            fix_model=_text("PITH_FIX_MODEL", DEFAULT_FIX_MODEL),
            fix_fallback=_text("PITH_FIX_FALLBACK", DEFAULT_FIX_FALLBACK),
            fix_min_words=_int("PITH_FIX_MIN_WORDS", 4),
            fix_timeout=_float("PITH_FIX_TIMEOUT", 4.0, minimum=0.5),
            stop_on_enter=_flag("PITH_STOP_ON_ENTER", True),
            keep_clipboard=_flag("PITH_KEEP_CLIPBOARD", True),
            clipboard_restore_ms=_int("PITH_CLIPBOARD_RESTORE_MS", 250),
            leading_space=_flag("PITH_LEADING_SPACE", False),
            history_size=_int("PITH_HISTORY_SIZE", 5),
            silence_threshold=_int("PITH_SILENCE_THRESHOLD", 500),
            trim_padding_ms=_int("PITH_TRIM_PADDING_MS", 250),
            flac_threshold_bytes=_int("PITH_FLAC_THRESHOLD_KB", 600) * 1024,
            max_seconds=_int("PITH_MAX_SECONDS", 600, minimum=5),
            request_timeout=_float("PITH_REQUEST_TIMEOUT", 60.0, minimum=5.0),
        )

    def require_api_key(self) -> str:
        if self.api_key:
            return self.api_key
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file next to the app, or set it "
            "as a Windows environment variable. Get a key at https://console.groq.com/keys "
            "(this replaces the old POLLINATIONS_API_KEY setting)."
        )
