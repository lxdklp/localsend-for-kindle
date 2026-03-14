import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from src.config import PROTOCOL_VERSION, DEFAULT_PORT

# 数据模型
@dataclass
class DeviceInfo:
    alias: str
    version: str = PROTOCOL_VERSION
    device_model: Optional[str] = None
    device_type: str = "headless"
    fingerprint: str = ""
    port: int = DEFAULT_PORT
    protocol: str = "https"
    download: bool = True
    ip: str = ""

    # 转换
    # 转为 multicast 公告格式
    def to_announcement(self, announce: bool = True) -> dict:
        return {
            "alias": self.alias,
            "version": self.version,
            "deviceModel": self.device_model,
            "deviceType": self.device_type,
            "fingerprint": self.fingerprint,
            "port": self.port,
            "protocol": self.protocol,
            "download": self.download,
            "announce": announce,
        }
    # 转为 HTTP 注册格式
    def to_register(self) -> dict:
        return {
            "alias": self.alias,
            "version": self.version,
            "deviceModel": self.device_model,
            "deviceType": self.device_type,
            "fingerprint": self.fingerprint,
            "port": self.port,
            "protocol": self.protocol,
            "download": self.download,
        }
    # 转为设备信息格式
    def to_info(self) -> dict:
        return {
            "alias": self.alias,
            "version": self.version,
            "deviceModel": self.device_model,
            "deviceType": self.device_type,
            "fingerprint": self.fingerprint,
            "download": self.download,
        }

# 文件信息、上传会话、下载会话
@dataclass
class FileInfo:
    id: str
    file_name: str
    size: int
    file_type: str = "application/octet-stream"
    sha256: Optional[str] = None
    preview: Optional[str] = None
    local_path: Optional[str] = None

    # 转为字典
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fileName": self.file_name,
            "size": self.size,
            "fileType": self.file_type,
            "sha256": self.sha256,
            "preview": self.preview,
        }

# 上传会话
@dataclass
class UploadSession:
    session_id: str
    sender_ip: str
    timeout: int = 600
    files: Dict[str, FileInfo] = field(default_factory=dict)
    tokens: Dict[str, str] = field(default_factory=dict)
    received: Dict[str, bool] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    def is_valid(self) -> bool:
        return (time.time() - self.created_at) < self.timeout

# 下载会话
@dataclass
class DownloadSession:
    session_id: str
    timeout: int = 600
    files: Dict[str, FileInfo] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    def is_valid(self) -> bool:
        return (time.time() - self.created_at) < self.timeout
