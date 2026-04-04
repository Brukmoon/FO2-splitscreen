"""Tests for virtual network protocol."""

from fo2_splitscreen.network.protocol import VirtIPHeader, virtual_ip_for_instance


def test_header_pack_unpack():
    header = VirtIPHeader(source_ip="192.168.80.1", source_port=23756)
    packed = header.pack()
    payload = b"hello game data"
    data = packed + payload

    unpacked, remaining = VirtIPHeader.unpack(data)
    assert unpacked.source_ip == "192.168.80.1"
    assert unpacked.source_port == 23756
    assert remaining == payload


def test_virtual_ip_for_instance():
    assert virtual_ip_for_instance(0) == "192.168.80.1"
    assert virtual_ip_for_instance(1) == "192.168.80.2"
    assert virtual_ip_for_instance(7) == "192.168.80.8"


def test_header_roundtrip_multiple():
    for ip, port in [("10.0.0.1", 1234), ("255.255.255.255", 65535), ("0.0.0.0", 0)]:
        header = VirtIPHeader(source_ip=ip, source_port=port)
        restored, _ = VirtIPHeader.unpack(header.pack() + b"x")
        assert restored.source_ip == ip
        assert restored.source_port == port
