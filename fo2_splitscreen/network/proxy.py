"""Asyncio UDP relay proxy for virtual LAN between FlatOut 2 instances.

Each game instance binds to a different LAN port (configured via options.cfg).
The proxy intercepts traffic and relays between instances, enabling LAN
discovery and gameplay across instances on the same machine.

Architecture:
  Instance 0 (host):   query_port=23756, game_port=23757
  Instance 1 (client): query_port=23760, game_port=23761

  The proxy does NOT bind the game's ports (the game itself binds them).
  Instead, it binds separate relay ports and uses them to forward packets
  between instances via localhost.

Discovery flow:
  1. Instance 1 broadcasts a LAN query on its query_port
  2. Proxy captures it and forwards to instance 0's query_port
  3. Instance 0 replies; proxy forwards reply back to instance 1
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from ..config import NetworkConfig

logger = logging.getLogger(__name__)

# The proxy relay port offset — relay sockets bind at game_port + RELAY_OFFSET
# to avoid conflicting with the game's own port bindings.
RELAY_PORT_OFFSET = 100


@dataclass
class InstanceEndpoint:
    instance_id: int
    query_port: int
    game_port: int


class RelayProtocol(asyncio.DatagramProtocol):
    """UDP protocol that relays packets between game instances."""

    def __init__(self, proxy: LANProxy, port_label: str) -> None:
        self.proxy = proxy
        self.port_label = port_label
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.proxy.handle_packet(data, addr, self.port_label)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error on %s: %s", self.port_label, exc)

    def send_to(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.transport:
            self.transport.sendto(data, addr)


class LANProxy:
    """Central relay that bridges FlatOut 2 LAN traffic between instances.

    For each instance, the proxy creates a relay socket. When the game sends
    a packet, the proxy's relay socket for the TARGET instance forwards it
    to that instance's game port on localhost.

    This avoids the bootstrap problem: the proxy always knows where each
    instance listens (its configured query_port/game_port on 127.0.0.1),
    so it can forward immediately without waiting for the target to send first.
    """

    def __init__(self, network_config: NetworkConfig, instance_count: int) -> None:
        self.config = network_config
        self.instance_count = instance_count
        self.endpoints: list[InstanceEndpoint] = []
        # label -> RelayProtocol (e.g. "query_0", "game_1")
        self.protocols: dict[str, RelayProtocol] = {}
        # Track which source port belongs to which instance
        self._source_port_to_instance: dict[int, int] = {}

        for i in range(instance_count):
            ep = InstanceEndpoint(
                instance_id=i,
                query_port=network_config.query_port_for(i),
                game_port=network_config.game_port_for(i),
            )
            self.endpoints.append(ep)

    async def start(self) -> None:
        """Create relay sockets for all instances.

        For each instance, we create two relay sockets:
        - One for query traffic (discovery)
        - One for game traffic

        These relay sockets listen on separate ports and forward to the
        appropriate game instance ports.
        """
        loop = asyncio.get_running_loop()

        for ep in self.endpoints:
            for kind, game_port in [("query", ep.query_port), ("game", ep.game_port)]:
                relay_port = game_port + RELAY_PORT_OFFSET
                label = f"{kind}_{ep.instance_id}"
                try:
                    transport, protocol = await loop.create_datagram_endpoint(
                        lambda lbl=label: RelayProtocol(self, lbl),
                        local_addr=("127.0.0.1", relay_port),
                    )
                    self.protocols[label] = protocol
                    logger.info(
                        "Relay %s listening on 127.0.0.1:%d (forwards to game port %d)",
                        label, relay_port, game_port,
                    )
                except OSError as e:
                    logger.error("Failed to bind relay port %d: %s", relay_port, e)

        # Also listen on each game port to intercept outgoing game traffic.
        # But the game binds these ports — so we use a sniffer approach:
        # We set SO_REUSEADDR to share the port with the game.
        for ep in self.endpoints:
            for kind, port in [("query", ep.query_port), ("game", ep.game_port)]:
                label = f"sniff_{kind}_{ep.instance_id}"
                try:
                    transport, protocol = await loop.create_datagram_endpoint(
                        lambda lbl=label: RelayProtocol(self, lbl),
                        local_addr=("127.0.0.1", port),
                        reuse_port=True,
                    )
                    self.protocols[label] = protocol
                    self._source_port_to_instance[port] = ep.instance_id
                    logger.info("Sniffer %s on 127.0.0.1:%d", label, port)
                except OSError:
                    # Expected on Windows — SO_REUSEPORT not supported.
                    # Fall back to proxy-only approach without sniffing.
                    logger.debug(
                        "Could not share port %d (expected on Windows), "
                        "using relay-only mode",
                        port,
                    )

    def handle_packet(self, data: bytes, addr: tuple[str, int], port_label: str) -> None:
        """Route a received packet to other instances."""
        # Determine source instance from the label or source address
        parts = port_label.split("_")
        if parts[0] == "sniff":
            # Packet from a game instance's bound port
            kind = parts[1]  # "query" or "game"
            source_id = int(parts[2])
            self._forward_to_others(data, source_id, kind)
        else:
            # Packet received on a relay socket — this is a response
            # from a game instance, forward it back
            kind = parts[0]
            relay_instance = int(parts[1])
            # The game sent this to our relay port thinking it was another player.
            # Forward to all other instances.
            self._forward_to_others(data, relay_instance, kind)

    def _forward_to_others(self, data: bytes, source_instance: int, kind: str) -> None:
        """Forward a packet from source_instance to all other instances."""
        for ep in self.endpoints:
            if ep.instance_id == source_instance:
                continue
            target_port = ep.query_port if kind == "query" else ep.game_port
            # Send from our relay socket for this target to the target's game port
            relay_label = f"{kind}_{ep.instance_id}"
            protocol = self.protocols.get(relay_label)
            if protocol:
                protocol.send_to(data, ("127.0.0.1", target_port))
                logger.debug(
                    "Forwarded %d bytes: instance %d -> instance %d (%s port %d)",
                    len(data), source_instance, ep.instance_id, kind, target_port,
                )

    async def stop(self) -> None:
        """Close all sockets."""
        for protocol in self.protocols.values():
            if protocol.transport:
                protocol.transport.close()
        self.protocols.clear()
        logger.info("Proxy stopped")


async def run_proxy(network_config: NetworkConfig, instance_count: int) -> LANProxy:
    """Create and start the LAN proxy. Returns the proxy (call stop() to shut down)."""
    proxy = LANProxy(network_config, instance_count)
    await proxy.start()
    return proxy
