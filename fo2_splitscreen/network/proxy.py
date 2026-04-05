"""Simple UDP broadcast relay for FlatOut 2 LAN play.

When instances use different ports (--change-ports), they can't discover
each other. This relay bridges discovery traffic between port sets.

Architecture:
  Instance 0: Port=23756, BroadcastPort=23757
  Instance 1: Port=23760, BroadcastPort=23761

  The relay forwards broadcast/discovery packets between instances
  so they can find each other despite using different ports.

When instances use the SAME ports (default), this relay is NOT needed.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass

from ..config import NetworkConfig

logger = logging.getLogger(__name__)


@dataclass
class InstancePorts:
    instance_id: int
    port: int           # Settings.Network.Port
    broadcast_port: int  # Settings.Network.BroadcastPort
    query_port: int      # Settings.Network.GameSpyQueryPort


class BroadcastRelay:
    """Relays UDP packets between game instances on different port sets.

    For each port type (Port, BroadcastPort, GameSpyQueryPort), the relay
    listens on a separate socket and forwards incoming packets to all other
    instances' corresponding ports.
    """

    def __init__(self, instances: list[InstancePorts]) -> None:
        self.instances = instances
        self._transports: list[asyncio.DatagramTransport] = []
        self._running = False

    async def start(self) -> None:
        """Start relay sockets for all port types."""
        loop = asyncio.get_running_loop()

        for inst in self.instances:
            for port_type, port in [
                ("broadcast", inst.broadcast_port),
                ("query", inst.query_port),
            ]:
                try:
                    # Create a socket that can receive broadcasts
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.bind(("0.0.0.0", port))
                    sock.setblocking(False)

                    transport, _ = await loop.create_datagram_endpoint(
                        lambda i=inst.instance_id, pt=port_type: _RelayProtocol(
                            self, i, pt
                        ),
                        sock=sock,
                    )
                    self._transports.append(transport)
                    logger.info(
                        "Relay listening on port %d for instance %d (%s)",
                        port, inst.instance_id, port_type,
                    )
                except OSError as e:
                    logger.warning(
                        "Cannot bind relay port %d (instance %d, %s): %s — "
                        "game may already be using it",
                        port, inst.instance_id, port_type, e,
                    )

        self._running = True
        logger.info("Broadcast relay started for %d instances", len(self.instances))

    def forward(self, data: bytes, source_instance: int, port_type: str) -> None:
        """Forward a packet from source to all other instances."""
        for inst in self.instances:
            if inst.instance_id == source_instance:
                continue
            target_port = (
                inst.broadcast_port if port_type == "broadcast"
                else inst.query_port
            )
            # Send to localhost since all instances are on the same machine
            for transport in self._transports:
                try:
                    transport.sendto(data, ("127.0.0.1", target_port))
                    logger.debug(
                        "Relayed %d bytes: instance %d -> %d (%s, port %d)",
                        len(data), source_instance, inst.instance_id,
                        port_type, target_port,
                    )
                    break  # Only need one transport to send
                except Exception:
                    continue

    async def stop(self) -> None:
        """Close all relay sockets."""
        for transport in self._transports:
            transport.close()
        self._transports.clear()
        self._running = False
        logger.info("Broadcast relay stopped")


class _RelayProtocol(asyncio.DatagramProtocol):
    def __init__(self, relay: BroadcastRelay, instance_id: int, port_type: str):
        self.relay = relay
        self.instance_id = instance_id
        self.port_type = port_type

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.relay.forward(data, self.instance_id, self.port_type)

    def error_received(self, exc: Exception) -> None:
        logger.debug("Relay UDP error (instance %d, %s): %s",
                      self.instance_id, self.port_type, exc)


def build_instance_ports(
    network_config: NetworkConfig, instance_count: int
) -> list[InstancePorts]:
    """Build the port configuration for each instance."""
    result = []
    for i in range(instance_count):
        base_offset = i * network_config.port_stride
        result.append(InstancePorts(
            instance_id=i,
            port=23756 + base_offset,
            broadcast_port=23757 + base_offset,
            query_port=23758 + base_offset,
        ))
    return result


async def run_relay(
    network_config: NetworkConfig, instance_count: int
) -> BroadcastRelay:
    """Create and start the broadcast relay."""
    instances = build_instance_ports(network_config, instance_count)
    relay = BroadcastRelay(instances)
    await relay.start()
    return relay
