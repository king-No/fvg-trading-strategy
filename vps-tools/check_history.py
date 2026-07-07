import sqlite3
db = sqlite3.connect("/root/freqtrade/tradesv3.sqlite")
db.row_factory = sqlite3.Row
print(f"{'#':>4} {'方向':>4} {'杠杆':>4} {'开仓':>20} {'平仓':>20} {'开仓价':>10} {'平仓价':>10} {'盈亏%':>8} {'盈亏$':>8} {'出场':>18}")
print("-"*120)
for r in db.execute("SELECT id, is_short, leverage, open_date, close_date, open_rate, close_rate, close_profit, stake_amount, exit_reason FROM trades WHERE is_open=0 ORDER BY id"):
    side = "空" if r['is_short'] else "多"
    pf = r['close_profit']
    pct = f"{pf*100:+.2f}%" if pf else "—"
    usd = f"${pf*r['stake_amount']:+.2f}" if pf and r['stake_amount'] else "—"
    close = r['close_date'][:16] if r['close_date'] else "—"
    cr = f"${r['close_rate']:.2f}" if r['close_rate'] else "—"
    print(f"{r['id']:>4} {side:>4} {r['leverage']:>3.0f}x {r['open_date'][:16]:>20} {close:>20} ${r['open_rate']:>8.2f} {cr:>10} {pct:>8} {usd:>8} {r['exit_reason']:>18}")

print()
for r in db.execute("SELECT exit_reason, COUNT(*) as c, SUM(close_profit*stake_amount) as tot FROM trades WHERE is_open=0 GROUP BY exit_reason"):
    print(f"  {r['exit_reason']:20s} {r['c']:>3d}笔  合计 ${r['tot']:+.2f}")

db.close()
