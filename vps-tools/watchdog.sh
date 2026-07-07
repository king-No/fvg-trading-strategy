#!/bin/bash
# VPS 自我监控 — 每5分钟检查，挂了自动恢复
LOG="/root/fvg/watchdog.log"

log() { echo "[$(date)] $1" >> "$LOG"; }

# 检查看板 — 进程+端口双检测
DASH_PID=$(pgrep -f "trade_dashboard" | head -1)
if [ -z "$DASH_PID" ]; then
    log "看板进程不存在, 重启..."
    cd /root/fvg || exit 1
    nohup ./venv/bin/python trade_dashboard.py > /dev/null 2>&1 &
    sleep 2
elif ! curl -s --connect-timeout 3 -o /dev/null http://127.0.0.1:8899; then
    log "看板进程($DASH_PID)无响应, 重启..."
    kill -9 "$DASH_PID" 2>/dev/null
    sleep 1
    cd /root/fvg || exit 1
    nohup ./venv/bin/python trade_dashboard.py > /dev/null 2>&1 &
    sleep 2
fi

# 检查Freqtrade
if ! ps aux | grep -q "[f]reqtrade trade"; then
    log "Freqtrade挂了, 重启..."
    cd /root/freqtrade || exit 1
    nohup .venv/bin/freqtrade trade --strategy LGRStrategy >> trade.log 2>&1 &
fi
