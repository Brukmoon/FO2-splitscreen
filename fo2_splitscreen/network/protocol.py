"""Virtual network packet protocol for FlatOut 2 LAN relay.

The proxy wraps/unwraps game UDP packets with a VirtIPHeader so that
multiple instances on the same machine appear to be on separate IPs.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from ipaddress import IPv4Address


# Header prepended to relayed packets (matches reference VirtIPHeader)
HEADER_FORMAT = "!IH"  # network byte order: uint32 source_ip, uint16 source_port
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 6 bytes


@dataclass
class VirtIPHeader:
    source_ip: str
    source_port: int

    def pack(self) -> bytes:
        ip_int = int(IPv4Address(self.source_ip))
        return struct.pack(HEADER_FORMAT, ip_int, self.source_port)

    @classmethod
    def unpack(cls, data: bytes) -> tuple[VirtIPHeader, bytes]:
        """Unpack header from data, return (header, remaining_payload)."""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Packet too small for VirtIPHeader: {len(data)} bytes")
        ip_int, port = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
        header = cls(source_ip=str(IPv4Address(ip_int)), source_port=port)
        return header, data[HEADER_SIZE:]


def virtual_ip_for_instance(instance_id: int, base: str = "192.168.80.0", offset: int = 1) -> str:
    """Compute the virtual IP address for a given instance."""
    base_ip = int(IPv4Address(base))
    return str(IPv4Address(base_ip + offset + instance_id))
