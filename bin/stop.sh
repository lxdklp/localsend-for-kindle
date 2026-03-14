#!/bin/sh
#路径
PID_FILE=/mnt/us/extensions/localsend/bin/localsend.pid
CONFIG_FILE=/mnt/us/extensions/localsend/bin/config.json

# 检查 LocalSend 是否在运行
if [ ! -f "$PID_FILE" ]; then
    /usr/sbin/eips 1 35 "LocalSend not running (no PID file)"
    exit 0
fi

# 读取 PID 并尝试停止进程
PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    /usr/sbin/eips 1 35 "LocalSend stopped (PID: $PID)"
else
    /usr/sbin/eips 1 35 "Process $PID not found, already stopped"
fi
rm -f "$PID_FILE"

# 从 config.json 读取端口
PORT=$(/mnt/us/python3/bin/python3.14 -c "import json; print(json.load(open('$CONFIG_FILE')).get('port', 53317))" 2>/dev/null)
if [ -z "$PORT" ] || [ "$PORT" = "None" ]; then
    PORT=53317
fi

# 移除 iptables 规则
iptables -D INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null
iptables -D INPUT -p udp --dport "$PORT" -j ACCEPT 2>/dev/null
