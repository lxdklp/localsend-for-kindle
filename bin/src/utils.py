import hashlib
import mimetypes
import os
import socket
import uuid
from pathlib import Path

from src.config import DEFAULT_PORT
from src.models import FileInfo

CHUNK_SIZE = 65536

# 获取本地 IP 地址
def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# 生成随机 ID
def generate_file_id() -> str:
    return str(uuid.uuid4())[:8]

# 计算 SHA256 哈希
def file_sha256(path: str, chunk_size: int = CHUNK_SIZE) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

# 设备信息
def build_file_info(filepath: str, chunk_size: int = CHUNK_SIZE) -> FileInfo:
    p = Path(filepath)
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    fid = generate_file_id()
    return FileInfo(
        id=fid,
        file_name=p.name,
        size=p.stat().st_size,
        file_type=mime,
        sha256=file_sha256(filepath, chunk_size),
        local_path=str(p.resolve()),
    )

# 处理文件名冲突
def safe_filename(name: str, dest_dir: Path) -> Path:
    name = Path(name).name
    target = dest_dir / name
    if not target.exists():
        return target
    stem, suffix = os.path.splitext(name)
    counter = 1
    while True:
        target = dest_dir / f"{stem}({counter}){suffix}"
        if not target.exists():
            return target
        counter += 1

# 格式化文件大小
def format_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
