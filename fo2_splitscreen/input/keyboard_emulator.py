"""Controller-to-keyboard emulation: reads gamepad, injects key events into game windows.

Uses SendInput via ctypes for reliable keyboard injection regardless of window focus.
Falls back to PostMessage for targeting specific windows.

Windows-only module.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time

from .controller import ControllerReader
from .input_config import ControllerProfile

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt"

# Win32 constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

if _IS_WINDOWS:
    import ctypes.wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.wintypes.WORD),
            ("wScan", ctypes.wintypes.WORD),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]

        _anonymous_ = ("_input",)
        _fields_ = [
            ("type", ctypes.wintypes.DWORD),
            ("_input", _INPUT),
        ]


def _send_key(vk: int, down: bool) -> None:
    """Send a keyboard event using SendInput."""
    if not _IS_WINDOWS:
        return
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki.wVk = vk
    inp.ki.dwFlags = 0 if down else KEYEVENTF_KEYUP
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))  # type: ignore[attr-defined]


def _post_key(hwnd: int, vk: int, down: bool) -> None:
    """Send a keyboard event to a specific window using PostMessage."""
    if not _IS_WINDOWS:
        return
    msg = WM_KEYDOWN if down else WM_KEYUP
    ctypes.windll.user32.PostMessageW(hwnd, msg, vk, 0)  # type: ignore[attr-defined]


class KeyboardEmulator:
    """Maps controller input to keyboard events for a single game instance."""

    def __init__(
        self,
        controller_index: int,
        profile: ControllerProfile,
        target_hwnd: int | None = None,
        poll_rate: float = 1 / 60,
    ) -> None:
        if not _IS_WINDOWS:
            raise RuntimeError("Keyboard emulation requires Windows")
        self.reader = ControllerReader(controller_index)
        self.profile = profile
        self.target_hwnd = target_hwnd
        self.poll_rate = poll_rate
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._button_state: dict[int, bool] = {}
        self._axis_state: dict[tuple[int, str], bool] = {}

    def _send(self, vk: int, down: bool) -> None:
        if self.target_hwnd:
            _post_key(self.target_hwnd, vk, down)
        else:
            _send_key(vk, down)

    def _poll_once(self) -> None:
        import pygame
        pygame.event.pump()

        buttons = self.reader.read_buttons()
        axes = self.reader.read_axes()

        for mapping in self.profile.buttons:
            if mapping.button_index >= len(buttons):
                continue
            pressed = buttons[mapping.button_index]
            was_pressed = self._button_state.get(mapping.button_index, False)
            if pressed and not was_pressed:
                self._send(mapping.key, True)
            elif not pressed and was_pressed:
                self._send(mapping.key, False)
            self._button_state[mapping.button_index] = pressed

        for mapping in self.profile.axes:
            if mapping.axis_index >= len(axes):
                continue
            value = axes[mapping.axis_index]

            neg_pressed = value < -mapping.threshold
            pos_pressed = value > mapping.threshold

            neg_key = (mapping.axis_index, "neg")
            pos_key = (mapping.axis_index, "pos")

            was_neg = self._axis_state.get(neg_key, False)
            was_pos = self._axis_state.get(pos_key, False)

            if neg_pressed and not was_neg:
                self._send(mapping.negative_key, True)
            elif not neg_pressed and was_neg:
                self._send(mapping.negative_key, False)

            if pos_pressed and not was_pos:
                self._send(mapping.positive_key, True)
            elif not pos_pressed and was_pos:
                self._send(mapping.positive_key, False)

            self._axis_state[neg_key] = neg_pressed
            self._axis_state[pos_key] = pos_pressed

    def _run(self) -> None:
        logger.info("Keyboard emulator started (controller %d)", self.reader.joystick.get_id())
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                logger.exception("Error in input polling loop")
            time.sleep(self.poll_rate)
        # Release all pressed keys
        for btn_idx, pressed in self._button_state.items():
            if pressed:
                mapping = next(
                    (m for m in self.profile.buttons if m.button_index == btn_idx), None
                )
                if mapping:
                    self._send(mapping.key, False)
        logger.info("Keyboard emulator stopped")

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
