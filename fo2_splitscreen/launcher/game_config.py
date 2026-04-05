"""Read and modify FlatOut 2 configuration files (device.cfg, options.cfg).

device.cfg is a binary file. Resolution is stored as two uint32 values at offset 0x78.
options.cfg is a Lua-like text file — ANSI-encoded (latin-1), NOT UTF-8.

Real options.cfg field names (from the actual game):
  Settings.Control.ControllerGuid = "00000000000000000000000000000000"
  Settings.Control.Controller = 0
  Settings.Network.Port = 23756
  Settings.Network.BroadcastPort = 23757
  Settings.Network.GameSpyQueryPort = 23758
"""

from __future__ import annotations

import logging
import re
import shutil
import struct
from pathlib import Path

from ..constants import DEVICE_CFG_RESOLUTION_OFFSET

logger = logging.getLogger(__name__)

SAVEGAME_DIR = "Savegame"
DEVICE_CFG = "device.cfg"
OPTIONS_CFG = "options.cfg"
BACKUP_SUFFIX = ".bak.fo2ss"

# FlatOut 2 (2006) uses ANSI encoding for its config files.
# latin-1 preserves all bytes 1:1 on read/write.
OPTIONS_ENCODING = "latin-1"


def _savegame_path(game_dir: Path, savegame_dir: Path | None = None) -> Path:
    return savegame_dir if savegame_dir else game_dir / SAVEGAME_DIR


def backup_config(game_dir: Path) -> None:
    """Create backups of device.cfg and options.cfg if not already backed up."""
    sg = _savegame_path(game_dir)
    for name in (DEVICE_CFG, OPTIONS_CFG):
        src = sg / name
        dst = sg / (name + BACKUP_SUFFIX)
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            logger.info("Backed up %s -> %s", src, dst)


def restore_config(game_dir: Path) -> None:
    """Restore original config files from backups."""
    sg = _savegame_path(game_dir)
    for name in (DEVICE_CFG, OPTIONS_CFG):
        bak = sg / (name + BACKUP_SUFFIX)
        dst = sg / name
        if bak.exists():
            shutil.copy2(bak, dst)
            bak.unlink()
            logger.info("Restored %s from backup", dst)


def patch_resolution(game_dir: Path, width: int, height: int, *, savegame_dir: Path | None = None) -> None:
    """Write resolution into device.cfg at the known binary offset."""
    device_path = _savegame_path(game_dir, savegame_dir) / DEVICE_CFG
    if not device_path.exists():
        logger.warning("device.cfg not found at %s — skipping resolution patch", device_path)
        return
    data = bytearray(device_path.read_bytes())
    off = DEVICE_CFG_RESOLUTION_OFFSET
    if len(data) < off + 8:
        logger.warning("device.cfg too small (%d bytes) — skipping resolution patch", len(data))
        return
    struct.pack_into("<II", data, off, width, height)
    device_path.write_bytes(data)
    logger.info("Patched resolution to %dx%d in %s", width, height, device_path)


def _read_options(path: Path) -> str:
    """Read options.cfg preserving its original encoding."""
    return path.read_text(encoding=OPTIONS_ENCODING)


def _write_options(path: Path, text: str) -> None:
    """Write options.cfg in its original encoding."""
    path.write_text(text, encoding=OPTIONS_ENCODING)


def _replace_option(text: str, key: str, value: str) -> tuple[str, bool]:
    """Replace an existing option value. Returns (new_text, matched).

    Preserves the trailing comment (e.g. --[0 .. 65536]).
    Never appends unknown keys — only modifies existing ones.
    """
    pattern = rf"({re.escape(key)}\s*=\s*)\S+"
    new_text, count = re.subn(pattern, rf"\g<1>{value}", text)
    return new_text, count > 0


def reset_controller_guid(game_dir: Path, *, savegame_dir: Path | None = None) -> None:
    """Zero out the controller GUID in options.cfg so the game uses keyboard."""
    options_path = _savegame_path(game_dir, savegame_dir) / OPTIONS_CFG
    if not options_path.exists():
        logger.warning("options.cfg not found at %s", options_path)
        return
    text = _read_options(options_path)

    # ControllerGuid value is a quoted hex string without dashes
    text = re.sub(
        r'(Settings\.Control\.ControllerGuid\s*=\s*)"[^"]*"',
        r'\1"00000000000000000000000000000000"',
        text,
    )
    text, _ = _replace_option(text, "Settings.Control.Controller", "0")

    _write_options(options_path, text)
    logger.info("Reset controller GUID in %s", options_path)


def set_network_ports(game_dir: Path, instance_id: int, port_stride: int = 4, *, savegame_dir: Path | None = None) -> None:
    """Set per-instance network ports in options.cfg.

    FlatOut 2 uses three ports:
      Settings.Network.Port          (default 23756)
      Settings.Network.BroadcastPort (default 23757)
      Settings.Network.GameSpyQueryPort (default 23758)

    Each instance gets ports offset by instance_id * port_stride.
    Only modifies existing keys — never appends new ones.
    """
    options_path = _savegame_path(game_dir, savegame_dir) / OPTIONS_CFG
    if not options_path.exists():
        logger.warning("options.cfg not found at %s", options_path)
        return
    text = _read_options(options_path)

    base_offset = instance_id * port_stride
    ports = {
        "Settings.Network.Port": 23756 + base_offset,
        "Settings.Network.BroadcastPort": 23757 + base_offset,
        "Settings.Network.GameSpyQueryPort": 23758 + base_offset,
    }

    for key, value in ports.items():
        text, matched = _replace_option(text, key, str(value))
        if matched:
            logger.info("Set %s = %d", key, value)
        else:
            logger.warning("Key '%s' not found in options.cfg — skipping", key)

    _write_options(options_path, text)


def create_instance_savegame(game_dir: Path, instance_id: int) -> Path:
    """Create a per-instance copy of the Savegame directory.

    Returns the path to the instance-specific savegame directory.
    """
    src = _savegame_path(game_dir)
    dst = game_dir / f"Savegame_instance_{instance_id}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    logger.info("Created instance savegame: %s", dst)
    return dst
