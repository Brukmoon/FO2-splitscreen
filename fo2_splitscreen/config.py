"""Session configuration for FlatOut 2 splitscreen."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

import yaml

from .constants import (
    DEFAULT_GAME_PORT,
    DEFAULT_QUERY_PORT,
    MAX_INSTANCES,
    MIN_RESOLUTION,
    PORT_STRIDE,
)

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    host_port: int = DEFAULT_QUERY_PORT
    game_port: int = DEFAULT_GAME_PORT
    port_stride: int = PORT_STRIDE

    def query_port_for(self, instance_id: int) -> int:
        return self.host_port + instance_id * self.port_stride

    def game_port_for(self, instance_id: int) -> int:
        return self.game_port + instance_id * self.port_stride


@dataclass
class WindowRect:
    x: int
    y: int
    width: int
    height: int


@dataclass
class SessionConfig:
    game_dir: str = ""
    instance_count: int = 2
    resolution: tuple[int, int] = (640, 480)
    patch_resolution: bool = False  # Patch device.cfg binary — risky, off by default
    skip_intros: bool = True
    controller_assignments: list[str | None] = field(default_factory=list)
    window_positions: list[WindowRect] = field(default_factory=list)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if not 1 <= self.instance_count <= MAX_INSTANCES:
            raise ValueError(f"instance_count must be 1-{MAX_INSTANCES}")
        w, h = self.resolution
        if w < MIN_RESOLUTION[0] or h < MIN_RESOLUTION[1]:
            raise ValueError(f"Resolution must be at least {MIN_RESOLUTION}")
        # Validate that computed ports won't exceed valid range
        max_port = self.network.game_port_for(self.instance_count - 1)
        if max_port > 65535:
            raise ValueError(
                f"Port overflow: instance {self.instance_count - 1} would use port {max_port}"
            )

    def compute_default_layout(self, screen_width: int, screen_height: int) -> None:
        """Compute side-by-side window positions for all instances."""
        n = self.instance_count
        win_w = screen_width // n
        win_h = screen_height
        # For >2 players, use a grid
        if n > 2:
            cols = 2
            rows = (n + 1) // 2
            win_w = screen_width // cols
            win_h = screen_height // rows
        self.window_positions = []
        for i in range(n):
            if n <= 2:
                x = i * win_w
                y = 0
            else:
                col = i % 2
                row = i // 2
                x = col * win_w
                y = row * win_h
            self.window_positions.append(WindowRect(x, y, win_w, win_h))
        self.resolution = (win_w, win_h)

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        data = yaml.safe_load(path.read_text())
        net = NetworkConfig(**data.pop("network", {}))
        positions = [WindowRect(**p) for p in data.pop("window_positions", [])]
        controllers = data.pop("controller_assignments", [])
        resolution = tuple(data.pop("resolution", [640, 480]))
        return cls(
            network=net,
            window_positions=positions,
            controller_assignments=controllers,
            resolution=resolution,
            **data,
        )

    def to_yaml(self, path: Path) -> None:
        data = {
            "game_dir": self.game_dir,
            "instance_count": self.instance_count,
            "resolution": list(self.resolution),
            "patch_resolution": self.patch_resolution,
            "skip_intros": self.skip_intros,
            "log_level": self.log_level,
            "controller_assignments": self.controller_assignments,
            "window_positions": [
                {"x": p.x, "y": p.y, "width": p.width, "height": p.height}
                for p in self.window_positions
            ],
            "network": {
                "host_port": self.network.host_port,
                "game_port": self.network.game_port,
                "port_stride": self.network.port_stride,
            },
        }
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        logger.info("Config saved to %s", path)
