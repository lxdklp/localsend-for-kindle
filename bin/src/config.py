import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

PROTOCOL_VERSION = "2.0"
DEFAULT_PORT = 53317
MULTICAST_ADDR = "224.0.0.167"
MULTICAST_PORT = 53317
API_BASE = "/api/localsend/v2"

_CONFIG_FILE = Path(__file__).parent / "../config.json"

# 配置项
@dataclass
class Config:
    alias: str
    port: int = DEFAULT_PORT
    http: bool = False
    dest: str = "/mnt/us/localsend"
    book_dest: str = "/mnt/us/documents"
    book_extensions: List[str] = field(default_factory=lambda: [".azw3", ".mobi", ".kfx", ".pdf", ".txt", ".prc"])
    pin: str = ""
    device_model: str = ""
    device_type: str = "mobile"
    announce_interval: int = 5
    session_timeout: int = 600
    chunk_size: int = 65536
    command: str = "receive"
    files: Optional[list[str]] = None
    verbose: bool = False

# 从 config.json 加载配置
def load_config() -> Config:
    data: dict = {}
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    alias = data.get("alias", "") or "Kindle"
    device_model = data.get("device_model", "") or "amazon"
    return Config(
        alias=alias,
        port=data.get("port", DEFAULT_PORT),
        http=data.get("http", False),
        dest=data.get("dest", "/mnt/us/localsend"),
        book_dest=data.get("book_dest", "/mnt/us/documents"),
        book_extensions=data.get("book_extensions", [".azw3", ".mobi", ".kfx", ".pdf", ".txt", ".prc"]),
        pin=data.get("pin", "") or "",
        device_model=device_model,
        device_type=data.get("device_type", "mobile"),
        announce_interval=data.get("announce_interval", 5),
        session_timeout=data.get("session_timeout", 600),
        chunk_size=data.get("chunk_size", 65536),
    )
