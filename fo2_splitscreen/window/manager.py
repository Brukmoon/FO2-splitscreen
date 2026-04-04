"""Window management: discovery, positioning, and borderless mode via Win32 API.

Windows-only module. All public functions raise RuntimeError on non-Windows.
"""

from __future__ import annotations

import ctypes
import logging
import os
import time

from ..constants import (
    GWL_STYLE,
    HWND_TOP,
    SWP_FRAMECHANGED,
    SWP_NOZORDER,
    WS_BORDER,
    WS_CAPTION,
    WS_DLGFRAME,
    WS_THICKFRAME,
)

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    import ctypes.wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong, ctypes.c_ulong)


def _require_windows() -> None:
    if not _IS_WINDOWS:
        raise RuntimeError("Window management requires Windows")


def find_window_by_pid(pid: int) -> int | None:
    """Find the main window handle for a given process ID."""
    _require_windows()
    result: list[int] = []

    @WNDENUMPROC
    def enum_callback(hwnd, lparam):
        proc_id = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(hwnd):
            result.append(hwnd)
        return True

    user32.EnumWindows(enum_callback, 0)
    return result[0] if result else None


def wait_for_window(pid: int, timeout: float = 30.0, poll_interval: float = 0.5) -> int:
    """Poll until a visible window appears for the given PID.

    Raises TimeoutError if no window found within timeout.
    """
    _require_windows()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = find_window_by_pid(pid)
        if hwnd is not None:
            logger.info("Found window 0x%X for PID %d", hwnd, pid)
            return hwnd
        time.sleep(poll_interval)
    raise TimeoutError(f"No window found for PID {pid} within {timeout}s")


def position_window(hwnd: int, x: int, y: int, width: int, height: int) -> None:
    """Move and resize a window."""
    _require_windows()
    success = user32.SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_NOZORDER)
    if not success:
        logger.warning("SetWindowPos failed for 0x%X", hwnd)
    else:
        logger.info("Positioned window 0x%X at (%d, %d, %d, %d)", hwnd, x, y, width, height)


def make_borderless(hwnd: int) -> None:
    """Remove window borders and title bar to create a borderless window."""
    _require_windows()
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    new_style = style & ~(WS_CAPTION | WS_THICKFRAME | WS_BORDER | WS_DLGFRAME)
    user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
    # SWP_NOMOVE=0x0002, SWP_NOSIZE=0x0001, SWP_NOZORDER=0x0004
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | 0x0001 | 0x0002 | 0x0004)
    logger.info("Made window 0x%X borderless", hwnd)


def set_window_focus(hwnd: int) -> None:
    """Bring a window to the foreground."""
    _require_windows()
    user32.SetForegroundWindow(hwnd)


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """Get window position and size as (x, y, width, height)."""
    _require_windows()
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
