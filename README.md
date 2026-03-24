<p align="center"> <img src=https://img.shields.io/badge/GPLv3-1?style=for-the-badge&label=License> <img src=https://img.shields.io/badge/3.14.3-1?logo=python&logoColor=white&style=for-the-badge&label=Python> </p>

# LocalSend for Kindle
### 根据 localsend V2 协议编写的 Python 实现, 适用于 Kindle 5.16.3+ 设备
项目参考资料: https://github.com/localsend/protocol 、https://kindlemodding.org/kindle-dev/awesome-window-manager
# 安装
需要设备越狱, 并且安装 [Python](https://github.com/lxdklp/python-for-kindle) 与 [KUAL](https://www.mobileread.com/forums/showthread.php?t=225030) 如果需要发送文件功能, 还需要魔改版[kindle explorer](https://github.com/lxdklp/kindle-explorer)
# 配置
### 默认 config.json
```json
{
    "alias": "",
    "port": 53317,
    "http": false,
    "dest": "/mnt/us/localsend",
    "book_dest": "/mnt/us/documents",
    "book_extensions": [".azw3", ".mobi", ".kfx", ".pdf", ".txt", ".prc"],
    "pin": "1234",
    "device_model": "amazon",
    "device_type": "mobile",
    "announce_interval": 5,
    "session_timeout": 600,
    "chunk_size": 65536
}
```
| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| alias | 设备名称 | 空(空时显示为Kindle) |
| port | 监听端口 | 53317 |
| http | http模式 | false |
| dest | 接收文件的保存路径 | /mnt/us/localsend |
| book_dest | 接收书籍的保存路径 | /mnt/us/documents |
| book_extensions | 识别为书籍的文件扩展名列表 | [".azw3", ".mobi", ".kfx", ".pdf", ".txt", ".prc"] |
| pin | 连接 PIN 码 | 1234 |
| device_model | 设备型号, 用于协议中的设备信息 | amazon |
| device_type | 设备类型, 用于协议中的设备信息 | mobile |
| announce_interval | 设备信息广播间隔 | 5 |
| session_timeout | 会话超时时间 | 600 |
| chunk_size | 文件块大小 | 65536 |