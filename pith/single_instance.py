"""Single-instance guard: one Pith process owns the global hotkeys.

Running twice used to install two low-level keyboard hooks for the same
chords. The `keyboard` library suppresses and fake-replays modifier events to
make suppression work (see its `_KeyboardListener.transition_table`), so two
hooks competing over Ctrl/Shift produced the synthetic Shift/Ctrl events from
the report and could swallow the real key-up, leaving Shift/Ctrl "stuck" in
games and browsers until the next press. Exiting the second process before it
binds anything removes the whole class of failure.
"""

from __future__ import annotations

import ctypes
import sys

MUTEX_NAME = "Global\\PithDictationSingleInstance"

_ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """Windows named-mutex guard. Use as a context manager or via acquire()."""

    def __init__(self, name: str = MUTEX_NAME) -> None:
        self._name = name
        self._handle = None
        self._owned = False

    def acquire(self) -> bool:
        """Return True when this process is the single owner, False otherwise."""
        if sys.platform != "win32":
            # Non-Windows (tests, dev machines): fail open, there is no hook.
            self._owned = True
            return True
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateMutexW(None, False, self._name)
            if not handle:
                # Could not create the mutex at all; fail open rather than
                # refusing to start over a guard malfunction.
                self._owned = True
                return True
            already_exists = kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
            if already_exists:
                kernel32.CloseHandle(handle)
                self._owned = False
                return False
            self._handle = handle
            self._owned = True
            return True
        except Exception:
            # ctypes failures must never prevent dictation from starting.
            self._owned = True
            return True

    def release(self) -> None:
        if sys.platform != "win32":
            self._owned = False
            return
        handle, self._handle = self._handle, None
        self._owned = False
        if handle:
            try:
                ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass

    @property
    def owned(self) -> bool:
        return self._owned

    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, *exc_info) -> None:
        self.release()
