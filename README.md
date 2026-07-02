# FVG Trading Strategy — v9.4

FVG + RSI + 移动止盈量化交易策略，基于 **ICT/SMC**（Smart Money Concepts）概念，用于 BTC/USDT 期货交易。

## 回测表现 (v9.4)

| 指标 | 数值 |
|------|------|
| 区间 | 约 125 天 (3000根1h K线) |
| 杠杆 | 5x (30%仓位 = 1.5x有效) |
| 交易次数 | 103 ~ 110 |
| 胜率 | 53.6% ~ 57.3% |
| 利润因子 | 1.51 ~ 1.65 |
| 总收益率 | **+57.74% ~ +75.63%** |
| 最大回撤 | **-7.42% ~ -7.76%** |
| 卡玛比率 | **7.44 ~ 10.19** |

## 核心逻辑

### 入场条件

1. **FVG 偏度** — 窗口期内多头/空头 FVG 数量比值 > 1.1
2. **4H 趋势确认** — BOS/CHoCH + FVG 方向共振过滤
3. **RSI 过滤** — 多头 RSI < 73，空头 RSI > 35
4. **ADX 趋势强度** — ADX ≥ 20，避免震荡市场
5. **ATR 收缩过滤** — ATR 收缩超过 20% 时不交易

### 出场条件

- **移动止盈**: 价格走到 2.0x ATR 激活 → 从最高价回撤 0.5x ATR 止盈
- **止损**: ATR × 2.3（动态）
- **反转**: 出现相反信号时提前出场
- **硬止损**: -10%（兜底）

### 参数

| 参数 | 值 |
|------|------|
| FVG_WINDOW | 36 |
| FVG_RATIO | 1.1 |
| RSI_OB | 73 |
| RSI_OS | 35 |
| SL_MULT | **2.3** |
| TP | **移动止盈 0.5x ATR (2.0x激活)** |
| ADX 阈值 | 20 |
| 杠杆 | **5x** |
| 仓位 | **30%** |

## 优化历程

| 版本 | 改进 | 收益 | 回撤 | 卡玛 |
|------|------|------|------|------|
| v6 | 基线 | +19.89% | -9.07% | 2.19 |
| v7.5 | ADX≥20 + ATR收缩 + 4h共振 | +33.64% | -5.96% | 5.64 |
| **v9.4** | **移动止盈 + 5x + 2.3x SL** | **+57.74%** | **-7.76%** | **7.44** |

### v9.4 关键改进

1. **移动止盈代替固定TP** — 价格从最高点回撤 0.5x ATR 时止盈，上涨趋势中能吃到更多利润
2. **SL从1.9x放宽到2.3x** — 减少被波动扫损的次数
3. **杠杆从3x提升到5x** — 30%仓位管理，有效杠杆1.5x
4. **不依赖固定止盈位** — 纯ATR动态出场，适应市场波动

## 文件说明

| 文件 | 说明 |
|------|------|
| `FVGStrategy_v94.py` | Freqtrade 策略文件（v9.4 最终版） |
| `backtest/fvg_sl_scan_v94.py` | SL倍数参数扫描回测 |
| `backtest/fvg_activate_scan.py` | 移动止盈激活倍数扫描 |
| `vps-tools/trade_dashboard.py` | 交易看板 WebUI |
| `vps-tools/vps_manager.py` | VPS 状态管理 |
| `push_trading_plan.py` | 微信推送脚本 |

## 使用方法

### 独立回测

```bash
pip install requests pandas numpy smartmoneyconcepts pandas-ta
python backtest/fvg_backtest_v7_5.py
```

### Freqtrade 部署

```bash
cp freqtrade/FVGStrategy_v94.py ~/freqtrade/user_data/strategies/
freqtrade trade --strategy FVGStrategy
```

## 技术栈

- Python 3.11+
- [smartmoneyconcepts](https://github.com/joshyattridge/smart-money-concepts) — FVG/OB/ICT 指标
- [pandas-ta](https://github.com/twopirllc/pandas-ta) — 技术指标
- [CCXT](https://github.com/ccxt/ccxt) — 交易所 API
- [Freqtrade](https://github.com/freqtrade/freqtrade) — 交易框架
- OKX 模拟盘/实盘

## 免责声明

**本策略仅供参考和学习，不构成投资建议。** 加密货币交易存在高风险，使用前请充分测试并做好风控。
