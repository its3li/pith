"""Hotkey and single-instance regression tests.

Root cause these lock in: the `keyboard` library implements suppression by
holding Ctrl/Shift pending/suppressed and fake-replaying them, so a globally
suppressed Ctrl+Shift chord swallows the real modifier key-up and Shift/Ctrl
reads as stuck in games/browsers. A second process doubles the effect. Global
hotkeys must therefore observe (suppress=False); only the short-lived
recording session (Esc/Enter) may suppress.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pith import app as app_module
from pith.app import DictationApp
from pith.single_instance import SingleInstance
from test_groq_client import make_settings


class RecordingKeyboard:
    """Stands in for `keyboard`: records suppress flags, tracks bindings."""

    def __init__(self) -> None:
        self.bindings: dict[str, bool] = {}
        self.handles: list[str] = []
        self.unhooked_all = 0
        self.sent: list[str] = []

    def add_hotkey(self, combo, handler, suppress=False):
        self.bindings[combo] = suppress
        self.handles.append(combo)
        return combo

    def remove_hotkey(self, handle):
        self.handles.remove(handle)

    def unhook_all_hotkeys(self):
        self.unhooked_all += 1
        self.handles.clear()

    def press_and_release(self, combo):
        # Mirrors the real library: synthetic sends are marked replaying so the
        # process's own hooks pass them through instead of re-triggering.
        self.sent.append(combo)


@pytest.fixture
def hooked(monkeypatch):
    import numpy as np

    class FakeRecorder:
        def __init__(self) -> None:
            self.overflowed = False

        def start(self) -> None:
            pass

        def stop(self):
            return np.zeros(0, dtype=np.int16)

        def close(self) -> None:
            pass

        def toggle_pause(self) -> bool:
            return False

    kb = RecordingKeyboard()
    monkeypatch.setattr(app_module, "keyboard", kb)
    monkeypatch.setattr(app_module, "beep", lambda _frequency: None)
    instance = DictationApp(make_settings(stop_on_enter=True))
    instance.recorder = FakeRecorder()
    instance.client = SimpleNamespace(prewarm=lambda: None, close=lambda: None)
    instance.bound = kb
    return instance, kb


class TestGlobalHotkeysDoNotSwallowModifiers:
    def test_toggle_and_overlay_observe_without_suppressing(self, hooked):
        instance, kb = hooked
        instance._bind_global_hotkeys()
        assert kb.bindings["ctrl+shift+space"] is False
        assert kb.bindings["ctrl+shift+p"] is False

    def test_session_esc_and_enter_suppress_only_while_recording(self, hooked):
        instance, kb = hooked
        instance._bind_global_hotkeys()
        instance.start()
        assert kb.bindings["esc"] is True
        assert kb.bindings["enter"] is True
        instance.cancel()
        assert "esc" not in kb.handles
        assert "enter" not in kb.handles

    def test_shutdown_releases_everything_even_after_failure(self, hooked):
        instance, kb = hooked
        instance._bind_global_hotkeys()
        instance.start()
        instance.shutdown()
        assert kb.handles == []
        assert kb.unhooked_all >= 1
        instance.shutdown()  # Safe to call twice (tray Quit + exec teardown).
        assert kb.handles == []

    def test_synthetic_paste_is_marked_replayable_not_reentrant(self, hooked):
        _, kb = hooked
        kb.press_and_release("ctrl+v")
        assert kb.sent == ["ctrl+v"]
        # No binding matches a bare ctrl+v, so even if it were seen it could
        # never retrigger the toggle chord.
        assert "ctrl+v" not in kb.bindings


class TestSingleInstance:
    def test_second_owner_is_rejected_while_first_holds_the_mutex(self):
        first = SingleInstance("Local\\PithTestMutex")
        second = SingleInstance("Local\\PithTestMutex")
        assert first.acquire() is True
        try:
            assert second.acquire() is False
        finally:
            first.release()
            second.release()

    def test_mutex_is_reacquirable_after_release(self):
        guard = SingleInstance("Local\\PithTestMutexReacquire")
        assert guard.acquire() is True
        guard.release()
        assert guard.acquire() is True
        guard.release()

    def test_context_manager_releases(self):
        with SingleInstance("Local\\PithTestMutexCtx") as guard:
            assert guard.owned is True
        assert guard.owned is False
