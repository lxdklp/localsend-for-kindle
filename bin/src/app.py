from __future__ import annotations

import asyncio
import logging
import platform
import secrets
import ssl
from pathlib import Path
from typing import Dict, Optional, Union

from aiohttp import web

from src.network.cert import CertManager
from src.network.client import reply_register
from src.config import Config
from src.network.discovery import MulticastDiscovery
from src.models import DeviceInfo, DownloadSession, FileInfo, UploadSession
from src.network.server import create_routes
from src.utils import get_local_ip

log = logging.getLogger("localsend")

# LocalSend 主应用类
class LocalSendApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.device = DeviceInfo(
            alias=cfg.alias,
            device_model=cfg.device_model or platform.system(),
            port=cfg.port,
            protocol="http" if cfg.http else "https",
            device_type=cfg.device_type,
        )
        self.peers: Dict[str, DeviceInfo] = {}
        self.upload_sessions: Dict[str, UploadSession] = {}
        self.download_sessions: Dict[str, DownloadSession] = {}
        self.active_upload_session: Optional[str] = None
        self.files_to_send: Dict[str, FileInfo] = {}

        self.receive_dir = Path(cfg.dest).resolve()
        self.receive_dir.mkdir(parents=True, exist_ok=True)
        # 证书
        if not cfg.http:
            cert_dir = Path("/mnt/us/extensions/localsend/bin/cert")
            cm = CertManager(cert_dir)
            cert_path, key_path, fingerprint = cm.ensure_cert()
            self.device.fingerprint = fingerprint
            self.ssl_ctx: Optional[ssl.SSLContext] = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.ssl_ctx.load_cert_chain(cert_path, key_path)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self.client_ssl: Union[ssl.SSLContext, bool] = ctx
        else:
            self.device.fingerprint = secrets.token_hex(16)
            self.ssl_ctx = None
            self.client_ssl = False
        # 组播发现
        self.discovery = MulticastDiscovery(
            self.device, self._on_peer_found,
            announce_interval=cfg.announce_interval,
        )

    ### 设备发现回调
    def _on_peer_found(self, peer: DeviceInfo, is_announce: bool) -> None:
        if peer.fingerprint == self.device.fingerprint:
            return
        is_new = peer.fingerprint not in self.peers
        self.peers[peer.fingerprint] = peer
        if is_new:
            log.info("发现设备: %s (%s) @ %s:%d", peer.alias, peer.device_type, peer.ip, peer.port)
        if is_announce:
            asyncio.ensure_future(reply_register(self, peer))

    ### 会话清理
    def _cleanup_sessions(self) -> None:
        expired = [sid for sid, s in self.upload_sessions.items() if not s.is_valid()]
        for sid in expired:
            del self.upload_sessions[sid]
            if self.active_upload_session == sid:
                self.active_upload_session = None
        expired = [sid for sid, s in self.download_sessions.items() if not s.is_valid()]
        for sid in expired:
            del self.download_sessions[sid]

    ### 接收模式
    async def run_server(self) -> None:
        wapp = create_routes(self)
        runner = web.AppRunner(wapp)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.device.port, ssl_context=self.ssl_ctx)
        try:
            await site.start()
            proto_name = "HTTPS" if self.ssl_ctx else "HTTP"
            local_ip = get_local_ip()
            log.info("LocalSend 服务器启动: %s://%s:%d", proto_name.lower(), local_ip, self.device.port)
            log.info("设备名称: %s | 指纹: %s", self.device.alias, self.device.fingerprint[:16] + "...")
            log.info("文件接收目录: %s", self.receive_dir)
            if self.cfg.pin:
                log.info("PIN 保护已启用")
            if self.files_to_send:
                log.info("共享文件: %d 个, 浏览器下载: http://%s:%d", len(self.files_to_send), local_ip, self.device.port)
        except OSError as e:
            if e.errno == 98:
                log.warning("端口 %d 已被占用,HTTP 服务器未启动（仅组播发现模式）", self.device.port)
            else:
                raise
        try:
            await self.discovery.start()
            asyncio.ensure_future(self.discovery.announce_loop())
        except Exception as e:
            log.warning("Multicast 发现启动失败: %s (将使用 HTTP 回退模式)", e)
        try:
            while True:
                self._cleanup_sessions()
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
        finally:
            self.discovery.stop()
            await runner.cleanup()