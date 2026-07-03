# LGR Trading Strategy — v1.0

**Liquidity Grab Reversal** — 流动性掠夺反转策略，基于 **ICT/SMC**（Smart Money Concepts）概念，用于加密货币期货交易。

替代之前 30+ 轮迭代的 FVG v9.4 策略。LGR v1.0 在回测中全面超越 v9.4。

## 回测对比 (15m, 31天)

| 指标 | v9.4 ❌ | **LGR v1.0 🏆** |
|------|:-------:|:---------------:|
| 交易次数 | 247 | **95** |
| 胜率 | 43.7% | **74.7%** |
| 利润因子 | 0.84 | **3.21** |
| 总收益率 | -21.26% | **+62.60%** |
| 最大回撤 | -27.5% | **-4.8%** |
| **卡玛比率** | **0.77** | **13.17** |

### 多品种表现

| 品种 | 交易 | 胜率 | PF | 收益 | 回撤 | 卡玛 |
|:----|:---:|:---:|:--:|:---:|:---:|:---:|
| **BTC** | 95 | 74.7% | 3.21 | +62.6% | -4.8% | 13.17 |
| **ETH** | 59 | 72.9% | **4.11** | **+113.8%** | -7.9% | **14.40** |
| **SOL** | 63 | 69.8% | 1.89 | +58.8% | -18.8% | 3.14 |

## 核心逻辑

### 入场条件 (LGR)

1. **摆动点检测** — Swing Window=3，检测摆动高/低点
2. **流动性掠夺** — 价格假突破摆动点后收回 (sweep)
3. **FVG 确认** — 同方向 FVG 在前后 5 根 K 线内存在
4. **ADX 过滤** — ADX ≥ 20，只在趋势市场交易

### 出场条件

- **移动止盈**: 价格走到 2.0x ATR 激活 → 从最高价回撤 0.5x ATR 止盈
- **止损**: ATR × 2.3（动态，存储入场 ATR）
- **反转**: 出现相反信号时提前出场
- **硬止损**: -8%（兜底）

### 参数

| 参数 | 值 |
|------|:--:|
| Swing Window | 3 |
| ADX 阈值 | 20 |
| FVG 确认窗口 | ±5 根 |
| SL / TP 激活 / TP 跟随 | 2.3x / 2.0x / 0.5x ATR |
| 杠杆 | 5x (30%仓位 = 1.5x有效) |

## 优化历程

| 阶段 | 描述 | 结果 | 卡玛 |
|:----|:-----|:----|:---:|
| v6~v9.4 | FVG 偏度策略 (30+轮迭代) | +75.63% / 125天 | 10.19 |
| SMC v1.0~v2.2 | 状态机尝试 (零信号 / 错误) | ❌ 失败 | — |
| **SMC v2.3** | **SwingW=5 + FVG确认** | **+17.33%** | **1.18** |
| **SMC v2.4 / LGR v1.0** | **SwingW=3 + 纯LGR模式** | **+62.60%** | **13.17** |

## 文件说明

| 文件 | 说明 |
|------|------|
| `freqtrade/LGRStrategy.py` | Freqtrade 策略文件 (生产版) |
| `backtest/smc_lgr_v24.py` | 独立回测引擎 (研究用) |
| `backtest/smc_lgr_v24_report.md` | SMC 引擎开发报告 |
| `vps-tools/` | VPS 管理/部署工具 |

## 使用方法

### 独立回测

```bash
pip install requests pandas numpy smartmoneyconcepts pandas-ta

# 15m 回测 (默认)
python backtest/smc_lgr_v24.py

# 1h 回测
python backtest/smc_lgr_v24.py --tf 1h
```

### Freqtrade 部署

```bash
cp freqtrade/LGRStrategy.py ~/freqtrade/user_data/strategies/
freqtrade trade --strategy LGRStrategy
```

## 技术栈

- Python 3.11+
- [smartmoneyconcepts](https://github.com/joshyattridge/smart-money-concepts) — FVG/OB/ICT 指标
- [pandas-ta](https://github.com/twopirllc/pandas-ta) — 技术指标
- [CCXT](https://github.com/ccxt/ccxt) — 交易所 API
- [Freqtrade](https://github.com/freqtrade/freqtrade) — 交易框架
- OKX 模拟盘 → 实盘

## 免责声明

**本策略仅供参考和学习，不构成投资建议。** 加密货币交易存在高风险，使用前请充分测试并做好风控。
