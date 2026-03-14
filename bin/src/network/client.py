from __future__ import annotations

import asyncio
import logging
import ssl
from typing import TYPE_CHECKING, List, Optional, Union

import aiohttp

from src.config import API_BASE, DEFAULT_PORT
from src.models import DeviceInfo, FileInfo
from src.utils import format_size

if TYPE_CHECKING:
    from src.app import LocalSendApp

log = logging.getLogger("localsend")

# 构建 TCPConnector
def _connector(client_ssl: Union[ssl.SSLContext, bool], proto: str) -> aiohttp.TCPConnector:
    if proto == "https" and isinstance(client_ssl, ssl.SSLContext):
        return aiohttp.TCPConnector(ssl=client_ssl)
    return aiohttp.TCPConnector(ssl=False)

# 发送文件
async def send_files(
    app: "LocalSendApp",
    peer: DeviceInfo,
    files: List[FileInfo],
) -> bool:
    base_url = f"{peer.protocol}://{peer.ip}:{peer.port}{API_BASE}"
    chunk_size = app.cfg.chunk_size
    connector = _connector(app.client_ssl, peer.protocol)
    async with aiohttp.ClientSession(connector=connector) as session:
        files_dict = {fi.id: fi.to_dict() for fi in files}
        payload = {
            "info": app.device.to_register(),
            "files": files_dict,
        }
        url = f"{base_url}/prepare-upload"
        if app.cfg.pin:
            url += f"?pin={app.cfg.pin}"
        log.info("发送传输请求到 %s ...", peer.alias)
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status == 204:
                    log.info("对方不需要任何文件")
                    return True
                if resp.status == 401:
                    log.error("需要PIN或PIN无效")
                    return False
                if resp.status == 403:
                    log.error("对方拒绝接收")
                    return False
                if resp.status == 409:
                    log.error("对方正在进行其他传输")
                    return False
                if resp.status != 200:
                    body = await resp.text()
                    log.error("prepare-upload 失败: %d %s", resp.status, body)
                    return False
                result = await resp.json()
        except aiohttp.ClientError as e:
            log.error("连接失败: %s", e)
            return False
        session_id: str = result.get("sessionId", "")
        file_tokens: dict = result.get("files", {})
        if not session_id or not file_tokens:
            log.error("无效的prepare-upload响应")
            return False
        log.info("对方已接受, 开始传输 %d 个文件...", len(file_tokens))
        success = True
        for file_id, token in file_tokens.items():
            fi = next((f for f in files if f.id == file_id), None)
            if not fi or not fi.local_path:
                continue
            upload_url = (
                f"{base_url}/upload"
                f"?sessionId={session_id}&fileId={file_id}&token={token}"
            )
            log.info("发送: %s (%s)", fi.file_name, format_size(fi.size))
            try:
                with open(fi.local_path, "rb") as f:
                    fi_ref = fi
                    async def file_sender(
                        fobj=f, file_info: FileInfo = fi_ref, cs: int = chunk_size
                    ):
                        sent = 0
                        while True:
                            chunk = fobj.read(cs)
                            if not chunk:
                                break
                            sent += len(chunk)
                            if file_info.size > 0:
                                pct = min(100, sent * 100 // file_info.size)
                                print(
                                    f"\r  发送 {file_info.file_name}: "
                                    f"{format_size(sent)}/{format_size(file_info.size)} ({pct}%)",
                                    end="", flush=True,
                                )
                            yield chunk
                    async with session.post(upload_url, data=file_sender()) as resp:
                        print()
                        if resp.status != 200:
                            body = await resp.text()
                            log.error("上传失败 %s: %d %s", fi.file_name, resp.status, body)
                            success = False
                        else:
                            log.info("发送完成: %s", fi.file_name)
            except Exception as e:
                log.error("发送文件出错: %s - %s", fi.file_name, e)
                success = False
        if success:
            log.info("所有文件发送成功!")
        return success

# 回复 multicast announce，通过 HTTP 注册
async def reply_register(app: "LocalSendApp", peer: DeviceInfo) -> None:
    url = f"{peer.protocol}://{peer.ip}:{peer.port}{API_BASE}/register"
    connector = _connector(app.client_ssl, peer.protocol)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                url,
                json=app.device.to_register(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    log.debug("已回复注册到 %s", peer.alias)
    except Exception as e:
        log.debug("回复注册失败 %s: %s", peer.alias, e)

# 扫描局域网设备
async def scan_network(app: "LocalSendApp") -> List[DeviceInfo]:
    from src.utils import get_local_ip
    local_ip = get_local_ip()
    prefix = ".".join(local_ip.split(".")[:3])
    found: List[DeviceInfo] = []
    sem = asyncio.Semaphore(50)
    async def try_ip(ip: str) -> None:
        async with sem:
            for proto in ("https", "http"):
                url = f"{proto}://{ip}:{DEFAULT_PORT}{API_BASE}/register"
                connector = _connector(app.client_ssl, proto)
                try:
                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.post(
                            url,
                            json=app.device.to_register(),
                            timeout=aiohttp.ClientTimeout(total=2),
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                peer = DeviceInfo(
                                    alias=data.get("alias", "Unknown"),
                                    version=data.get("version", "2.0"),
                                    device_model=data.get("deviceModel"),
                                    device_type=data.get("deviceType", "desktop"),
                                    fingerprint=data.get("fingerprint", ""),
                                    port=DEFAULT_PORT,
                                    protocol=proto,
                                    download=data.get("download", False),
                                    ip=ip,
                                )
                                app.peers[peer.fingerprint] = peer
                                found.append(peer)
                                return
                except Exception:
                    pass
    tasks = [try_ip(f"{prefix}.{i}") for i in range(1, 255) if f"{prefix}.{i}" != local_ip]
    await asyncio.gather(*tasks)
    return found
