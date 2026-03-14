#!/bin/sh
export LD_LIBRARY_PATH=/mnt/us/extensions/localsend/bin/lib:$LD_LIBRARY_PATH

# 路径
PID_FILE=/mnt/us/extensions/localsend/bin/localsend.pid
LOG_DIR=/mnt/us/extensions/localsend/bin/logs
LOG_FILE=/mnt/us/extensions/localsend/bin/logs/localsend_receive.log
CONFIG_FILE=/mnt/us/extensions/localsend/bin/config.json

# 创建日志目录
if [ ! -d "$LOG_DIR" ]; then
    mkdir -p "$LOG_DIR"
fi
: > "$LOG_FILE"

# 检查 LocalSend 是否已在运行
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    /usr/sbin/eips 1 35 "LocalSend already running (PID: $(cat "$PID_FILE"))"
    exit 0
fi

# 从 config.json 读取端口
PORT=$(/mnt/us/python3/bin/python3.14 -c "import json; print(json.load(open('$CONFIG_FILE')).get('port', 53317))" 2>/dev/null)
if [ -z "$PORT" ] || [ "$PORT" = "None" ]; then
    PORT=53317
fi

# 开放端口
iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null
iptables -I INPUT -p udp --dport "$PORT" -j ACCEPT 2>/dev/null

# 启动 LocalSend 接收
/mnt/us/python3/bin/python3.14 /mnt/us/extensions/localsend/bin/localsend.py receive \
    >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
/usr/sbin/eips 1 35 "LocalSend started (PID: $!)"
