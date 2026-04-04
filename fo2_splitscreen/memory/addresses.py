"""Known memory addresses for FlatOut 2 versions.

Each version has a set of known addresses with expected bytes at those
locations for verification before patching.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PatchTarget:
    """A memory location to patch, with verification."""

    address: int
    expected_bytes: bytes  # First N bytes we expect at this address (for version check)
    patch_bytes: bytes  # What to write
    description: str


@dataclass
class GameVersion:
    name: str
    patches: dict[str, PatchTarget]


# FlatOut 2 v1.2 (retail/GOG)
FO2_V1_2 = GameVersion(
    name="FlatOut 2 v1.2",
    patches={
        "skip_intro": PatchTarget(
            address=0x00520BB0,
            expected_bytes=b"\x55\x8B\xEC",  # push ebp; mov ebp, esp
            patch_bytes=b"\xC3",  # ret
            description="Skip intro videos (PlayIntro)",
        ),
        "skip_movie": PatchTarget(
            address=0x004C8F00,
            expected_bytes=b"\x55\x8B\xEC",  # push ebp; mov ebp, esp
            patch_bytes=b"\xC3",  # ret
            description="Skip movie playback (PlayMovie)",
        ),
    },
)

# Add more versions here as discovered
KNOWN_VERSIONS = [FO2_V1_2]
