import asyncio
import json
import logging
import socket
import struct
from typing import Callable, Optional, Tuple

from src.config import DEFAULT_PORT, MULTICAST_ADDR, MULTICAST_PORT
from src.models import DeviceInfo

log = logging.getLogger("localsend")

### MulticastDiscovery 设备发现类
class MulticastDiscovery:
    def __init__(self, device: DeviceInfo, on_peer_found: Callable[[DeviceInfo, bool], None],
                announce_interval: int = 5):
        self.device = device
        self.on_peer_found = on_peer_found
        self.announce_interval = announce_interval
        self.transport: Optional[asyncio.DatagramTransport] = None
    async def start(self) -> None:
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.bind(("", MULTICAST_PORT))
        group = socket.inet_aton(MULTICAST_ADDR)
        mreq = struct.pack("4sL", group, socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: _MulticastProtocol(self.device, self.on_peer_found),
            sock=sock,
        )
        log.info("Multicast 监听启动: %s:%d", MULTICAST_ADDR, MULTICAST_PORT)
    # 发送 multicast 公告
    async def announce(self) -> None:
        if not self.transport:
            return
        msg = json.dumps(self.device.to_announcement(announce=True)).encode()
        self.transport.sendto(msg, (MULTICAST_ADDR, MULTICAST_PORT))
    # 周期性广播
    async def announce_loop(self) -> None:
        while True:
            try:
                await self.announce()
            except Exception as e:
                log.debug("Announce error: %s", e)
            await asyncio.sleep(self.announce_interval)
    # 停止监听
    def stop(self) -> None:
        if self.transport:
            self.transport.close()

### MulticastDiscovery 的 DatagramProtocol 实现
class _MulticastProtocol(asyncio.DatagramProtocol):
    def __init__(self, device: DeviceInfo, on_peer_found: Callable[[DeviceInfo, bool], None]):
        self.device = device
        self.on_peer_found = on_peer_found
    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        try:
            msg = json.loads(data.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        fp = msg.get("fingerprint", "")
        if fp == self.device.fingerprint:
            return
        peer = DeviceInfo(
            alias=msg.get("alias", "Unknown"),
            version=msg.get("version", "2.0"),
            device_model=msg.get("deviceModel"),
            device_type=msg.get("deviceType", "desktop"),
            fingerprint=fp,
            port=msg.get("port", DEFAULT_PORT),
            protocol=msg.get("protocol", "https"),
            download=msg.get("download", False),
            ip=addr[0],
        )
        is_announce: bool = msg.get("announce", False)
        asyncio.get_event_loop().call_soon(self.on_peer_found, peer, is_announce)
