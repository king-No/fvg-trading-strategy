#!/usr/bin/env python3
"""
VPS 管理工具集
==============
使用方法:  /path/to/venv/python vps_conn.py <action>

Actions:
  status     - 查看VPS状态(进程/cron/磁盘)
  bt         - 运行FVG回测(优化参数)
  push       - 测试推送交易计划
  logs       - 查看最近推送日志
  <cmd>      - 执行自定义命令
"""
import paramiko, sys, os

HOST = "47.82.99.159"
USER = "root"
PASS = "Lhlzyx1122!"


def ssh():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=10, banner_timeout=3)
    return client


def run(client, cmd):
    i, o, e = client.exec_command(cmd)
    out = o.read().decode()
    err = e.read().decode()
    return out, err


def status():
    client = ssh()
    print("=== RUNNING PROCESSES ===")
    out, _ = run(client, "ps aux | grep -iE 'freqtrade|python.*fvg' | grep -v grep")
    print(out or "  (none)")

    print("\n=== CRONTAB ===")
    out, _ = run(client, "crontab -l 2>/dev/null || echo 'no crontab'")
    print(out)

    print("\n=== DISK ===")
    out, _ = run(client, "df -h /")
    print(out)

    print("\n=== FREQTRADE DB ===")
    out, _ = run(client, "ls -la /root/freqtrade/tradesv3.sqlite 2>/dev/null")
    print(out or "  (no db)")

    client.close()


def backtest():
    """用优化参数运行回测"""
    client = ssh()

    # 备份 + 改参数
    run(client, "cp /root/fvg/fvg_backtest_v6.py /root/fvg/.bt_bak")
    sed_cmds = [
        "s/^FVG_WINDOW = .*/FVG_WINDOW = 36/",
        "s/^FVG_RATIO = .*/FVG_RATIO = 1.1/",
        "s/^RSI_OB = .*/RSI_OB = 73/",
        "s/^RSI_OS = .*/RSI_OS = 35/",
        "s/^SL_MULT = .*/SL_MULT = 1.9/",
        "s/^TP_MULT = .*/TP_MULT = 5.1/",
    ]
    for s in sed_cmds:
        run(client, f"sed -i '{s}' /root/fvg/fvg_backtest_v6.py")

    print("Running backtest with optimized params...\n")
    out, err = run(client, "cd /root/fvg && ./venv/bin/python fvg_backtest_v6.py 2>&1")
    print(out)

    # 恢复
    run(client, "mv /root/fvg/.bt_bak /root/fvg/fvg_backtest_v6.py")
    client.close()


def push_test():
    """测试推送交易计划(到微信)"""
    client = ssh()
    print("Testing push_trading_plan.py...\n")
    out, err = run(client, "cd /root/fvg && ./venv/bin/python push_trading_plan.py 2>&1")
    print(out)
    if err:
        print("STDERR:", err[:500])
    client.close()


def logs():
    """查看最近推送日志"""
    client = ssh()
    print("=== PUSH CRON LOG (last 30 lines) ===")
    out, _ = run(client, "tail -30 /root/fvg/push_cron.log 2>/dev/null || echo 'no log'")
    print(out)
    print("\n=== WATCH CRON LOG (last 10 lines) ===")
    out, _ = run(client, "tail -10 /root/fvg/watch_cron.log 2>/dev/null || echo 'no log'")
    print(out)
    client.close()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"

    actions = {
        "status": status,
        "bt": backtest,
        "push": push_test,
        "logs": logs,
    }

    if action in actions:
        actions[action]()
    else:
        # Run custom command
        client = ssh()
        out, err = run(client, " ".join(sys.argv[1:]))
        print(out)
        if err:
            print("STDERR:", err)
        client.close()
