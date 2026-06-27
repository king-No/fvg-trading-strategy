# FVG Trading Strategy

FVG + RSI 多周期量化交易策略，基于 **ICT/SMC**（Smart Money Concepts）概念，用于 BTC/USDT 期货交易。

## 回测表现 (v7.5)

| 指标 | 数值 |
|------|------|
| 区间 | 2026-02-23 ~ 2026-06-27 (124天) |
| 交易次数 | 72 |
| 胜率 | 37.5% |
| 盈亏比 | 2.54 |
| 利润因子 | 1.52 |
| 总收益率 | **+33.64%** |
| 最大回撤 | **-5.96%** |
| 卡玛比率 | **5.64** |

年化收益约 ~100%（基于4个月数据推算）。

## 核心逻辑

### 入场条件

1. **FVG 偏度** — 窗口期内多头/空头 FVG 数量比值 > 1.1
2. **4H 趋势确认** — 4H FVG 方向与信号方向一致（共振过滤）
3. **RSI 过滤** — 多头 RSI < 73，空头 RSI > 35
4. **ADX 趋势强度** — ADX ≥ 20，避免震荡市场
5. **ATR 收缩过滤** — ATR 收缩超过 20% 时不交易

### 出场条件

- **止盈**: ATR × 5.1（动态）
- **止损**: ATR × 1.9（动态）
- **反转**: 出现相反信号时提前出场

### 参数

| 参数 | 值 |
|------|------|
| FVG_WINDOW | 36 |
| FVG_RATIO | 1.1 |
| RSI_OB | 73 |
| RSI_OS | 35 |
| SL_MULT | 1.9 |
| TP_MULT | 5.1 |
| ADX 阈值 | 20 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `FVGStrategy.py` | Freqtrade 策略文件（可直接部署） |
| `backtest/fvg_backtest_v7_5.py` | 独立回测脚本（无需 Freqtrade） |

## 使用方法

### 独立回测

```bash
pip install requests pandas numpy smartmoneyconcepts pandas-ta
python backtest/fvg_backtest_v7_5.py
```

### Freqtrade 部署

```bash
cp FVGStrategy.py ~/freqtrade/user_data/strategies/
freqtrade trade --strategy FVGStrategy
```

## 优化历程

| 版本 | 改进 | 收益 | 回撤 | 卡玛 |
|------|------|------|------|------|
| v6 | 基线 | +19.89% | -9.07% | 2.19 |
| v7.1 | 结构止损 | +13.61% | -17.29% | 0.79 |
| v7.2 | 参数微调 | +17.45% | -12.82% | 1.36 |
| v7.3 | +FVG共振+ATR收缩 | +31.44% | -7.85% | 4.01 |
| v7.4 | +ADX对比 | +32.75% | -5.96% | 5.49 |
| **v7.5** | **+ADX≥20最优** | **+33.64%** | **-5.96%** | **5.64** |

## 技术栈

- Python 3.11+
- [smartmoneyconcepts](https://github.com/joshyattridge/smart-money-concepts) — FVG/OB/ICT 指标
- [pandas-ta](https://github.com/twopirllc/pandas-ta) — 技术指标
- [CCXT](https://github.com/ccxt/ccxt) — 交易所 API
- [Freqtrade](https://github.com/freqtrade/freqtrade) — 交易框架

## 免责声明

**本策略仅供参考和学习，不构成投资建议。** 加密货币交易存在高风险，使用前请充分测试并做好风控。
