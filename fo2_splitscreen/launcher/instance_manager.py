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


class InstanceManager:
    """Orchestrates launching and managing multiple FlatOut 2 instances."""

    def __init__(self, config: SessionConfig) -> None:
        self.config = config
        self.game_dir = Path(config.game_dir)
        self.processes: list[subprocess.Popen] = []
        self.instance_dirs: list[Path] = []
        self._original_savegame: Path = self.game_dir / "Savegame"
        self._savegame_backup: Path = self.game_dir / "Savegame_original"
        self._savegame_swapped = False
        atexit.register(self.shutdown)

    def prepare(self) -> None:
        """Prepare the game directory: backup configs, create per-instance copies."""
        if not self.game_dir.exists():
            raise FileNotFoundError(f"Game directory not found: {self.game_dir}")
        if not (self.game_dir / "FlatOut2.exe").exists():
            raise FileNotFoundError(f"FlatOut2.exe not found in {self.game_dir}")
        if not self._original_savegame.exists():
            raise FileNotFoundError(
                f"Savegame directory not found: {self._original_savegame}"
            )

        backup_config(self.game_dir)

        # Create per-instance savegame directories with customized configs
        self.instance_dirs = []
        for i in range(self.config.instance_count):
            inst_dir = create_instance_savegame(self.game_dir, i)
            w, h = self.config.resolution
            patch_resolution(self.game_dir, w, h, savegame_dir=inst_dir)
            reset_controller_guid(self.game_dir, savegame_dir=inst_dir)
            port = self.config.network.query_port_for(i)
            set_lan_port(self.game_dir, port, savegame_dir=inst_dir)
            self.instance_dirs.append(inst_dir)

        logger.info("Prepared %d instances", self.config.instance_count)

    def launch_all(self, window_wait_timeout: float = 30.0) -> list[int]:
        """Launch all game instances sequentially.

        For each instance, the Savegame directory is temporarily swapped to
        the instance-specific copy. We wait for the game window to appear
        (indicating it has loaded its config) before swapping for the next.

        Returns list of PIDs.
        """
        pids: list[int] = []
        for i in range(self.config.instance_count):
            pid = self._launch_instance(i, window_wait_timeout)
            pids.append(pid)
        return pids

    def _swap_savegame_in(self, instance_savegame: Path) -> None:
        """Replace the real Savegame dir with a junction/symlink to instance copy."""
        real = self._original_savegame
        backup = self._savegame_backup

        # Move real savegame out of the way (first time only)
        if real.exists() and not real.is_symlink() and not self._savegame_swapped:
            if backup.exists():
                shutil.rmtree(backup)
            real.rename(backup)
            self._savegame_swapped = True
        elif real.is_symlink() or (os.name == "nt" and real.exists() and self._savegame_swapped):
            # Remove previous symlink/junction
            self._remove_link(real)

        # Create symlink/junction to instance savegame
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(real), str(instance_savegame)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to create junction {real} -> {instance_savegame}: {result.stderr}"
                )
        else:
            real.symlink_to(instance_savegame)

        logger.debug("Savegame swapped to %s", instance_savegame)

    def _swap_savegame_out(self) -> None:
        """Remove the symlink/junction and restore the original Savegame."""
        real = self._original_savegame
        backup = self._savegame_backup

        if real.is_symlink() or (os.name == "nt" and self._savegame_swapped and real.exists()):
            self._remove_link(real)

        if backup.exists():
            backup.rename(real)
            self._savegame_swapped = False
            logger.debug("Original Savegame restored")

    @staticmethod
    def _remove_link(path: Path) -> None:
        """Remove a symlink or Windows directory junction."""
        if os.name == "nt":
            # rmdir removes junctions without deleting target contents
            subprocess.run(["cmd", "/c", "rmdir", str(path)], capture_output=True)
        else:
            path.unlink(missing_ok=True)

    def _launch_instance(self, instance_id: int, window_wait_timeout: float) -> int:
        """Launch a single instance with its savegame swapped in.

        Waits for the game window to appear before returning, so the next
        instance can safely swap in its own savegame.
        """
        self._swap_savegame_in(self.instance_dirs[instance_id])

        proc = launch_game(self.game_dir)
        self.processes.append(proc)
        logger.info("Instance %d launched with PID %d", instance_id, proc.pid)

        # Wait for the game to create its window, which means it has
        # finished reading config files and we can safely swap savegame.
        if os.name == "nt":
            from ..window.manager import wait_for_window

            try:
                wait_for_window(proc.pid, timeout=window_wait_timeout)
                logger.info("Instance %d window detected, savegame loaded", instance_id)
            except TimeoutError:
                logger.warning(
                    "Instance %d: timed out waiting for window — "
                    "proceeding anyway (config may not have loaded)",
                    instance_id,
                )
        else:
            # Non-Windows: just wait a fixed delay (development/testing)
            time.sleep(3)

        return proc.pid

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

        # Restore original savegame directory
        self._swap_savegame_out()

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
