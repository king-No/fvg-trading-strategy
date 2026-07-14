# LGR Trading Strategy — Handoff 文档

> 编写于 2026-07-11 · 交接给下一会话

---

## 一、我们在做什么

开发并实盘验证 **SMC/ICT 流动性掠夺反转 (Liquidity Grab Reversal)** 量化交易策略，用于加密货币合约交易。

### 现状概要

| 项目 | 状态 |
|:----|:----|
| **策略** | LGR v1.0 — Sweep+FVG+ADX 入场, ATR动态出场 |
| **Freqtrade** | ✅ 运行中, PID 78507, OKX 模拟盘 |
| **品种** | BTC/USDT + ETH/USDT 双品种 |
| **看板** | ✅ http://47.82.99.159:8899 (LGR 交易看板) |
| **GitHub** | https://github.com/king-No/fvg-trading-strategy.git |
| **VPS** | 香港阿里云, 47.82.99.159, root/Lhlzyx1122! |

---

## 二、已完成的任务

### 策略开发 (SMC 独立引擎)

经过 **6 轮迭代** (v1.0 → v2.4) 构建了 LGR 引擎，对比测试排除了一系列无效方向：

- ❌ **SMC 三层入场** (CHOCH+Sweep+FVG) — 信号太少(25笔/3月), 不适合15m BTC
- ❌ **结构破位反转出场** — 滞后, 收益从+180%跌到+73%
- ❌ **5m 周期** — 信号虽多但收益减半(+9% vs +29%)
- ❌ **5m反转出场** — 太吵, 频繁切单
- ❌ **完全去掉反转出场** — 收益从+176%降到+97%

### 多品种验证

| 品种 | 交易 | 胜率 | PF | 收益 | 卡玛 |
|:----|:---:|:---:|:-:|:---:|:---:|
| BTC | 96 | 60.4% | 2.02 | +29.3% | 7.26 |
| ETH | 29 | 62.1% | 1.63 | +24.0% | 2.02 |
| SOL | 4 | — | — | — | 信号太少放弃 |

结论: **BTC+ETH 双品种最优**, 日均 ~4 笔, 月 ~120 笔。

### 参数优化扫描

执行了多轮参数扫描, 最终参数:

| 参数 | 值 | 说明 |
|:----|:---:|:------|
| `swing_window` | 3 | 摆动检测窗口 |
| `adx_threshold` | 20 | ADX趋势过滤 |
| `fvg_lookback` | 5 | FVG确认窗口(前后各5根) |
| `sl_mult` | **1.5x ATR** | 固定止损倍数 |
| `tp_activate_mult` | **1.5x ATR** | 移动止盈激活倍数 |
| `tp_trail_mult` | **0.2x ATR** | 从最高价回撤锁利 |
| `leverage` | 5x | 杠杆 |
| `stake` | 30% | 仓位比例 |
| 反转限制 | 前8根K线(2h) | 持仓2小时内允许反转退出 |

回测结果 (BTC, 3个月, 8700根15m K线):

| 指标 | 值 |
|:----|:---:|
| 交易 | **295笔** |
| 胜率 | **65.1%** |
| PF | **2.61** |
| 总收益 | **+168.0%** |
| 最大回撤 | **-4.0%** |
| 卡玛 | **41.57** |

### VPS 部署

- Freqtrade 策略: `LGRStrategy.py` → `/root/freqtrade/user_data/strategies/`
- 看板: `trade_dashboard.py` → `/root/fvg/trade_dashboard.py` (端口8899)
- 独立引擎: `smc_lgr_v24.py` → `/root/fvg/smc_lgr_v24.py` 
- 看门狗: `watchdog.sh` → `/root/fvg/watchdog.sh` (每5分钟检查)

### GitHub

- 仓库: `king-No/fvg-trading-strategy`
- 最新 commit: `68fd571` — LGR v1.0 最终参数
- 本地路径: `D:\liuhongliang\桌面\hermes_agent\`

---

## 三、当前状态

### VPS 运行中

```
Freqtrade:   LGRStrategy, PID 78507, RUNNING
品种:        BTC/USDT:USDT + ETH/USDT:USDT
看板:        http://47.82.99.159:8899 (30s自动刷新)
DB:          1笔已平仓(#1 BTC多 +2.32%), 0持仓

VPS SSH:     root@47.82.99.159 / pw: Lhlzyx1122!
```

### 模拟盘交易记录

| # | 品种 | 方向 | 杠杆 | 盈亏 | 出场原因 |
|:-:|:---:|:---:|:---:|:---:|:--------|
| 1 | BTC | 多 | 5x | **+2.32%** | 移动止盈(TP) |

### 未完成的待办

- [ ] **收集足够样本** — 目标 100~200 笔交易 (预计1~2个月)
- [ ] **切换实盘** — 替换 OKX API Key + 关闭 sandboxMode
- [ ] **GitHub push 失败重试** — 如网络不通需重推 `git push origin main`

---

## 四、关键文件索引

| 本地路径 | 说明 |
|:---------|:-----|
| `hermes_agent/freqtrade/LGRStrategy.py` | **Freqtrade 策略 (生产版)** |
| `hermes_agent/backtest/smc_lgr_v24.py` | **独立回测引擎** |
| `hermes_agent/backtest/smc_lgr_v24_report.md` | 开发报告 (含30+轮失败尝试) |
| `hermes_agent/README.md` | GitHub README |

| VPS路径 | 说明 |
|:--------|:-----|
| `/root/freqtrade/user_data/strategies/LGRStrategy.py` | 策略文件 |
| `/root/freqtrade/user_data/config.json` | Freqtrade 配置 |
| `/root/fvg/trade_dashboard.py` | 看板 (端口8899) |
| `/root/fvg/smc_lgr_v24.py` | 独立引擎 (研究用) |
| `/root/fvg/watchdog.sh` | 看门狗 |

---

## 五、踩过的坑 — 绝对不要再踩

### 1. SSH 频繁掉线 / 被攻击

**现象：** SSH 连不上但看板(8899)和 Freqtrade 正常。
**原因：** VPS 被 SSH 暴力破解攻击, fail2ban 封禁 IP。
**解决：** 改用看板端口(8899)查看状态, 等攻击过去。看板没挂=系统正常。
**预防：** 已经配置 fail2ban + watchdog, 不需要额外操作。

### 2. Freqtrade 重启后配置静默丢失

**现象：** 重启后策略跑着但杠杆变成1x、仓位固定$20。
**原因：** `FVGStrategy.json` 的优先级高于策略类属性。同名 JSON 文件会静默覆盖策略参数。
**解决：** `mv FVGStrategy.json{,.bak}` 禁用 JSON 配置。
**预防：** 每次部署新策略时确认 JSON 文件已被重命名。

### 3. 持久化字典内存泄漏

**现象：** `custom_exit()` 中的 `_best_prices`, `_tp_active`, `_entry_atr` 字典随 trade.id 增长。
**影响：** 极小 (< 1MB / 千笔交易), Freqtrade 重启后清空。
**结论：** 不需要处理, 但要知道这个机制。

### 4. Parquet vs Feather 文件格式

**现象：** 读取数据时提示 `pyarrow` 或 `fastparquet` 缺失。
**原因：** Freqtrade 下载的数据是 `.feather` 格式, 不是 `.parquet`。
**解决：** 使用 `pd.read_feather()` 而不是 `pd.read_parquet()`。

### 5. SSH 连接中内嵌 Python 引号转义

**现象：** 在 paramiko `exec_command` 中嵌套 Python 字符串时, 引号嵌套导致 SyntaxError。
**解决：** 将脚本写入 `.py` 文件 → SFTP 上传 → 在 VPS 上执行。不要用 `python -c` 传复杂脚本。

### 6. 看板修改后 SyntaxError 导致启动失败

**现象：** 修改看板代码后服务起不来, curl 超时。
**原因：** Python f-string 替换时插入了字面 `\n` 而不是换行符。
**预防：** 修改看板后用 `python -c "import py_compile; py_compile.compile('trade_dashboard.py', doraise=True)"` 验证语法。

### 7. SMC 库的 CHOCH 在15m上过于稀少

**现象：** CHOCH+Sweep+FVG 三层条件 → 3个月仅25个信号。
**原因：** `smartmoneyconcepts` 库的 CHOCH/BOS 检测设计用于大周期(4h/日线)。
**结论：** 15m 上用 Sweep+FVG+ADX 就够了, 不需要 CHOCH。

### 8. 反转出场的数据验证

**现象：** 用户感觉反转出场"浮盈被打光了", 想去掉。
**数据：** 去掉反转出场 → 收益从+176%降到+97%。反转出场实际上是有利的(提前止损)。
**结论：** 用户感觉 ≠ 数学事实。遇到这种情况要用数据说服, 不要盲目改。

---

## 六、下一步计划

### 短期 (当前会话)

1. 继续跑模拟盘, 积累交易样本
2. 每30笔检查一次胜率/PF/回撤
3. 如BTC和ETH表现差异大, 考虑调整权重

### 中期 (100笔样本后)

1. 统计实盘数据 vs 回测数据偏差
2. 如果胜率 > 55%, PF > 1.5 → 准备实盘
3. 准备实盘参数: 缩小仓位(15%~20%), 降低杠杆(3x)

### 实盘切换

```python
# config.json 需要改:
"dry_run": false,                             # 关闭模拟
"sandboxMode": false,                          # 关闭沙盒
# 替换为真实 API Key (OKX mainnet)
"key": "your-real-api-key",
"secret": "your-real-api-secret",
"password": "your-real-api-passphrase",
```

---

## 七、快速命令参考

### 日常操作

```bash
# 查看状态
curl -s http://47.82.99.159:8899 | head -5

# SSH 连接
ssh root@47.82.99.159

# 重启 Freqtrade
pkill -9 -f "freqtrade trade"
cd /root/freqtrade && nohup .venv/bin/freqtrade trade --strategy LGRStrategy > trade.log 2>&1 &

# 重启看板
pkill -f trade_dashboard
cd /root/fvg && nohup ./venv/bin/python trade_dashboard.py > /dev/null 2>&1 &

# 跑回测 (3个月数据)
cd /root/fvg && ./venv/bin/python smc_lgr_v24.py --months 3

# 查看最近持仓
cd /root/freqtrade && .venv/bin/python3.12 -c "
import sqlite3;db=sqlite3.connect('tradesv3.sqlite')
for r in db.execute('SELECT id,pair,is_open,close_profit,exit_reason FROM trades ORDER BY id DESC LIMIT 5'):
    print(f'#{r[0]} {r[1]} open={r[2]} profit={r[3]} reason={r[4]}')
"
```

### 部署新版本

```bash
# 1. 上传策略
scp LGRStrategy.py root@47.82.99.159:/root/freqtrade/user_data/strategies/

# 2. 禁用 JSON 覆盖 (关键!)
ssh root@47.82.99.159 "mv /root/freqtrade/user_data/strategies/FVGStrategy.json{,.bak} 2>/dev/null"

# 3. 重启
ssh root@47.82.99.159 "pkill -9 -f 'freqtrade trade'; sleep 3; cd /root/freqtrade && nohup .venv/bin/freqtrade trade --strategy LGRStrategy > trade.log 2>&1 &"

# 4. 审计
ssh root@47.82.99.159 "grep -c 'def leverage\|def custom_stoploss\|def custom_exit\|tp_trail' /root/freqtrade/user_data/strategies/LGRStrategy.py"
```

---

*交接完毕。祝好运！*
