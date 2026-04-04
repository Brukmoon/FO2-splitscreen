"""Constants for FlatOut 2 splitscreen enabler."""

# Game process
GAME_EXE = "FlatOut2.exe"
GAME_WINDOW_CLASS = "BDX9 Render Window"
GAME_WINDOW_TITLE = "FlatOut2"

# Memory addresses (FlatOut 2 retail v1.2)
# These are absolute virtual addresses — verify bytes before patching.
ADDR_PLAY_INTRO = 0x00520BB0
ADDR_PLAY_MOVIE = 0x004C8F00
ADDR_WINMAIN = 0x00520ED0

# x86 RET instruction — used to skip intro/movie functions
X86_RET = b"\xC3"

# device.cfg binary offsets
DEVICE_CFG_RESOLUTION_OFFSET = 0x78  # Two consecutive uint32: width, height

# Network defaults (FO2 LAN ports)
DEFAULT_GAME_PORT = 23757
DEFAULT_QUERY_PORT = 23756
PORT_STRIDE = 4  # Port increment per instance

# Virtual network
VIRTUAL_IP_BASE = "192.168.80.0"
VIRTUAL_IP_OFFSET = 1  # First instance gets .1

# Limits
MAX_INSTANCES = 8
MIN_RESOLUTION = (640, 480)

# Win32 window style flags
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
GWL_STYLE = -16

SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
HWND_TOP = 0
