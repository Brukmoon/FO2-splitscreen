"""Window management: discovery, positioning, and borderless mode via Win32 API.

Windows-only module. All public functions raise RuntimeError on non-Windows.

FlatOut 2 launch flow:
  1. FlatOut2.exe starts -> shows a small launcher dialog
  2. User clicks "Play" -> game creates the actual render window
  3. We need to find the GAME window, not the launcher dialog

The game render window has class "BDX9 Render Window" and is much larger
than the launcher dialog. We detect it by size (>= 640x480).
"""

from __future__ import annotations

import ctypes
import logging
import os
import time

from ..constants import (
    GAME_WINDOW_CLASS,
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

# Minimum window size to be considered a game window (not the launcher dialog)
MIN_GAME_WINDOW_SIZE = (640, 400)


def _require_windows() -> None:
    if not _IS_WINDOWS:
        raise RuntimeError("Window management requires Windows")


def _get_window_class(hwnd: int) -> str:
    """Get the window class name."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _get_window_size(hwnd: int) -> tuple[int, int]:
    """Get window width and height."""
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (rect.right - rect.left, rect.bottom - rect.top)


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


def find_game_window_by_pid(pid: int) -> int | None:
    """Find the game render window for a given PID.

    Distinguishes the game window from the launcher dialog by checking:
    1. Window class name matches "BDX9 Render Window" (preferred)
    2. Falls back to the largest visible window >= 640x400
    """
    _require_windows()
    candidates: list[tuple[int, int, int, str]] = []  # (hwnd, width, height, class)

    @WNDENUMPROC
    def enum_callback(hwnd, lparam):
        proc_id = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value == pid and user32.IsWindowVisible(hwnd):
            w, h = _get_window_size(hwnd)
            cls = _get_window_class(hwnd)
            candidates.append((hwnd, w, h, cls))
        return True

    user32.EnumWindows(enum_callback, 0)

    if not candidates:
        return None

    # Prefer window with the expected game class
    for hwnd, w, h, cls in candidates:
        if cls == GAME_WINDOW_CLASS:
            logger.debug("Found game window by class '%s': 0x%X (%dx%d)", cls, hwnd, w, h)
            return hwnd

    # Fall back: pick the largest window that looks like a game window
    min_w, min_h = MIN_GAME_WINDOW_SIZE
    game_windows = [
        (hwnd, w, h) for hwnd, w, h, _ in candidates
        if w >= min_w and h >= min_h
    ]
    if game_windows:
        # Sort by area, pick largest
        game_windows.sort(key=lambda x: x[1] * x[2], reverse=True)
        hwnd, w, h = game_windows[0]
        logger.debug("Found game window by size: 0x%X (%dx%d)", hwnd, w, h)
        return hwnd

    return None


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


def wait_for_game_window(pid: int, timeout: float = 120.0, poll_interval: float = 1.0) -> int:
    """Wait for the actual game render window (not the launcher dialog).

    FlatOut 2 shows a launcher dialog first. The user must click "Play"
    before the game window appears. This function waits for the game window
    with a longer timeout.

    Raises TimeoutError if no game window found within timeout.
    """
    _require_windows()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = find_game_window_by_pid(pid)
        if hwnd is not None:
            logger.info("Found game window 0x%X for PID %d", hwnd, pid)
            return hwnd
        time.sleep(poll_interval)
    raise TimeoutError(
        f"No game window found for PID {pid} within {timeout}s. "
        f"Did you click 'Play' in the launcher?"
    )


def position_window(hwnd: int, x: int, y: int, width: int, height: int) -> None:
    """Move and resize a window. Retries to handle dgVoodoo2/D3D9 wrapper timing."""
    _require_windows()
    for attempt in range(3):
        success = user32.SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_NOZORDER)
        if success:
            # Verify the position actually stuck (dgVoodoo2 may override)
            actual = get_window_rect(hwnd)
            if abs(actual[0] - x) <= 2 and abs(actual[1] - y) <= 2:
                logger.info(
                    "Positioned window 0x%X at (%d, %d, %d, %d)",
                    hwnd, x, y, width, height,
                )
                return
            logger.debug(
                "Window 0x%X moved to (%d, %d) instead of (%d, %d), retrying...",
                hwnd, actual[0], actual[1], x, y,
            )
        if attempt < 2:
            time.sleep(1.0)
    logger.warning("SetWindowPos may not have applied correctly for 0x%X", hwnd)


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
