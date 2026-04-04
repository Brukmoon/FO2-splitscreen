"""Screen/monitor geometry detection using ctypes.

Windows-only module. Functions raise RuntimeError on non-Windows.
"""

from __future__ import annotations

import ctypes
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    import ctypes.wintypes


@dataclass
class MonitorInfo:
    x: int
    y: int
    width: int
    height: int
    is_primary: bool


def get_primary_monitor() -> MonitorInfo:
    """Get the primary monitor dimensions via GetSystemMetrics."""
    if not _IS_WINDOWS:
        raise RuntimeError("Monitor detection requires Windows")
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
    h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
    return MonitorInfo(x=0, y=0, width=w, height=h, is_primary=True)


def get_all_monitors() -> list[MonitorInfo]:
    """Enumerate all monitors using EnumDisplayMonitors."""
    if not _IS_WINDOWS:
        raise RuntimeError("Monitor detection requires Windows")

    monitors: list[MonitorInfo] = []
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]

    MONITORINFOF_PRIMARY = 0x00000001

    class MONITORINFOEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork", ctypes.wintypes.RECT),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    @ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.wintypes.RECT),
        ctypes.c_double,
    )
    def monitor_enum_proc(hmonitor, hdc, lprect, lparam):
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
        rc = info.rcMonitor
        monitors.append(MonitorInfo(
            x=rc.left,
            y=rc.top,
            width=rc.right - rc.left,
            height=rc.bottom - rc.top,
            is_primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
        ))
        return 1

    user32.EnumDisplayMonitors(None, None, monitor_enum_proc, 0)

    if not monitors:
        logger.warning("EnumDisplayMonitors returned no monitors, falling back to primary")
        return [get_primary_monitor()]

    return monitors
