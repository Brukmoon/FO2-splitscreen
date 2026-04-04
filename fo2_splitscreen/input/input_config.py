"""Button mapping definitions for controller-to-keyboard emulation."""

from __future__ import annotations

from dataclasses import dataclass

# Virtual key codes (Windows)
VK_UP = 0x26
VK_DOWN = 0x28
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_TAB = 0x09
VK_SPACE = 0x20
VK_SHIFT = 0x10
VK_CONTROL = 0x11


@dataclass
class AxisMapping:
    """Maps a controller axis to two keyboard keys (negative/positive direction)."""

    axis_index: int
    negative_key: int  # VK code when axis < -threshold
    positive_key: int  # VK code when axis > +threshold
    threshold: float = 0.5


@dataclass
class ButtonMapping:
    """Maps a controller button to a keyboard key."""

    button_index: int
    key: int  # VK code


@dataclass
class ControllerProfile:
    """Complete mapping from one controller to keyboard keys."""

    name: str
    buttons: list[ButtonMapping]
    axes: list[AxisMapping]


# Default profile: XInput-style controller for FlatOut 2
DEFAULT_PROFILE = ControllerProfile(
    name="default",
    buttons=[
        ButtonMapping(0, VK_RETURN),   # A -> Enter (select/nitro)
        ButtonMapping(1, VK_ESCAPE),   # B -> Escape (back)
        ButtonMapping(2, VK_SHIFT),    # X -> Shift (handbrake)
        ButtonMapping(3, VK_SPACE),    # Y -> Space
        ButtonMapping(4, VK_TAB),      # LB -> Tab
        ButtonMapping(5, VK_CONTROL),  # RB -> Ctrl
        ButtonMapping(6, VK_ESCAPE),   # Back -> Escape
        ButtonMapping(7, VK_RETURN),   # Start -> Enter
    ],
    axes=[
        AxisMapping(0, VK_LEFT, VK_RIGHT, 0.3),  # Left stick X -> steering
        AxisMapping(1, VK_UP, VK_DOWN, 0.3),      # Left stick Y -> (unused in-race)
        # Triggers: axis 4 (LT) = brake, axis 5 (RT) = accelerate
        # pygame maps triggers as axes with range 0..1 or -1..1 depending on driver
        AxisMapping(4, VK_DOWN, VK_DOWN, 0.3),    # LT -> brake (Down arrow)
        AxisMapping(5, VK_UP, VK_UP, 0.3),        # RT -> accelerate (Up arrow)
    ],
)
