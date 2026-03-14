from __future__ import annotations

import hashlib
import logging
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from aiohttp import web

from src.config import API_BASE, DEFAULT_PORT
from src.models import DeviceInfo, DownloadSession, FileInfo, UploadSession
from src.utils import format_size, safe_filename

if TYPE_CHECKING:
    from src.app import LocalSendApp

log = logging.getLogger("localsend")

# 创建 aiohttp Application
def create_routes(app_ref: "LocalSendApp") -> web.Application:
    handler = _Handler(app_ref)
    wapp = web.Application()
    wapp.router.add_post(f"{API_BASE}/register", handler.register)
    wapp.router.add_get(f"{API_BASE}/info", handler.info)
    wapp.router.add_post(f"{API_BASE}/prepare-upload", handler.prepare_upload)
    wapp.router.add_post(f"{API_BASE}/upload", handler.upload)
    wapp.router.add_post(f"{API_BASE}/cancel", handler.cancel)
    wapp.router.add_post(f"{API_BASE}/prepare-download", handler.prepare_download)
    wapp.router.add_get(f"{API_BASE}/download", handler.download)
    wapp.router.add_get("/", handler.browser_index)
    return wapp

### HTTP 请求处理类
class _Handler:
    def __init__(self, app: "LocalSendApp"):
        self.app = app
    # 设备信息
    @property
    def device(self) -> DeviceInfo:
        return self.app.device
    # PIN 码
    @property
    def pin(self) -> str:
        return self.app.cfg.pin
    # 块大小
    @property
    def chunk_size(self) -> int:
        return self.app.cfg.chunk_size
    # 获取请求的远程 IP 地址
    def _remote(self, request: web.Request) -> str:
        return request.remote or "0.0.0.0"
    # 处理设备注册
    # POST /api/localsend/v2/register
    async def register(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid body"}, status=400)
        peer = DeviceInfo(
            alias=data.get("alias", "Unknown"),
            version=data.get("version", "2.0"),
            device_model=data.get("deviceModel"),
            device_type=data.get("deviceType", "desktop"),
            fingerprint=data.get("fingerprint", ""),
            port=data.get("port", DEFAULT_PORT),
            protocol=data.get("protocol", "https"),
            download=data.get("download", False),
            ip=self._remote(request),
        )
        self.app.peers[peer.fingerprint] = peer
        log.info("设备注册: %s (%s) @ %s", peer.alias, peer.device_model, peer.ip)
        return web.json_response(self.device.to_register())
    # GET /api/localsend/v2/info
    async def info(self, request: web.Request) -> web.Response:
        return web.json_response(self.device.to_info())
    # POST /api/localsend/v2/prepare-upload
    async def prepare_upload(self, request: web.Request) -> web.Response:
        if self.pin:
            pin_param = request.query.get("pin", "")
            if pin_param != self.pin:
                msg = "PIN required" if not pin_param else "Invalid PIN"
                return web.json_response({"error": msg}, status=401)
        # 检查活跃会话
        active_sid = self.app.active_upload_session
        if active_sid:
            sess = self.app.upload_sessions.get(active_sid)
            if sess and sess.is_valid():
                return web.json_response({"error": "Blocked by another session"}, status=409)
            self.app.active_upload_session = None
        try:
            data = await request.json()
        except Exception as e:
            log.warning("prepare-upload JSON 解析失败: %s", e)
            return web.json_response({"error": "Invalid body"}, status=400)
        info_dict = data.get("info", {})
        files: dict = data.get("files", {})
        if not files:
            log.warning("prepare-upload 缺少 files 字段")
            return web.json_response({"error": "Invalid body"}, status=400)
        sender_alias = info_dict.get("alias", "Unknown")
        total_size = sum(f.get("size", 0) for f in files.values())
        file_names = [f.get("fileName", "?") for f in files.values()]
        log.info(
            "收到来自 [%s] 的文件传输请求: %d 个文件, 总计 %s",
            sender_alias, len(files), format_size(total_size),
        )
        for name in file_names:
            log.info("  - %s", name)
        log.info("自动接受传输请求")
        session_id = secrets.token_urlsafe(16)
        session = UploadSession(
            session_id=session_id,
            sender_ip=self._remote(request),
            timeout=self.app.cfg.session_timeout,
        )
        tokens: Dict[str, str] = {}
        for file_id, file_data in files.items():
            fi = FileInfo(
                id=file_id,
                file_name=file_data.get("fileName", "unknown"),
                size=file_data.get("size", 0),
                file_type=file_data.get("fileType", "application/octet-stream"),
                sha256=file_data.get("sha256"),
            )
            token = secrets.token_urlsafe(16)
            session.files[file_id] = fi
            session.tokens[file_id] = token
            session.received[file_id] = False
            tokens[file_id] = token
        self.app.upload_sessions[session_id] = session
        self.app.active_upload_session = session_id
        if not tokens:
            return web.Response(status=204)
        log.info("已接受传输, sessionId=%s", session_id)
        return web.json_response({"sessionId": session_id, "files": tokens})
    # POST /api/localsend/v2/upload
    async def upload(self, request: web.Request) -> web.Response:
        session_id = request.query.get("sessionId", "")
        file_id = request.query.get("fileId", "")
        token = request.query.get("token", "")
        if not all([session_id, file_id, token]):
            return web.json_response({"error": "Missing parameters"}, status=400)
        session = self.app.upload_sessions.get(session_id)
        if not session or not session.is_valid():
            return web.json_response({"error": "Invalid token or IP address"}, status=403)
        if session.tokens.get(file_id) != token:
            return web.json_response({"error": "Invalid token or IP address"}, status=403)
        if session.sender_ip != self._remote(request):
            return web.json_response({"error": "Invalid token or IP address"}, status=403)
        file_info = session.files.get(file_id)
        if not file_info:
            return web.json_response({"error": "Invalid file"}, status=400)
        # 按扩展名选择接收目录
        ext = Path(file_info.file_name).suffix.lower()
        book_exts = [e.lower() for e in self.app.cfg.book_extensions]
        if ext in book_exts:
            recv_dir = Path(self.app.cfg.book_dest)
        else:
            recv_dir = self.app.receive_dir
        recv_dir.mkdir(parents=True, exist_ok=True)
        dest = safe_filename(file_info.file_name, recv_dir)
        log.info("接收目录: %s (扩展名: %s)", recv_dir, ext)
        received = 0
        sha = hashlib.sha256()
        try:
            with open(dest, "wb") as f:
                async for chunk, _ in request.content.iter_chunks():
                    f.write(chunk)
                    sha.update(chunk)
                    received += len(chunk)
                    if file_info.size > 0:
                        pct = min(100, received * 100 // file_info.size)
                        print(
                            f"\r  接收 {file_info.file_name}: "
                            f"{format_size(received)}/{format_size(file_info.size)} ({pct}%)",
                            end="", flush=True,
                        )
        except Exception as e:
            log.error("文件接收失败: %s", e)
            if dest.exists():
                dest.unlink()
            return web.json_response({"error": "Unknown error by receiver"}, status=500)
        if file_info.sha256 and sha.hexdigest().lower() != file_info.sha256.lower():
            log.warning("SHA256 校验失败: %s", file_info.file_name)
        session.received[file_id] = True
        log.info("文件接收完成: %s -> %s", file_info.file_name, dest)
        if all(session.received.values()):
            log.info("会话 %s 所有文件传输完成!", session_id)
            self.app.active_upload_session = None
        return web.Response(status=200)
    # POST /api/localsend/v2/cancel
    async def cancel(self, request: web.Request) -> web.Response:
        session_id = request.query.get("sessionId", "")
        if session_id in self.app.upload_sessions:
            del self.app.upload_sessions[session_id]
            if self.app.active_upload_session == session_id:
                self.app.active_upload_session = None
            log.info("会话已取消: %s", session_id)
        return web.Response(status=200)
    # POST /api/localsend/v2/prepare-download
    async def prepare_download(self, request: web.Request) -> web.Response:
        if not self.app.files_to_send:
            return web.json_response({"error": "Rejected"}, status=403)
        if self.pin:
            existing_sid = request.query.get("sessionId", "")
            if existing_sid and existing_sid in self.app.download_sessions:
                ds = self.app.download_sessions[existing_sid]
                if ds.is_valid():
                    return web.json_response({
                        "info": self.device.to_info(),
                        "sessionId": ds.session_id,
                        "files": {fid: fi.to_dict() for fid, fi in ds.files.items()},
                    })
            pin_param = request.query.get("pin", "")
            if pin_param != self.pin:
                msg = "PIN required" if not pin_param else "Invalid PIN"
                return web.json_response({"error": msg}, status=401)
        session_id = secrets.token_urlsafe(16)
        session = DownloadSession(
            session_id=session_id,
            timeout=self.app.cfg.session_timeout,
            files=dict(self.app.files_to_send),
        )
        self.app.download_sessions[session_id] = session
        return web.json_response({
            "info": self.device.to_info(),
            "sessionId": session_id,
            "files": {fid: fi.to_dict() for fid, fi in self.app.files_to_send.items()},
        })
    # GET /api/localsend/v2/download
    async def download(self, request: web.Request) -> web.StreamResponse:
        session_id = request.query.get("sessionId", "")
        file_id = request.query.get("fileId", "")
        session = self.app.download_sessions.get(session_id)
        if not session or not session.is_valid():
            return web.json_response({"error": "Invalid session"}, status=403)
        file_info = session.files.get(file_id)
        if not file_info or not file_info.local_path:
            return web.json_response({"error": "File not found"}, status=404)
        local_path = Path(file_info.local_path)
        if not local_path.exists():
            return web.json_response({"error": "File not found"}, status=404)
        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": file_info.file_type,
                "Content-Length": str(file_info.size),
                "Content-Disposition": f'attachment; filename="{file_info.file_name}"',
            },
        )
        await resp.prepare(request)
        with open(local_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                await resp.write(chunk)
        await resp.write_eof()
        log.info("文件发送完成: %s -> %s", file_info.file_name, self._remote(request))
        return resp
    # 浏览器下载
    async def browser_index(self, request: web.Request) -> web.Response:
        if not self.app.files_to_send:
            return web.Response(text="No files available", status=404)
        sid = secrets.token_urlsafe(16)
        session = DownloadSession(
            session_id=sid,
            timeout=self.app.cfg.session_timeout,
            files=dict(self.app.files_to_send),
        )
        self.app.download_sessions[sid] = session
        html_parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>",
            "<title>LocalSend</title>",
            "<style>body{font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px}",
            "a{display:block;padding:10px;margin:5px 0;background:#f0f0f0;text-decoration:none;",
            "color:#333;border-radius:4px}a:hover{background:#e0e0e0}</style></head><body>",
            f"<h1>{self.device.alias}</h1><h3>可下载文件:</h3>",
        ]
        for fid, fi in self.app.files_to_send.items():
            url = f"{API_BASE}/download?sessionId={sid}&fileId={fid}"
            html_parts.append(
                f'<a href="{url}">{fi.file_name} ({format_size(fi.size)})</a>'
            )
        html_parts.append("</body></html>")
        return web.Response(text="".join(html_parts), content_type="text/html")