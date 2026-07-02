#!/usr/bin/env python3
"""
FVG 交易计划推送 — ServerChan
每6小时运行一次，推送开仓位/止损/目标价到微信
"""

import requests, json, time
from datetime import datetime
import pandas as pd
import numpy as np
from smartmoneyconcepts import smc
import pandas_ta as ta

SENDKEY = "SCT371405TGb3weMeess0nvZ3lEeV9RY4R"
SYMBOL = "BTC/USDT"

def fetch_ohlcv(tf, limit=300):
    url = f"https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&limit={limit}&bar={tf}"
    try:
        resp = requests.get(url, timeout=10).json()
        if resp.get("code") != "0":
            return None
        candles = resp.get("data", [])
        rows = []
        for c in candles:
            rows.append([int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
        df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df
    except:
        return None

def get_trading_plan():
    df1 = fetch_ohlcv("1H", 300)
    df4 = fetch_ohlcv("4H", 150)
    if df1 is None or df4 is None:
        return None

    # 4h 趋势
    fvg4 = smc.fvg(df4)
    df4["FVG"] = fvg4["FVG"]
    sw4 = smc.swing_highs_lows(df4, 15)
    bos4 = smc.bos_choch(df4, sw4)
    df4["net_fvg"] = ((fvg4["FVG"] == 1).rolling(8).sum() - (fvg4["FVG"] == -1).rolling(8).sum()).fillna(0)
    df4["trend"] = 0
    df4.loc[(df4["net_fvg"] >= 2) | (bos4["CHOCH"] == 1) | (bos4["BOS"] == 1), "trend"] = 1
    df4.loc[(df4["net_fvg"] <= -2) | (bos4["CHOCH"] == -1) | (bos4["BOS"] == -1), "trend"] = -1
    trend_4h = int(df4["trend"].iloc[-1])

    # 1h 信号
    fvg1 = smc.fvg(df1)
    sw1 = smc.swing_highs_lows(df1, 20)
    bos1 = smc.bos_choch(df1, sw1)
    df1["FVG"] = fvg1["FVG"]
    df1["RSI"] = ta.rsi(df1["close"], 14)
    atr = ta.atr(df1["high"], df1["low"], df1["close"], 14)
    df1["ATR"] = atr

    window = 36
    if len(df1) < window:
        return None
    bulls = int((df1["FVG"].iloc[-window:].fillna(0) == 1).sum())
    bears = int((df1["FVG"].iloc[-window:].fillna(0) == -1).sum())

    price = float(df1["close"].iloc[-1])
    rsi = float(df1["RSI"].iloc[-1]) if not pd.isna(df1["RSI"].iloc[-1]) else 50
    atr_val = float(df1["ATR"].iloc[-1]) if not pd.isna(df1["ATR"].iloc[-1]) else price * 0.008

    # 方向判断（使用优化参数）
    fvg_bull = bulls > bears * 1.1
    fvg_bear = bears > bulls * 1.1
    rsi_ok = 35 < rsi < 73

    if fvg_bull and trend_4h != -1 and rsi_ok:
        direction = "LONG"
    elif fvg_bear and trend_4h != 1 and rsi_ok:
        direction = "SHORT"
    else:
        direction = "WAIT"

    sl_mult = 1.9
    tp_mult = 5.1
    sl_dist = atr_val * sl_mult
    tp_dist = atr_val * tp_mult

    if direction == "LONG":
        entry = f"${price:,.0f}"
        sl = f"${price - sl_dist:,.0f}"
        tp = f"${price + tp_dist:,.0f}"
    elif direction == "SHORT":
        entry = f"${price:,.0f}"
        sl = f"${price + sl_dist:,.0f}"
        tp = f"${price - tp_dist:,.0f}"
    else:
        entry = f"${price:,.0f}"
        sl = "--"
        tp = "--"

    trend_text = {1: "多头", -1: "空头", 0: "震荡"}.get(trend_4h, "震荡")

    # 市场情绪
    try:
        fg = json.loads(requests.get("https://api.alternative.me/fng/?limit=1", timeout=5).text)
        fg_val = fg["data"][0]["value"]
        fg_label = fg["data"][0]["value_classification"]
    except:
        fg_val, fg_label = "?", "未知"

    # 构建推送消息
    dir_icon = "BUY" if direction == "LONG" else "SELL" if direction == "SHORT" else "WAIT"
    title = f"FVG {dir_icon} BTC {price:,.0f}"

    lines = []
    lines.append(f"BTC/USDT  ${price:,.0f}")
    lines.append("")
    if direction == "LONG":
        lines.append("操作：做多")
    elif direction == "SHORT":
        lines.append("操作：做空")
    else:
        lines.append("操作：观望")
    lines.append("")
    lines.append(f"入场  {entry}")
    lines.append(f"止损  {sl}")
    lines.append(f"目标  {tp}")
    lines.append("")
    lines.append(f"4H趋势  {trend_text}")
    fvg_4h = int(df4["FVG"].notna().sum())
    dir_1h = "偏多" if bulls > bears else "偏空" if bears > bulls else "均衡"
    lines.append(f"1H信号  {dir_1h}  RSI {rsi:.1f}")
    lines.append(f"FVG  {bulls}B/{bears}S")
    lines.append("")
    lines.append(f"恐惧贪婪  {fg_val}/100 {fg_label}")
    lines.append("")
    lines.append(datetime.now().strftime("%Y-%m-%d %H:%M"))

    desp = "\n".join(lines)
    return title, desp

def push(title, desp):
    url = f"https://sctapi.ftqq.com/{SENDKEY}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": desp}, timeout=15)
        result = resp.json()
        if result.get("code") == 0:
            print("OK:", title)
            return True
        else:
            print("FAIL:", result)
            return False
    except Exception as e:
        print("ERR:", e)
        return False

if __name__ == "__main__":
    print("FVG 交易计划推送...")
    plan = get_trading_plan()
    if plan:
        title, desp = plan
        print("Signal:", title)
        print("Content:", desp)
        push(title, desp)
    else:
        print("Data failed")
