"""Client-side virtual network logic."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class VirtualClient:
    """Represents a client instance in the virtual network.

    Each client sends all its traffic to the host for routing/broadcast.
    """

    def __init__(self, instance_id: int, host_addr: str, host_port: int) -> None:
        self.instance_id = instance_id
        self.host_addr = host_addr
        self.host_port = host_port

    def get_host_endpoint(self) -> tuple[str, int]:
        return (self.host_addr, self.host_port)
