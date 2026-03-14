#!/bin/sh
export LD_LIBRARY_PATH=/mnt/us/extensions/localsend/bin/lib:$LD_LIBRARY_PATH

# 路径
LOG_DIR=/mnt/us/extensions/localsend/bin/logs
LOG_FILE=/mnt/us/extensions/localsend/bin/logs/localsend_send.log

# 创建日志目录
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi
: > "$LOG_FILE"

# 关闭 LocalSend 接收
bash /mnt/us/extensions/localsend/bin/stop.sh

# 启动 LocalSend 发送
/mnt/us/python3/bin/python3.14 /mnt/us/extensions/localsend/bin/localsend.py send "$@"  \
    >> "$LOG_FILE" 2>&1 &
