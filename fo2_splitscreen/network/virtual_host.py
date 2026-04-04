"""Host-side virtual network logic: broadcasts packets to all clients."""

from __future__ import annotations

import logging

from .protocol import VirtIPHeader

logger = logging.getLogger(__name__)


class VirtualHost:
    """Manages packet routing for the host instance (instance 0).

    The host receives packets from all clients and broadcasts them to
    all other clients. This mirrors the VirtualHost from the reference
    C++ implementation.
    """

    def __init__(self, instance_count: int) -> None:
        self.instance_count = instance_count
        # Map instance_id -> (addr, port) for sending back
        self.client_endpoints: dict[int, tuple[str, int]] = {}

    def register_client(self, instance_id: int, addr: str, port: int) -> None:
        self.client_endpoints[instance_id] = (addr, port)
        logger.info("Registered client %d at %s:%d", instance_id, addr, port)

    def get_broadcast_targets(self, source_instance: int) -> list[tuple[str, int]]:
        """Get all endpoints to broadcast to, excluding the source."""
        return [
            endpoint
            for iid, endpoint in self.client_endpoints.items()
            if iid != source_instance
        ]

    def get_target(self, instance_id: int) -> tuple[str, int] | None:
        return self.client_endpoints.get(instance_id)
