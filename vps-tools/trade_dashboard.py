#!/usr/bin/env python3
"""FVG 交易看板 — BTC"""
import sqlite3, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse

DB_PATH = "/root/freqtrade/tradesv3.sqlite"
PORT = 8899

def bj_time(dt=None):
    """UTC转北京时间 UTC+8"""
    if dt is None:
        return datetime.utcnow() + timedelta(hours=8)
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    return dt + timedelta(hours=8)

def fetch_live():
    try:
        import ccxt
        c = json.load(open("/root/freqtrade/user_data/config.json"))
        ex = ccxt.okx({"apiKey":c["exchange"]["key"],"secret":c["exchange"]["secret"],"password":c["exchange"]["password"]})
        ex.set_sandbox_mode(True)
        btc = ex.fetch_ticker("BTC/USDT:USDT")["last"]
        pos = ex.fetch_positions()
        upnl = sum(float(p.get("unrealizedPnl",0)) for p in pos if float(p.get("contracts",0)) > 0)
        return btc, upnl
    except:
        return None, None

def get_db_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM trades"); total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM trades WHERE is_open=1"); open_n = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM trades WHERE is_open=0"); closed_n = cur.fetchone()["c"]
    cur.execute("SELECT open_rate,close_rate,close_profit,is_short,stake_amount FROM trades WHERE is_open=0")
    wins = 0; realized = 0.0
    for r in cur.fetchall():
        p = r["close_profit"]; s = r["stake_amount"] or 0; u = p * s if p is not None else None
        if u is None and r["close_rate"] and r["open_rate"]:
            raw = (r["close_rate"]-r["open_rate"])/r["open_rate"]; pct = -raw if r["is_short"] else raw; u = s * pct
        if u is not None: realized += u; wins += 1 if u > 0 else 0
    wr = wins/closed_n*100 if closed_n else 0
    conn.close()
    return total, open_n, wr, realized

STYLES = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px;max-width:1100px;margin:0 auto}
h1{color:#58a6ff;margin-bottom:4px;font-size:22px}
.sub{color:#8b949e;font-size:12px;margin-bottom:16px}
.price-bar{display:flex;justify-content:space-between;align-items:center;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 20px;margin-bottom:16px}
.price-bar .label{font-size:11px;color:#8b949e}
.price-bar .btc{font-size:26px;font-weight:700;color:#f7931a}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:16px}
.stat-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px}
.stat-card .label{font-size:10px;color:#8b949e;text-transform:uppercase}
.stat-card .value{font-size:18px;font-weight:600;margin-top:2px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#161b22;padding:8px 10px;text-align:left;color:#8b949e;font-weight:500;border-bottom:1px solid #30363d;white-space:nowrap}
td{padding:8px 10px;border-bottom:1px solid #21262d;white-space:nowrap}
tr:hover{background:#161b22}
.green{color:#3fb950}.red{color:#f85149}.short{color:#f85149}
.badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:500}
.badge-tp{background:#1a3a1a;color:#3fb950}.badge-sl{background:#3a1a1a;color:#f85149}.badge-rev{background:#1a1a3a;color:#58a6ff}.badge-open{background:#3a2a1a;color:#d29922}
.updated{color:#484f58;font-size:10px;margin-top:10px;text-align:right}
</style>"""

JS = """<script>
let lb=0;
function ul(){
  fetch('/api/live').then(r=>r.json()).then(d=>{
    if(d.btc){const e=document.getElementById('bp');
      if(d.btc>lb)e.style.color='#3fb950';else if(d.btc<lb)e.style.color='#f85149';lb=d.btc;
      e.innerText='$'+d.btc.toLocaleString(undefined,{minimumFractionDigits:2});setTimeout(()=>{e.style.color='#f7931a'},500)}
    const u=document.getElementById('upnl');if(u&&d.upnl!==undefined){const v=d.upnl;u.innerText=(v>=0?'$+':'$')+Math.abs(v).toFixed(2);u.style.color=v>=0?'#3fb950':'#f85149'}
    document.getElementById('ls').innerText=' LIVE '+d.ts;
  }).catch(()=>{document.getElementById('ls').innerText=' OFFLINE'});
}
setInterval(ul,5000);setInterval(()=>{location.reload()},60000);ul();
</script>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/live":
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            btc, upnl = fetch_live()
            _,_,_,realized = get_db_stats()
            self.wfile.write(json.dumps({"btc":btc,"unrealized_pnl":upnl,"realized_pnl":realized,"ts":bj_time().strftime('%H:%M:%S')}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        btc, upnl = fetch_live()
        total, open_n, wr, realized = get_db_stats()

        btc_str = f"${btc:,.2f}" if btc else "—"
        upnl_str = f"${upnl:+,.2f}" if upnl and abs(upnl)>=0.01 else "$0.00"
        upnl_c = '#3fb950' if upnl and upnl >= 0 else '#f85149'
        rlzd_str = f"${realized:+,.2f}" if abs(realized)>=0.01 else "$0.00"
        rlzd_c = '#3fb950' if realized >= 0 else '#f85149'

        parts = [f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FVG 交易看板</title>{STYLES}</head><body>
<h1> FVG 交易看板</h1>
<div class="sub">BTC/USDT · OKX 模拟盘 · FVG v9.4 · 5x杠杆(1.5x有效)</div>
<div class="price-bar">
  <div><span class="label">BTC/USDT</span><div class="btc" id="bp">{btc_str}</div></div>
  <div><span class="label">浮盈</span><div class="value" id="upnl" style="font-size:20px;color:{upnl_c}">{upnl_str}</div></div>
  <div><span class="label">已实现</span><div class="value" style="font-size:20px;color:{rlzd_c}">{rlzd_str}</div></div>
  <div><span class="label" id="ls" style="font-size:12px;color:#3fb950"> LIVE</span></div>
</div>
<div class="stats">
  <div class="stat-card"><div class="label">交易</div><div class="value">{total}</div></div>
  <div class="stat-card"><div class="label">持仓</div><div class="value">{open_n}</div></div>
  <div class="stat-card"><div class="label">胜率</div><div class="value">{wr:.1f}%</div></div>
  <div class="stat-card"><div class="label">策略</div><div class="value" style="font-size:13px">FVG v7.5</div></div>
</div>"""]

        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id,pair,open_date,close_date,open_rate,close_rate,close_profit,is_open,is_short,exit_reason,stake_amount,amount,leverage FROM trades ORDER BY id DESC LIMIT 50")
            rows = cur.fetchall()
            conn.close()
            if rows:
                parts.append("<table><thead><tr><th>#</th><th>方向</th><th>杠杆</th><th>开仓</th><th>开仓价</th><th>平仓</th><th>平仓价</th><th>盈亏</th><th>状态</th></tr></thead><tbody>")
                for r in rows:
                    io = r["is_open"]; sh = r["is_short"]; op = r["open_rate"]; cl = r["close_rate"]
                    pf = r["close_profit"]; lv = r["leverage"] or 1; sk = r["stake_amount"] or 0
                    side = "空" if sh else "多"; sc = "short" if sh else ""
                    pp = pf; pu = pf * sk if pf is not None else None
                    if pp is None and cl and op: r2 = (cl-op)/op; pp = -r2 if sh else r2; pu = sk * pp
                    if io:
                        badge = '<span class="badge badge-open">持仓</span>'; ps = "-"
                    else:
                        if r["exit_reason"] in ("stop_loss","stoploss") or (pp and pp < 0):
                            badge = '<span class="badge badge-sl">SL</span>'
                        elif r["exit_reason"] in ("take_profit","takeprofit") or (pp and pp > 0):
                            badge = '<span class="badge badge-tp">TP</span>'
                        else:
                            badge = '<span class="badge badge-rev">反转</span>'
                        ic = "🟢" if pp and pp > 0 else "🔴"
                        ps = f"{ic} {pp*100:+.2f}% ({f'${pu:+,.2f}' if pu and abs(pu)>=0.01 else '$0.00'})" if pp else "-"
                    parts.append(f"<tr><td>#{r['id']}</td><td class='{sc}'>{side}</td><td>{lv}x</td><td>{bj_time(r['open_date']).strftime('%m-%d %H:%M') if r['open_date'] else '-'}</td><td>${op:,.2f}</td><td>{bj_time(r['close_date']).strftime('%m-%d %H:%M') if r['close_date'] else '-'}</td><td>{f'${cl:,.2f}' if cl else '-'}</td><td class='{'green' if pp and pp>0 else 'red'}'>{ps}</td><td>{badge}</td></tr>")
                parts.append("</tbody></table>")

        parts.append(f'<div class="updated">更新于 {bj_time().strftime("%m-%d %H:%M:%S")}</div>' + JS + '</body></html>')
        self.wfile.write("".join(parts).encode())

    def log_message(self, *a): pass

if __name__ == "__main__":
    print(f"看板: http://0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
