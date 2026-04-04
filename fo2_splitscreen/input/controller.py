"""Controller enumeration and state reading via pygame."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ControllerInfo:
    index: int
    name: str
    guid: str
    num_buttons: int
    num_axes: int


def enumerate_controllers() -> list[ControllerInfo]:
    """List all connected game controllers."""
    import pygame

    if not pygame.get_init():
        pygame.init()
    pygame.joystick.init()

    controllers = []
    for i in range(pygame.joystick.get_count()):
        js = pygame.joystick.Joystick(i)
        js.init()
        controllers.append(ControllerInfo(
            index=i,
            name=js.get_name(),
            guid=js.get_guid(),
            num_buttons=js.get_numbuttons(),
            num_axes=js.get_numaxes(),
        ))
    return controllers


class ControllerReader:
    """Reads state from a specific controller by index."""

    def __init__(self, controller_index: int) -> None:
        import pygame

        if not pygame.get_init():
            pygame.init()
        pygame.joystick.init()
        self.joystick = pygame.joystick.Joystick(controller_index)
        self.joystick.init()
        self.num_buttons = self.joystick.get_numbuttons()
        self.num_axes = self.joystick.get_numaxes()
        logger.info(
            "Opened controller %d: %s (%d buttons, %d axes)",
            controller_index, self.joystick.get_name(), self.num_buttons, self.num_axes,
        )

    def read_buttons(self) -> list[bool]:
        """Read current button states. Call pygame.event.pump() before this."""
        return [self.joystick.get_button(i) for i in range(self.num_buttons)]

    def read_axes(self) -> list[float]:
        """Read current axis values (-1.0 to 1.0). Call pygame.event.pump() before this."""
        return [self.joystick.get_axis(i) for i in range(self.num_axes)]
