"""External memory patching for FlatOut 2 using pymem.

Attaches to a running game process and writes patches (e.g., intro skip)
after verifying expected bytes at the target addresses.

Windows-only module. Requires pymem.
"""

from __future__ import annotations

import logging
import os

from .addresses import KNOWN_VERSIONS, GameVersion, PatchTarget

logger = logging.getLogger(__name__)


def _require_pymem():
    """Lazily import pymem, raising a clear error if unavailable."""
    try:
        import pymem as _pymem
        return _pymem
    except ImportError:
        raise RuntimeError(
            "pymem is required for memory patching. "
            "Install it with: pip install pymem (Windows only)"
        )


class GamePatcher:
    """Attaches to a FlatOut 2 process and applies memory patches."""

    def __init__(self, pid: int) -> None:
        if os.name != "nt":
            raise RuntimeError("Memory patching requires Windows")
        pymem = _require_pymem()
        self.pid = pid
        self.pm = pymem.Pymem()
        try:
            self.pm.open_process_from_id(pid)
        except Exception as e:
            raise RuntimeError(
                f"Failed to attach to PID {pid}. "
                f"Ensure the game is running and you have permission: {e}"
            ) from e
        self._detected_version: GameVersion | None = None
        logger.info("Attached to PID %d", pid)

    def detect_version(self) -> GameVersion | None:
        """Try to detect the game version by checking known byte patterns."""
        for version in KNOWN_VERSIONS:
            match = True
            for patch in version.patches.values():
                try:
                    actual = self.pm.read_bytes(patch.address, len(patch.expected_bytes))
                    if actual != patch.expected_bytes:
                        match = False
                        break
                except Exception:
                    match = False
                    break
            if match:
                self._detected_version = version
                logger.info("Detected: %s", version.name)
                return version

        logger.warning("Could not detect game version — patches may not work")
        return None

    def apply_patch(self, patch_name: str) -> bool:
        """Apply a named patch from the detected version.

        Returns True if the patch was applied successfully.
        """
        if not self._detected_version:
            if not self.detect_version():
                logger.error("No version detected, cannot apply patch '%s'", patch_name)
                return False

        patch = self._detected_version.patches.get(patch_name)
        if not patch:
            logger.error("Unknown patch: '%s'", patch_name)
            return False

        return self._apply(patch)

    def _apply(self, patch: PatchTarget) -> bool:
        """Write patch bytes to the target address after verification."""
        try:
            actual = self.pm.read_bytes(patch.address, len(patch.expected_bytes))
        except Exception as e:
            logger.error("Failed to read 0x%X: %s", patch.address, e)
            return False

        if actual != patch.expected_bytes:
            if actual[: len(patch.patch_bytes)] == patch.patch_bytes:
                logger.info("Patch '%s' already applied at 0x%X", patch.description, patch.address)
                return True
            logger.warning(
                "Unexpected bytes at 0x%X: expected %s, got %s — skipping %s",
                patch.address,
                patch.expected_bytes.hex(),
                actual.hex(),
                patch.description,
            )
            return False

        try:
            self.pm.write_bytes(patch.address, patch.patch_bytes, len(patch.patch_bytes))
            logger.info("Applied: %s at 0x%X", patch.description, patch.address)
            return True
        except Exception as e:
            logger.error("Failed to write patch at 0x%X: %s", patch.address, e)
            return False

    def apply_all(self) -> dict[str, bool]:
        """Apply all patches for the detected version. Returns {name: success}."""
        if not self._detected_version:
            self.detect_version()
        if not self._detected_version:
            return {}

        results = {}
        for name in self._detected_version.patches:
            results[name] = self.apply_patch(name)
        return results

    def close(self) -> None:
        try:
            self.pm.close_process()
        except Exception:
            pass
