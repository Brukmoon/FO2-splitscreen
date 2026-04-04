"""Process launch helpers for FlatOut 2 instances."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..constants import GAME_EXE

logger = logging.getLogger(__name__)


def launch_game(
    game_dir: Path,
    *,
    savegame_dir: Path | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.Popen:
    """Launch a FlatOut 2 instance.

    Args:
        game_dir: Path to the FlatOut 2 installation directory.
        savegame_dir: If provided, override the savegame path (for per-instance isolation).
        extra_args: Additional command-line arguments to pass to the game.

    Returns:
        The Popen handle for the launched process.
    """
    exe = game_dir / GAME_EXE
    if not exe.exists():
        raise FileNotFoundError(f"Game executable not found: {exe}")

    cmd: list[str] = [str(exe)]
    if extra_args:
        cmd.extend(extra_args)

    logger.info("Launching: %s (cwd=%s)", " ".join(cmd), game_dir)

    # If using a custom savegame dir, we need to set up a junction/symlink
    # or modify the game's working directory. FlatOut 2 looks for Savegame/
    # relative to the exe, so we handle this in instance_manager via symlinks.
    proc = subprocess.Popen(
        cmd,
        cwd=str(game_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("Launched PID %d", proc.pid)
    return proc
