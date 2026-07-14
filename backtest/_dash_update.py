#!/usr/bin/env python3
"""LGR 交易看板 — 优化版"""
import sqlite3, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse

DB_PATH = "/root/freqtrade/tradesv3.sqlite"
PORT = 8899

def bj_time(dt=None):
    if dt is None: return datetime.utcnow() + timedelta(hours=8)
    if isinstance(dt, str):
        try: dt = datetime.fromisoformat(dt)
        except: return dt
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
    except: return None, None

def get_db_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM trades"); total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM trades WHERE is_open=1"); open_n = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM trades WHERE is_open=0"); closed_n = cur.fetchone()["c"]
    cur.execute("SELECT close_profit,stake_amount,close_rate,open_rate,is_short FROM trades WHERE is_open=0")
    wins = losses = 0; realized = 0.0
    for r in cur.fetchall():
        p = r["close_profit"]; s = r["stake_amount"] or 0
        if p is not None:
            u = p * s; realized += u
            if u > 0: wins += 1
            else: losses += 1
        elif r["close_rate"] and r["open_rate"]:
            raw = (r["close_rate"]-r["open_rate"])/r["open_rate"]
            pct = -raw if r["is_short"] else raw; u = s * pct; realized += u
            if u > 0: wins += 1; losses += 0 if losses else 0
    conn.close()
    wr = wins/(wins+losses)*100 if (wins+losses) else 0
    return total, open_n, closed_n, wins, losses, wr, round(realized,2)

STYLES = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;padding:20px;max-width:1100px;margin:0 auto}
h1{color:#58a6ff;margin-bottom:2px;font-size:22px;display:flex;align-items:center;gap:8px}
h1 .tag{font-size:10px;background:#1f2937;color:#8b949e;padding:2px 8px;border-radius:4px;font-weight:400}
.sub{color:#8b949e;font-size:12px;margin-bottom:14px}
.price-bar{display:flex;justify-content:space-between;align-items:center;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 20px;margin-bottom:14px}
.price-bar .label{font-size:11px;color:#8b949e}
.price-bar .btc{font-size:26px;font-weight:700;color:#f7931a}
.price-bar .upnl{font-size:20px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin-bottom:14px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px}
.card .l{font-size:10px;color:#8b949e;text-transform:uppercase;letter-spacing:0.5px}
.card .v{font-size:16px;font-weight:600;margin-top:1px}
.card .v.sm{font-size:12px}
.card .v.xs{font-size:11px;font-weight:400;color:#8b949e}
table{width:100%;border-collapse:collapse;font-size:11px}
th{background:#161b22;padding:6px 8px;text-align:left;color:#8b949e;font-weight:500;border-bottom:1px solid #30363d;white-space:nowrap}
td{padding:6px 8px;border-bottom:1px solid #21262d;white-space:nowrap;font-size:11px}
tr:hover{background:#161b22}
.green{color:#3fb950}.red{color:#f85149}
.badge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:500}
.badge-tp{background:#1a3a1a;color:#3fb950}.badge-sl{background:#3a1a1a;color:#f85149}
.badge-rev{background:#1a1a3a;color:#58a6ff}.badge-open{background:#3a2a1a;color:#d29922}
.updated{color:#484f58;font-size:10px;margin-top:8px;text-align:right}
.section-title{color:#8b949e;font-size:13px;font-weight:500;margin:14px 0 8px;padding-bottom:4px;border-bottom:1px solid #21262d}
</style>"""

JS = """<script>
let lb=0;
function ul(){
  fetch('/api/live').then(r=>r.json()).then(d=>{
    if(d.btc){const e=document.getElementById('bp');
      if(d.btc>lb)e.style.color='#3fb950';else if(d.btc<lb)e.style.color='#f85149';lb=d.btc;
      e.innerText='$'+d.btc.toLocaleString(undefined,{minimumFractionDigits:2});setTimeout(()=>{e.style.color='#f7931a'},500)}
    const u=document.getElementById('upnl');if(u&&d.upnl!==undefined){const v=d.upnl;u.innerText=(v>=0?'$+':'$')+Math.abs(v).toFixed(2);u.style.color=v>=0?'#3fb950':'#f85149'}
    document.getElementById('ls').innerText='LIVE '+d.ts;
  }).catch(()=>{document.getElementById('ls').innerText='OFFLINE'});
}
setInterval(ul,5000);setInterval(()=>{location.reload()},30000);ul();
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
            _,_,_,_,_,_,realized = get_db_stats()
            self.wfile.write(json.dumps({"btc":btc,"upnl":upnl,"realized":realized,"ts":bj_time().strftime('%H:%M:%S')}).encode())
            return

        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        btc, upnl = fetch_live()
        total, open_n, _, wins, losses, wr, realized = get_db_stats()

        btc_str = f"${btc:,.2f}" if btc else "—"
        upnl_str = f"${upnl:+,.2f}" if upnl and abs(upnl)>=0.01 else "$0.00"
        upnl_c = '#3fb950' if upnl and upnl >= 0 else '#f85149'
        rlzd_str = f"${realized:+,.2f}" if abs(realized)>=0.01 else "$0.00"
        rlzd_c = '#3fb950' if realized >= 0 else '#f85149'
        lv_str = "SL1.5x · 5x(1.5x有效)"

        parts = [f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>LGR 交易看板</title>{STYLES}</head><body>
<h1>LGR 交易看板 <span class="tag">{lv_str}</span></h1>
<div class="sub">BTC/USDT · OKX 模拟盘 · LGR v1.0 · {bj_time().strftime('%m-%d %H:%M')} 更新</div>
<div class="price-bar">
  <div><span class="label">BTC/USDT</span><div class="btc" id="bp">{btc_str}</div></div>
  <div><span class="label">浮盈</span><div class="upnl" id="upnl" style="color:{upnl_c}">{upnl_str}</div></div>
  <div><span class="label">已实现</span><div class="upnl" style="color:{rlzd_c}">{rlzd_str}</div></div>
  <div><span class="label" id="ls" style="font-size:11px;color:#3fb950">LIVE</span></div>
</div>
<div class="grid">
  <div class="card"><div class="l">交易</div><div class="v">{total}</div></div>
  <div class="card"><div class="l">持仓</div><div class="v">{open_n}</div></div>
  <div class="card"><div class="l">胜/负</div><div class="v sm">{wins}<span class="green">W</span> / {losses}<span class="red">L</span></div></div>
  <div class="card"><div class="l">胜率</div><div class="v">{wr:.1f}%</div></div>
  <div class="card"><div class="l">累计盈亏</div><div class="v sm" style="color:{rlzd_c}">{rlzd_str}</div></div>
  <div class="card"><div class="l">杠杆</div><div class="v sm">{lv_str}</div></div>
</div>"""]

        # 交易明细
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id,pair,open_date,close_date,open_rate,close_rate,close_profit,is_open,is_short,exit_reason,stake_amount,amount,leverage FROM trades ORDER BY id DESC LIMIT 50")
            rows = cur.fetchall()
            conn.close()
            if rows:
                parts.append('<div class="section-title">📋 交易明细</div><table><thead><tr><th>#</th><th>方向</th><th>杠杆</th><th>开仓</th><th>开仓价</th><th>平仓</th><th>平仓价</th><th>盈亏</th><th>状态</th></tr></thead><tbody>')
                for r in rows:
                    io = r["is_open"]; sh = r["is_short"]; op = r["open_rate"]; cl = r["close_rate"]
                    pf = r["close_profit"]; lv = r["leverage"] or 1; sk = r["stake_amount"] or 0
                    side = "空" if sh else "多"; sc = "red" if sh else "green"
                    pp = pf; pu = pf * sk if pf is not None else None
                    if pp is None and cl and op: r2 = (cl-op)/op; pp = -r2 if sh else r2; pu = sk * pp
                    if io:
                        badge = '<span class="badge badge-open">持仓</span>'; ps = "—"
                    else:
                        rea = r["exit_reason"] or ""
                        if "stoploss" in rea or "stop_loss" in rea or (pp is not None and pp < -0.005):
                            badge = '<span class="badge badge-sl">SL</span>'
                        elif pp is not None and pp > 0.005:
                            badge = '<span class="badge badge-tp">TP</span>'
                        else:
                            badge = '<span class="badge badge-rev">反转</span>'
                        ic = "🟢" if pp and pp > 0 else "🔴"
                        ps = f"{ic} {pp*100:+.2f}% ({pu:+.2f})" if pp is not None else "—"
                    parts.append(f"<tr><td>#{r['id']}</td><td class='{sc}'>{side}</td><td>{lv}x</td><td>{bj_time(r['open_date']).strftime('%m-%d %H:%M') if r['open_date'] else '-'}</td><td>${op:,.2f}</td><td>{bj_time(r['close_date']).strftime('%m-%d %H:%M') if r['close_date'] else '-'}</td><td>{'$'+f'{cl:,.2f}' if cl else '-'}</td><td class='{'green' if pp and pp>0 else 'red'}'>{ps}</td><td>{badge}</td></tr>")
                parts.append("</tbody></table>")

        parts.append(f'<div class="updated">🔄 30s自动刷新 · 最后更新 {bj_time().strftime("%m-%d %H:%M:%S")}</div>' + JS + '</body></html>')
        self.wfile.write("".join(parts).encode())

    def log_message(self, *a): pass

if __name__ == "__main__":
    print(f"看板: http://0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
