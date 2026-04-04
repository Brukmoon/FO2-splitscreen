"""Tests for session configuration."""

import tempfile
from pathlib import Path

from fo2_splitscreen.config import SessionConfig, WindowRect


def test_default_layout_2_players():
    config = SessionConfig(instance_count=2, resolution=(640, 480))
    config.compute_default_layout(1920, 1080)
    assert len(config.window_positions) == 2
    assert config.window_positions[0] == WindowRect(0, 0, 960, 1080)
    assert config.window_positions[1] == WindowRect(960, 0, 960, 1080)


def test_default_layout_4_players():
    config = SessionConfig(instance_count=4, resolution=(640, 480))
    config.compute_default_layout(1920, 1080)
    assert len(config.window_positions) == 4
    # 2x2 grid
    assert config.window_positions[0] == WindowRect(0, 0, 960, 540)
    assert config.window_positions[1] == WindowRect(960, 0, 960, 540)
    assert config.window_positions[2] == WindowRect(0, 540, 960, 540)
    assert config.window_positions[3] == WindowRect(960, 540, 960, 540)


def test_yaml_roundtrip():
    config = SessionConfig(
        game_dir="/tmp/game",
        instance_count=2,
        resolution=(800, 600),
    )
    config.compute_default_layout(1600, 900)

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    config.to_yaml(path)
    loaded = SessionConfig.from_yaml(path)

    assert loaded.game_dir == config.game_dir
    assert loaded.instance_count == config.instance_count
    assert loaded.resolution == config.resolution
    assert len(loaded.window_positions) == 2
    path.unlink()


def test_network_ports():
    config = SessionConfig(instance_count=3)
    assert config.network.query_port_for(0) == 23756
    assert config.network.query_port_for(1) == 23760
    assert config.network.query_port_for(2) == 23764
    assert config.network.game_port_for(0) == 23757
    assert config.network.game_port_for(1) == 23761
