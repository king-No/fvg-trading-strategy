#!/bin/bash
# VPS 自我监控 — 每5分钟检查，挂了自动恢复
# 放 crontab 每5分钟执行一次

# 检查看板
if ! curl -s -o /dev/null http://127.0.0.1:8899; then
    echo "[$(date)] 看板挂了, 重启..." >> /root/fvg/watchdog.log
    cd /root/fvg && nohup ./venv/bin/python trade_dashboard.py > /dev/null 2>&1 &
fi

# 检查Freqtrade
if ! ps aux | grep -q "[f]reqtrade trade"; then
    echo "[$(date)] Freqtrade挂了, 重启..." >> /root/fvg/watchdog.log
    cd /root/freqtrade && nohup .venv/bin/freqtrade trade --strategy FVGStrategy >> trade.log 2>&1 &
fi
