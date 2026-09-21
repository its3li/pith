"""Session orchestration: hotkeys, recording state, and the dictation pipeline."""

from __future__ import annotations

import sys
import threading
import time
from queue import Queue

import keyboard
import winsound

from .audio import AudioRecorder, encode_for_upload, trim_silence
from .config import (
    CANCEL_HOTKEY,
    SAMPLE_RATE,
    STOP_HOTKEY,
    TOGGLE_HOTKEY,
    UI_HOTKEY,
    UPLOAD_LIMIT_BYTES,
    Settings,
    load_env,
)
from .groq_client import GroqClient, describe_error
from .paste import apply_leading_space, get_foreground_window, paste_text
from .single_instance import SingleInstance
from .status import History, StatusBus, log

# Ignore a stop that lands within this window of a start: it is a double-tap, and
# the near-empty recording that used to result just failed at the API.
DEBOUNCE_SECONDS = 0.25


def beep(frequency: int) -> None:
    """Sound a cue without blocking the caller.

    winsound.Beep blocks for its full duration, which previously added 120 ms to
    the stop path before transcription could even begin.
    """

    def play() -> None:
        try:
            winsound.Beep(frequency, 120)
        except RuntimeError:
            winsound.MessageBeep(winsound.MB_OK)

    threading.Thread(target=play, daemon=True).start()


def preview(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


class DictationApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bus = StatusBus()
        self.history = History(settings.history_size)
        self.recorder = AudioRecorder(settings, self.bus)
        self.client = GroqClient(settings)

        self._lock = threading.Lock()
        self._recording = False
        self._started_at = 0.0
        self._target_window: int | None = None
        self._session_hotkeys: list = []
        self._global_hotkeys: list = []

        # Suppressed hotkeys fire on the Windows low-level hook thread, which
        # Windows silently unhooks if a callback overruns its timeout. So the
        # hook thread only ever enqueues, and this thread does the work, in the
        # order the keys were pressed.
        self._actions: Queue = Queue()
        self._pump_thread = threading.Thread(target=self._pump, daemon=True)

    def _pump(self) -> None:
        while True:
            action = self._actions.get()
            if action is None:
                return
            try:
                action()
            except Exception as exc:  # A bad keypress must not kill the pump.
                log(f"Unhandled error while handling a hotkey: {exc}")

    def _queued(self, action):
        """Wrap `action` so the hook thread returns immediately."""

        def handler() -> None:
            self._actions.put(action)

        return handler

    # -- recording lifecycle ------------------------------------------------

    def toggle(self) -> None:
        with self._lock:
            recording = self._recording
        if recording:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._started_at = time.monotonic()
            self._target_window = get_foreground_window()

        try:
            self.recorder.start()
        except Exception as exc:
            with self._lock:
                self._recording = False
            log(f"Could not start recording: {exc}")
            self.bus.set_status("Microphone error", str(exc))
            self.bus.hide(2500)
            return

        # Re-warm while the user is still speaking, so the upload never waits on
        # a TLS handshake.
        self.client.prewarm()
        self._bind_session_hotkeys()
        self.bus.show()
        self.bus.set_status("Recording...", self._recording_hint())
        beep(880)
        log("Recording...")

    def _recording_hint(self) -> str:
        """Name only the keys that are actually bound for this recording."""
        stop = f"{TOGGLE_HOTKEY} or Enter" if self.settings.stop_on_enter else TOGGLE_HOTKEY
        return f"Esc cancels · {stop} stops"

    def stop(self, cancel: bool = False) -> None:
        with self._lock:
            if not self._recording:
                return
            if not cancel and time.monotonic() - self._started_at < DEBOUNCE_SECONDS:
                return  # Still recording: swallow the double-tap, do not cancel.
            self._recording = False
            hwnd = self._target_window
            self._target_window = None

        self._unbind_session_hotkeys()
        audio = self.recorder.stop()
        beep(660)

        if cancel:
            log("Recording cancelled.")
            self.bus.set_status("Cancelled", "Recording discarded")
            self.bus.hide(900)
            return

        if self.recorder.overflowed:
            log(f"Recording reached the {self.settings.max_seconds}s limit and was cut short.")

        # A dedicated thread per dictation, so starting the next one never waits
        # on the previous transcription to come back.
        self._spawn_processing(audio, hwnd)

    def _spawn_processing(self, audio, hwnd: int | None) -> None:
        threading.Thread(target=self._process, args=(audio, hwnd), daemon=True).start()

    def cancel(self) -> None:
        self.stop(cancel=True)

    def toggle_pause(self) -> None:
        with self._lock:
            if not self._recording:
                return
        paused = self.recorder.toggle_pause()
        if paused:
            self.bus.set_status("Paused", "Same key resumes")
        else:
            self.bus.set_status("Recording...", self._recording_hint())

    # -- transcription pipeline ---------------------------------------------

    def _process(self, audio, hwnd: int | None) -> None:
        settings = self.settings
        try:
            trimmed = trim_silence(audio, settings.silence_threshold, settings.trim_padding_ms)
            if trimmed.size == 0:
                # Nothing crossed the silence threshold, so there is nothing to
                # send. Previously this uploaded a silent clip and surfaced an
                # API error as if something had gone wrong.
                log("No speech detected; nothing was sent.")
                self.bus.set_status("No speech detected", "Nothing to transcribe")
                self.bus.hide(1500)
                return

            payload, filename = encode_for_upload(trimmed, settings.flac_threshold_bytes)
            size = payload.getbuffer().nbytes
            if size > UPLOAD_LIMIT_BYTES:
                raise RuntimeError(
                    f"The recording is {size / 1_048_576:.1f} MB, over the "
                    f"{UPLOAD_LIMIT_BYTES / 1_048_576:.0f} MB upload limit. Try a shorter dictation."
                )

            seconds = trimmed.size / SAMPLE_RATE
            log(f"Transcribing {seconds:.1f}s ({size / 1024:.0f} KB as {filename})...")
            self.bus.set_status("Transcribing...", "")

            started = time.monotonic()
            text = self.client.transcribe(payload, filename)

            if settings.fix_enabled and len(text.split()) >= settings.fix_min_words:
                # Named explicitly so the extra second reads as a step rather
                # than a stall.
                self.bus.set_status("Polishing...", "")
            text = self.client.fix_transcript(text)
            log(f"Transcribed in {time.monotonic() - started:.2f}s: {preview(text)}")

            text = apply_leading_space(text, settings.leading_space)
            self.history.add(text)
            self._deliver(text, hwnd)
        except Exception as exc:
            message = describe_error(exc)
            log(f"Error: {message}")
            self.bus.set_status("Error", message)
            self.bus.hide(3000)

    def _deliver(self, text: str, hwnd: int | None) -> None:
        pasted = paste_text(text, hwnd, self.settings.keep_clipboard, self.settings.clipboard_restore_ms)
        if pasted:
            self.bus.set_status("Pasted", preview(text))
            self.bus.hide(1200)
            return

        # Focus moved during the round trip. The text is on the clipboard and in
        # the tray history, so nothing is lost.
        log("Focus changed, so the text was left on the clipboard instead.")
        self.bus.set_status("Copied to clipboard", "Focus moved, so Ctrl+V to paste")
        self.bus.hide(2600)
        winsound.MessageBeep(winsound.MB_ICONASTERISK)

    # -- hotkeys -------------------------------------------------------------

    def _bind_global_hotkeys(self) -> None:
        # Deliberately NOT suppressed. The `keyboard` library implements
        # suppression by holding Ctrl/Shift in a pending/suppressed state and
        # fake-replaying them (transition_table in keyboard/__init__.py). For a
        # chord built on two modifiers, the real modifier key-up is swallowed
        # after the hotkey fires ('suppressed', KEY_UP, 'modifier') -> blocked,
        # so the focused game/browser never sees the release and Shift/Ctrl
        # reads as stuck. With suppress=False the hook observes without
        # touching modifier delivery, and our own injected Ctrl+V paste is
        # already ignored by the library (is_replaying pass-through), so there
        # is no recursion either way. Ctrl+Shift+Space / Ctrl+Shift+P have no
        # destructive default action underneath, so letting them through is safe.
        self._global_hotkeys = [
            self._bind(TOGGLE_HOTKEY, self.toggle, suppress=False),
            self._bind(UI_HOTKEY, self.bus.toggle, suppress=False),
        ]

    def _bind_session_hotkeys(self) -> None:
        """Bind Esc, and optionally Enter, only for the life of the recording.

        This is the fix for the reported bug: a global Enter hook fired on every
        Enter press system-wide and, registered without suppression, still
        reached the focused app -- which is how a half-typed Discord message got
        sent by the keypress that was meant to stop the recording.
        """
        bindings = [self._bind(CANCEL_HOTKEY, self.cancel, suppress=True)]
        if self.settings.stop_on_enter:
            bindings.append(self._bind(STOP_HOTKEY, self.stop, suppress=True))
        self._session_hotkeys = [handle for handle in bindings if handle is not None]

    def _unbind_session_hotkeys(self) -> None:
        for handle in self._session_hotkeys:
            self._unbind(handle)
        self._session_hotkeys = []

    def _bind(self, combo: str, action, suppress: bool = True):
        try:
            return keyboard.add_hotkey(combo, self._queued(action), suppress=suppress)
        except Exception as exc:
            log(f"Could not register {combo}: {exc}")
            return None

    @staticmethod
    def _unbind(handle) -> None:
        if handle is None:
            return
        try:
            keyboard.remove_hotkey(handle)
        except (KeyError, ValueError):
            pass  # Already gone; nothing to undo.

    # -- lifecycle -----------------------------------------------------------

    def shutdown(self) -> None:
        """Release the microphone, hotkeys, and pooled connection.

        Quitting used to leave an active stream and the global hooks in place.
        Safe to call twice: the tray Quit action and the exec() teardown both do.
        """
        with self._lock:
            self._recording = False
        self._unbind_session_hotkeys()
        for handle in self._global_hotkeys:
            self._unbind(handle)
        self._global_hotkeys = []
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self._actions.put(None)
        try:
            self.recorder.close()
        except Exception:
            pass
        self.client.close()

    def run(self) -> int:
        # Imported here so the module stays importable (and testable) without Qt.
        from PySide6.QtWidgets import QApplication

        from .ui import PollenTrayIcon, StatusWidget

        qt_app = QApplication(sys.argv)
        # Qt now owns the main thread, rather than running in a daemon thread
        # while keyboard.wait() blocked here.
        QApplication.setQuitOnLastWindowClosed(False)

        # Routed through the same queue as the hotkeys, so every state change
        # happens on one thread and the UI never blocks on the microphone.
        widget = StatusWidget(
            self.bus, self._queued(self.toggle_pause), self._queued(self.cancel)
        )
        tray = PollenTrayIcon(widget, self.history, self.shutdown)
        tray.show()

        self.client.prewarm()
        self._pump_thread.start()
        self._bind_global_hotkeys()
        log(f"Ready in tray. {TOGGLE_HOTKEY} to dictate, {UI_HOTKEY} to show or hide the overlay.")
        self.bus.set_status("Ready in tray", f"{TOGGLE_HOTKEY} to dictate")

        try:
            return qt_app.exec()
        finally:
            self.shutdown()


def main() -> int:
    if sys.platform != "win32":
        log("Pith needs Windows: it uses winsound, user32, and the system tray.")
        return 1

    guard = SingleInstance()
    if not guard.acquire():
        log("Pith is already running; this second copy is exiting without binding hotkeys.")
        return 0

    load_env()
    settings = Settings.from_env()
    try:
        settings.require_api_key()
    except RuntimeError as exc:
        log(f"Error: {exc}")
        guard.release()
        return 1

    try:
        return DictationApp(settings).run()
    finally:
        guard.release()
