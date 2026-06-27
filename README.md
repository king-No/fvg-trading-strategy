# Hermes Agent 工作目录

## 结构说明

```
hermes_agent/
├── archive/          # 旧版/失败版回测脚本（历史存档）
├── backtest/         # 当前回测脚本
│   └── fvg_backtest_v7_5.py   ← 最终优化版 (ADX≥20, +33.64%)
├── freqtrade/        # Freqtrade 策略参考
├── vps-tools/        # VPS 管理工具
│   ├── vps_manager.py     # 多合一管理（status/bt/push/logs）
│   ├── vps_status.py      # 快速状态查看
│   └── FVGStrategy_v75.py # 已部署到模拟盘的 v7.5 策略
├── push_trading_plan.py   # 微信推送脚本（本地备份）
└── README.md
```

## FVG 策略版本

| 版本 | 结果 |
|------|------|
| v6 (基线) | +19.89%, DD -9.07%, 卡玛 2.19 |
| v7.5 (最终) | **+33.64%, DD -5.96%, 卡玛 5.64** |

v7.5 关键改进: 4h FVG 共振 + ATR 收缩过滤 + ADX≥20
