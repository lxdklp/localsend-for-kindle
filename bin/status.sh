#!/bin/sh
# 路径
PID_FILE=/mnt/us/extensions/localsend/bin/localsend.pid
LOG_DIR=/mnt/us/extensions/localsend/bin

# 打印工具
_R=35
_p() { /usr/sbin/eips 1 "$_R" "$1"; _R=$((_R + 1)); }

_p "=========================================="
_p "  LocalSend Receive Status"
_p "=========================================="

# 进程状态
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        _p "Status : Running"
        _p "PID    : $PID"
        if [ -f /proc/"$PID"/stat ]; then
            START=$(awk '{print $22}' /proc/"$PID"/stat 2>/dev/null)
            HZ=$(getconf CLK_TCK 2>/dev/null || echo 100)
            UPTIME_SEC=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 0)
            if [ -n "$START" ] && [ "$HZ" -gt 0 ]; then
                ELAPSED=$(( UPTIME_SEC - START / HZ ))
                H=$(( ELAPSED / 3600 ))
                M=$(( (ELAPSED % 3600) / 60 ))
                S=$(( ELAPSED % 60 ))
                _p "Uptime : ${H}h ${M}m ${S}s"
            fi
        fi
    else
        _p "Status : Not running (stale PID file)"
        _p "PID    : $PID (stale)"
    fi
else
    _p "Status : Not running"
fi

_p "------------------------------------------"

# 配置信息
CONFIG=/mnt/us/extensions/localsend/bin/config.json
if [ -f "$CONFIG" ]; then
    ALIAS=$(grep '"alias"'         "$CONFIG" | sed 's/.*: *"\(.*\)".*/\1/')
    PORT=$(grep '"port"'           "$CONFIG" | sed 's/.*: *\([0-9]*\).*/\1/')
    HTTP=$(grep '"http"'           "$CONFIG" | sed 's/.*: *\(.*\),/\1/')
    DEST=$(grep '"dest"'           "$CONFIG" | sed 's/.*: *"\(.*\)".*/\1/')
    BOOK_DEST=$(grep '"book_dest"' "$CONFIG" | sed 's/.*: *"\(.*\)".*/\1/')
    _p "Alias    : ${ALIAS:-Kindle}"
    _p "Port     : ${PORT:-53317}"
    _p "Protocol : $([ "$HTTP" = "true" ] && echo HTTP || echo HTTPS)"
    _p "Book dir : ${BOOK_DEST:-/mnt/us/documents}"
    _p "Other dir: ${DEST:-/mnt/us/localsend}"
else
    _p "Config not found: $CONFIG"
fi

_p "------------------------------------------"

# 接收目录文件统计
for DIR in /mnt/us/documents /mnt/us/localsend; do
    if [ -d "$DIR" ]; then
        COUNT=$(find "$DIR" -maxdepth 1 -type f 2>/dev/null | wc -l)
        _p "$DIR: $COUNT files"
    fi
done

_p "------------------------------------------"