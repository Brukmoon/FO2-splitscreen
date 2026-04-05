"""Tests for game config file manipulation."""

import struct
import tempfile
from pathlib import Path

from fo2_splitscreen.launcher.game_config import (
    backup_config,
    patch_resolution,
    reset_controller_guid,
    restore_config,
    set_network_ports,
)

# Matches the real FlatOut 2 options.cfg format
SAMPLE_OPTIONS = """\
Settings.Version.Settings = 12 \t\t\t--[0 .. 1000000]
Settings.Control.ControllerGuid = "AABBCCDD11223344AABBCCDD11223344"
Settings.Control.Controller = 1 \t\t\t--[0 .. 2]
Settings.Network.Port = 23756 \t\t\t--[0 .. 65536]
Settings.Network.BroadcastPort = 23757 \t\t\t--[0 .. 65536]
Settings.Network.GameSpyQueryPort = 23758 \t\t\t--[0 .. 65536]
"""


def _make_game_dir() -> Path:
    """Create a temporary game directory with mock config files."""
    tmp = Path(tempfile.mkdtemp())
    sg = tmp / "Savegame"
    sg.mkdir()

    device_data = bytearray(256)
    struct.pack_into("<II", device_data, 0x78, 800, 600)
    (sg / "device.cfg").write_bytes(device_data)

    (sg / "options.cfg").write_text(SAMPLE_OPTIONS, encoding="latin-1")

    return tmp


def test_backup_and_restore():
    game_dir = _make_game_dir()
    sg = game_dir / "Savegame"

    backup_config(game_dir)
    assert (sg / "device.cfg.bak.fo2ss").exists()
    assert (sg / "options.cfg.bak.fo2ss").exists()

    (sg / "device.cfg").write_bytes(b"\x00" * 10)

    restore_config(game_dir)
    assert len((sg / "device.cfg").read_bytes()) == 256
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
    alt_sg = game_dir / "Savegame_instance_0"
    alt_sg.mkdir()
    device_data = bytearray(256)
    struct.pack_into("<II", device_data, 0x78, 800, 600)
    (alt_sg / "device.cfg").write_bytes(device_data)

    patch_resolution(game_dir, 640, 480, savegame_dir=alt_sg)

    main_data = (game_dir / "Savegame" / "device.cfg").read_bytes()
    main_w, main_h = struct.unpack_from("<II", main_data, 0x78)
    assert main_w == 800
    assert main_h == 600

    alt_data = (alt_sg / "device.cfg").read_bytes()
    alt_w, alt_h = struct.unpack_from("<II", alt_data, 0x78)
    assert alt_w == 640
    assert alt_h == 480


def test_reset_controller_guid():
    game_dir = _make_game_dir()
    reset_controller_guid(game_dir)

    text = (game_dir / "Savegame" / "options.cfg").read_text(encoding="latin-1")
    assert '"00000000000000000000000000000000"' in text
    assert "Settings.Control.Controller = 0" in text


def test_set_network_ports_instance_0():
    game_dir = _make_game_dir()
    set_network_ports(game_dir, instance_id=0)

    text = (game_dir / "Savegame" / "options.cfg").read_text(encoding="latin-1")
    assert "Settings.Network.Port = 23756" in text
    assert "Settings.Network.BroadcastPort = 23757" in text
    assert "Settings.Network.GameSpyQueryPort = 23758" in text


def test_set_network_ports_instance_1():
    game_dir = _make_game_dir()
    set_network_ports(game_dir, instance_id=1, port_stride=4)

    text = (game_dir / "Savegame" / "options.cfg").read_text(encoding="latin-1")
    assert "Settings.Network.Port = 23760" in text
    assert "Settings.Network.BroadcastPort = 23761" in text
    assert "Settings.Network.GameSpyQueryPort = 23762" in text


def test_set_network_ports_preserves_comments():
    """Port replacement must not destroy the trailing --[0 .. 65536] comment."""
    game_dir = _make_game_dir()
    set_network_ports(game_dir, instance_id=1, port_stride=4)

    text = (game_dir / "Savegame" / "options.cfg").read_text(encoding="latin-1")
    # The comment should still be on the same line
    assert "--[0 .. 65536]" in text


def test_no_unknown_keys_appended():
    """We must never add lines the game doesn't expect."""
    game_dir = _make_game_dir()
    set_network_ports(game_dir, instance_id=2)
    reset_controller_guid(game_dir)

    text = (game_dir / "Savegame" / "options.cfg").read_text(encoding="latin-1")
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    # Same number of lines as input — nothing appended
    original_lines = [l.strip() for l in SAMPLE_OPTIONS.strip().splitlines() if l.strip()]
    assert len(lines) == len(original_lines)
