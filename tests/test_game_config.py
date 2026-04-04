"""Tests for game config file manipulation."""

import struct
import tempfile
from pathlib import Path

from fo2_splitscreen.launcher.game_config import (
    backup_config,
    patch_resolution,
    reset_controller_guid,
    restore_config,
    set_lan_port,
)


def _make_game_dir() -> Path:
    """Create a temporary game directory with mock config files."""
    tmp = Path(tempfile.mkdtemp())
    sg = tmp / "Savegame"
    sg.mkdir()

    # Create a mock device.cfg (needs to be at least 0x78 + 8 bytes)
    device_data = bytearray(256)
    # Write some default resolution at offset 0x78
    struct.pack_into("<II", device_data, 0x78, 800, 600)
    (sg / "device.cfg").write_bytes(device_data)

    # Create a mock options.cfg (latin-1 encoded, like the real game)
    options_text = (
        'Settings.Control.Controller = 1\n'
        'Settings.Control.ControllerGUID = "12345678-abcd-1234-abcd-123456789012"\n'
        'Settings.Online.LANPort = 23756\n'
    )
    (sg / "options.cfg").write_text(options_text, encoding="latin-1")

    return tmp


def test_backup_and_restore():
    game_dir = _make_game_dir()
    sg = game_dir / "Savegame"

    backup_config(game_dir)
    assert (sg / "device.cfg.bak.fo2ss").exists()
    assert (sg / "options.cfg.bak.fo2ss").exists()

    # Modify the original
    (sg / "device.cfg").write_bytes(b"\x00" * 10)

    restore_config(game_dir)
    # Original should be restored (256 bytes)
    assert len((sg / "device.cfg").read_bytes()) == 256
    # Backup should be cleaned up
    assert not (sg / "device.cfg.bak.fo2ss").exists()


def test_patch_resolution():
    game_dir = _make_game_dir()
    patch_resolution(game_dir, 1024, 768)

    data = (game_dir / "Savegame" / "device.cfg").read_bytes()
    w, h = struct.unpack_from("<II", data, 0x78)
    assert w == 1024
    assert h == 768


def test_patch_resolution_with_savegame_dir():
    game_dir = _make_game_dir()
    # Create an alternate savegame dir
    alt_sg = game_dir / "Savegame_instance_0"
    alt_sg.mkdir()
    device_data = bytearray(256)
    struct.pack_into("<II", device_data, 0x78, 800, 600)
    (alt_sg / "device.cfg").write_bytes(device_data)

    patch_resolution(game_dir, 640, 480, savegame_dir=alt_sg)

    # Main savegame should be untouched
    main_data = (game_dir / "Savegame" / "device.cfg").read_bytes()
    main_w, main_h = struct.unpack_from("<II", main_data, 0x78)
    assert main_w == 800
    assert main_h == 600

    # Alt savegame should be patched
    alt_data = (alt_sg / "device.cfg").read_bytes()
    alt_w, alt_h = struct.unpack_from("<II", alt_data, 0x78)
    assert alt_w == 640
    assert alt_h == 480


def test_reset_controller_guid():
    game_dir = _make_game_dir()
    reset_controller_guid(game_dir)

    text = (game_dir / "Savegame" / "options.cfg").read_text()
    assert "00000000-0000-0000-0000-000000000000" in text
    assert "Settings.Control.Controller = 0" in text


def test_set_lan_port():
    game_dir = _make_game_dir()
    set_lan_port(game_dir, 23760)

    text = (game_dir / "Savegame" / "options.cfg").read_text()
    assert "Settings.Online.LANPort = 23760" in text


def test_set_lan_port_when_missing():
    """When LANPort doesn't exist in options.cfg, it should be appended."""
    game_dir = _make_game_dir()
    sg = game_dir / "Savegame"
    # Write options without LANPort
    (sg / "options.cfg").write_text("Settings.Control.Controller = 0\n", encoding="latin-1")

    set_lan_port(game_dir, 23760)

    text = (sg / "options.cfg").read_text()
    assert "Settings.Online.LANPort = 23760" in text
