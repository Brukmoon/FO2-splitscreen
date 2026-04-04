"""Manages the lifecycle of multiple FlatOut 2 instances."""

from __future__ import annotations

import atexit
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from ..config import SessionConfig
from .game_config import (
    backup_config,
    create_instance_savegame,
    patch_resolution,
    reset_controller_guid,
    restore_config,
    set_lan_port,
)
from .process import launch_game

logger = logging.getLogger(__name__)

# How long to wait after launch for the game to read its config files.
# The game window appears almost instantly, but config loading happens after.
LAUNCH_SETTLE_SECONDS = 5


class InstanceManager:
    """Orchestrates launching and managing multiple FlatOut 2 instances."""

    def __init__(self, config: SessionConfig) -> None:
        self.config = config
        self.game_dir = Path(config.game_dir)
        self.processes: list[subprocess.Popen] = []
        self.instance_dirs: list[Path] = []
        self._savegame_dir: Path = self.game_dir / "Savegame"
        atexit.register(self.shutdown)

    def prepare(self) -> None:
        """Prepare the game directory: backup configs, create per-instance copies."""
        if not self.game_dir.exists():
            raise FileNotFoundError(f"Game directory not found: {self.game_dir}")
        if not (self.game_dir / "FlatOut2.exe").exists():
            raise FileNotFoundError(f"FlatOut2.exe not found in {self.game_dir}")
        if not self._savegame_dir.exists():
            raise FileNotFoundError(
                f"Savegame directory not found: {self._savegame_dir}"
            )

        backup_config(self.game_dir)

        # Create per-instance savegame directories with customized configs.
        # These are staging areas — their contents get copied into the real
        # Savegame/ dir right before each instance launches.
        self.instance_dirs = []
        for i in range(self.config.instance_count):
            inst_dir = create_instance_savegame(self.game_dir, i)
            if self.config.patch_resolution:
                w, h = self.config.resolution
                patch_resolution(self.game_dir, w, h, savegame_dir=inst_dir)
            reset_controller_guid(self.game_dir, savegame_dir=inst_dir)
            port = self.config.network.query_port_for(i)
            set_lan_port(self.game_dir, port, savegame_dir=inst_dir)
            self.instance_dirs.append(inst_dir)

        logger.info("Prepared %d instances", self.config.instance_count)

    def _apply_instance_config(self, instance_id: int) -> None:
        """Copy instance-specific config files into the real Savegame directory.

        The game reads from Savegame/ at startup. We overwrite device.cfg and
        options.cfg with the instance-specific versions right before launching.
        """
        inst_dir = self.instance_dirs[instance_id]
        for filename in ("device.cfg", "options.cfg"):
            src = inst_dir / filename
            dst = self._savegame_dir / filename
            if src.exists():
                shutil.copy2(src, dst)
        logger.info(
            "Applied instance %d config to %s", instance_id, self._savegame_dir
        )

    def launch_all(self) -> list[int]:
        """Launch all game instances sequentially.

        For each instance we:
        1. Copy its config into the real Savegame/ directory
        2. Launch the game
        3. Wait for the game to settle (read its config files)
        4. Repeat for the next instance

        Returns list of PIDs.
        """
        pids: list[int] = []
        for i in range(self.config.instance_count):
            self._apply_instance_config(i)

            proc = launch_game(self.game_dir)
            self.processes.append(proc)
            logger.info("Instance %d launched with PID %d", i, proc.pid)

            # Wait for the game to read config files before we overwrite
            # them for the next instance.
            if i < self.config.instance_count - 1:
                self._wait_for_config_load(proc.pid, i)

            pids.append(proc.pid)

        return pids

    def _wait_for_config_load(self, pid: int, instance_id: int) -> None:
        """Wait until the game has read its config files.

        First waits for the window to appear, then adds extra settle time
        because the game reads config AFTER creating the window.
        """
        if os.name == "nt":
            from ..window.manager import wait_for_window

            try:
                wait_for_window(pid, timeout=30)
            except TimeoutError:
                logger.warning(
                    "Instance %d: timed out waiting for window", instance_id
                )

        # Extra time for the game to finish reading device.cfg / options.cfg
        logger.info(
            "Instance %d: waiting %ds for config to load...",
            instance_id,
            LAUNCH_SETTLE_SECONDS,
        )
        time.sleep(LAUNCH_SETTLE_SECONDS)

    def shutdown(self) -> None:
        """Terminate all running instances and clean up."""
        for proc in self.processes:
            if proc.poll() is None:
                logger.info("Terminating PID %d", proc.pid)
                proc.terminate()
        # Wait for all processes to exit before cleanup
        for proc in self.processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Force-killing PID %d", proc.pid)
                proc.kill()
                proc.wait(timeout=5)
        self.processes.clear()

        # Clean up instance savegame dirs
        for inst_dir in self.instance_dirs:
            if inst_dir.exists():
                shutil.rmtree(inst_dir, ignore_errors=True)
        self.instance_dirs.clear()

        # Restore original configs
        restore_config(self.game_dir)
        logger.info("Shutdown complete")

    def get_pids(self) -> list[int]:
        return [p.pid for p in self.processes if p.poll() is None]
