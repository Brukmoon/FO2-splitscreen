"""Command-line interface for FlatOut 2 splitscreen enabler."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import shutil
import threading
from pathlib import Path

from .config import SessionConfig
from .launcher.instance_manager import InstanceManager
from .launcher.game_config import restore_config


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_launch(args: argparse.Namespace) -> None:
    """Launch splitscreen session."""
    if args.config:
        config = SessionConfig.from_yaml(Path(args.config))
    else:
        if not args.game_dir:
            print("Error: --game-dir is required when not using --config")
            raise SystemExit(1)
        config = SessionConfig(
            game_dir=args.game_dir,
            instance_count=args.players,
            resolution=tuple(int(x) for x in args.resolution.split("x")),
            patch_resolution=not args.no_patch_resolution,
            skip_intros=not args.no_skip_intros,
        )

    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    if os.name != "nt":
        logger.warning(
            "This tool is designed for Windows. "
            "Window management and memory patching will not work on this platform."
        )

    # Compute window layout if not specified
    if not config.window_positions:
        if os.name == "nt":
            from .window.monitor import get_primary_monitor
            monitor = get_primary_monitor()
            screen_w, screen_h = monitor.width, monitor.height
        else:
            screen_w, screen_h = 1920, 1080
        config.compute_default_layout(screen_w, screen_h)
        logger.info(
            "Auto layout: %d instances on %dx%d screen",
            config.instance_count, screen_w, screen_h,
        )

    manager = InstanceManager(config)

    # Handle Ctrl+C gracefully
    shutdown_event = threading.Event()

    def signal_handler(sig, frame):
        logger.info("Interrupt received, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        logger.info("Preparing %d instances...", config.instance_count)
        manager.prepare()

        logger.info("Launching instances...")
        pids = manager.launch_all()

        # Position windows (Windows only)
        if os.name == "nt":
            from .window.manager import make_borderless, position_window, wait_for_window

            for i, pid in enumerate(pids):
                if i >= len(config.window_positions):
                    logger.warning("No window position for instance %d, skipping", i)
                    continue
                try:
                    hwnd = wait_for_window(pid, timeout=30)
                    pos = config.window_positions[i]
                    make_borderless(hwnd)
                    position_window(hwnd, pos.x, pos.y, pos.width, pos.height)
                except TimeoutError:
                    logger.error(
                        "Timed out waiting for window of instance %d (PID %d)", i, pid
                    )
                except OSError as e:
                    logger.error("Window setup failed for instance %d: %s", i, e)

        # Apply memory patches if configured (Windows only)
        if config.skip_intros and os.name == "nt":
            try:
                from .memory.patcher import GamePatcher

                for i, pid in enumerate(pids):
                    try:
                        patcher = GamePatcher(pid)
                        results = patcher.apply_all()
                        for name, success in results.items():
                            if success:
                                logger.info("Instance %d: patch '%s' applied", i, name)
                            else:
                                logger.warning("Instance %d: patch '%s' failed", i, name)
                        patcher.close()
                    except RuntimeError as e:
                        logger.warning("Instance %d: memory patching failed: %s", i, e)
            except ImportError:
                logger.warning("pymem not installed — skipping memory patches")

        logger.info("All instances running. Press Ctrl+C to stop.")
        shutdown_event.wait()

    except FileNotFoundError as e:
        logger.error("%s", e)
        raise SystemExit(1)
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Unexpected error")
    finally:
        manager.shutdown()


def cmd_restore(args: argparse.Namespace) -> None:
    """Restore original game config files after a crash."""
    setup_logging("INFO")
    game_dir = Path(args.game_dir)
    sg = game_dir / "Savegame"

    if not sg.exists():
        print(f"Error: Savegame directory not found at {sg}")
        raise SystemExit(1)

    # Restore config backups
    restored = False
    for name in ("device.cfg", "options.cfg"):
        bak = sg / (name + ".bak.fo2ss")
        dst = sg / name
        if bak.exists():
            shutil.copy2(bak, dst)
            bak.unlink()
            print(f"Restored {name} from backup")
            restored = True

    # Clean up leftover instance dirs
    for p in game_dir.glob("Savegame_instance_*"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            print(f"Removed {p.name}")
            restored = True

    # Clean up leftover from old junction-based code
    old_backup = game_dir / "Savegame_original"
    if old_backup.exists():
        if not sg.exists():
            old_backup.rename(sg)
            print("Restored Savegame from Savegame_original")
        else:
            shutil.rmtree(old_backup, ignore_errors=True)
            print("Removed leftover Savegame_original")
        restored = True

    if restored:
        print("Done. Game files restored.")
    else:
        print("Nothing to restore — no backup files found.")


def cmd_config_create(args: argparse.Namespace) -> None:
    """Interactively create a configuration file."""
    print("FlatOut 2 Splitscreen — Configuration Creator")
    print("=" * 50)

    game_dir = input("Game directory (path to FlatOut2.exe): ").strip()
    players = int(input("Number of players [2]: ").strip() or "2")
    resolution = input("Resolution per player [640x480]: ").strip() or "640x480"
    w, h = (int(x) for x in resolution.split("x"))

    config = SessionConfig(
        game_dir=game_dir,
        instance_count=players,
        resolution=(w, h),
    )

    out = Path(args.output)
    config.to_yaml(out)
    print(f"Config saved to {out}")


def cmd_controllers(args: argparse.Namespace) -> None:
    """List connected controllers."""
    try:
        import pygame

        pygame.init()
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count == 0:
            print("No controllers found.")
        else:
            print(f"Found {count} controller(s):")
            for i in range(count):
                js = pygame.joystick.Joystick(i)
                js.init()
                print(f"  [{i}] {js.get_name()} (GUID: {js.get_guid()})")
        pygame.quit()
    except ImportError:
        print("pygame not installed. Install it with: pip install pygame")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fo2-splitscreen",
        description="FlatOut 2 Splitscreen Enabler",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # launch
    p_launch = sub.add_parser("launch", help="Launch splitscreen session")
    p_launch.add_argument("--game-dir", "-g", help="Path to FlatOut 2 installation")
    p_launch.add_argument("--players", "-p", type=int, default=2, help="Number of players (1-8)")
    p_launch.add_argument("--resolution", "-r", default="640x480", help="Resolution per player (WxH)")
    p_launch.add_argument("--config", "-c", help="Path to config.yaml")
    p_launch.add_argument("--no-patch-resolution", action="store_true", help="Don't patch device.cfg resolution")
    p_launch.add_argument("--no-skip-intros", action="store_true", help="Don't skip intro videos")
    p_launch.set_defaults(func=cmd_launch)

    # restore
    p_restore = sub.add_parser("restore", help="Restore game files after a crash")
    p_restore.add_argument("--game-dir", "-g", required=True, help="Path to FlatOut 2 installation")
    p_restore.set_defaults(func=cmd_restore)

    # config
    p_config = sub.add_parser("config", help="Create configuration file")
    p_config.add_argument("--output", "-o", default="config.yaml", help="Output file path")
    p_config.set_defaults(func=cmd_config_create)

    # controllers
    p_ctrl = sub.add_parser("controllers", help="List connected controllers")
    p_ctrl.set_defaults(func=cmd_controllers)

    args = parser.parse_args()
    args.func(args)
