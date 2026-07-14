#!/usr/bin/env python3
"""LGR 交易看板 — BTC+ETH双品种"""
import sqlite3, os, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse

DB_PATH = "/root/freqtrade/tradesv3.sqlite"
PORT = 8899

def bj(dt=None):
    if dt is None: return datetime.utcnow() + timedelta(hours=8)
    if isinstance(dt,str):
        try: dt=datetime.fromisoformat(dt)
        except: return dt
    return dt+timedelta(hours=8)

def live():
    try:
        import ccxt
        c=json.load(open("/root/freqtrade/user_data/config.json"))
        ex=ccxt.okx({"apiKey":c["exchange"]["key"],"secret":c["exchange"]["secret"],"password":c["exchange"]["password"]})
        ex.set_sandbox_mode(True)
        btc=ex.fetch_ticker("BTC/USDT:USDT")["last"]
        eth=ex.fetch_ticker("ETH/USDT:USDT")["last"]
        pos=ex.fetch_positions()
        ub=ue=0.0
        for p in pos:
            if float(p.get("contracts",0))>0:
                s=p.get("symbol","");pnl=float(p.get("unrealizedPnl",0))
                if "BTC" in s: ub+=pnl
                elif "ETH" in s: ue+=pnl
        return btc,eth,ub+ue,ub,ue
    except: return None,None,None,None,None

def db_stats():
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    cur=conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM trades");t=cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM trades WHERE is_open=1");o=cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM trades WHERE is_open=0");cl=cur.fetchone()["c"]
    cur.execute("SELECT close_profit,stake_amount,close_rate,open_rate,is_short FROM trades WHERE is_open=0")
    w=l=0;r=0.0
    for x in cur.fetchall():
        p=x["close_profit"];s=x["stake_amount"] or 0
        if p is not None:
            u=p*s;r+=u
            if u>0: w+=1
            else: l+=1
        elif x["close_rate"] and x["open_rate"]:
            raw=(x["close_rate"]-x["open_rate"])/x["open_rate"]
            pct=-raw if x["is_short"] else raw;u=s*pct;r+=u
            if u>0: w+=1
    conn.close()
    wr=w/(w+l)*100 if(w+l)else 0
    return t,o,cl,w,l,round(wr,1),round(r,2)

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d1117;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:24px;max-width:960px;margin:0 auto}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}
.top h1{color:#e6edf3;font-size:20px;font-weight:600}
.st{color:#3fb950;font-size:11px;display:flex;align-items:center;gap:6px}
.st::before{content:'';width:6px;height:6px;background:#3fb950;border-radius:50%;display:inline-block}
.pr{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px}
.c{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 18px;display:flex;justify-content:space-between;align-items:center}
.c .sy{font-size:10px;color:#8b949e;text-transform:uppercase}
.c .prc{font-size:24px;font-weight:700;letter-spacing:-0.5px;margin-top:1px}
.c .btc{color:#f7931a}
.c .eth{color:#a78bfa}
.c .rt{text-align:right}
.c .rl{font-size:9px;color:#484f58;text-transform:uppercase}
.c .rv{font-size:16px;font-weight:600}
.sg{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-bottom:14px}
.s{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:10px;text-align:center}
.s .l{font-size:8px;color:#484f58;text-transform:uppercase;letter-spacing:0.5px}
.s .v{font-size:14px;font-weight:600;margin-top:2px}
.s .v.sm{font-size:11px;font-weight:500}
.tg{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.t{font-size:10px;color:#484f58;background:#0d1117;padding:3px 10px;border-radius:10px;border:1px solid #21262d}
.stitle{font-size:11px;color:#8b949e;font-weight:500;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid #21262d}
table{width:100%;border-collapse:collapse;font-size:11px}
th{background:#161b22;padding:6px 8px;text-align:left;color:#484f58;font-weight:500;font-size:9px;text-transform:uppercase;border-bottom:1px solid #30363d}
td{padding:6px 8px;border-bottom:1px solid #161b22}
tr:hover td{background:rgba(255,255,255,0.015)}
.gn{color:#3fb950}.rd{color:#f85149}
.b{display:inline-block;padding:1px 6px;border-radius:6px;font-size:8px;font-weight:500}
.b-tp{background:rgba(63,185,80,0.1);color:#3fb950}
.b-sl{background:rgba(248,81,73,0.1);color:#f85149}
.b-rv{background:rgba(56,139,253,0.1);color:#58a6ff}
.b-op{background:rgba(210,153,34,0.1);color:#d29922}
.ft{color:#484f58;font-size:9px;margin-top:10px;padding-top:8px;border-top:1px solid #21262d;display:flex;justify-content:space-between}
"""

JS = """<script>
let la=0;
function up(){
  fetch('/api/live').then(r=>r.json()).then(d=>{
    if(d.btc){const e=document.getElementById('bp');
      if(d.btc>la)e.style.color='#3fb950';else if(d.btc<la)e.style.color='#f85149';la=d.btc;
      e.innerText='$'+d.btc.toLocaleString(undefined,{minimumFractionDigits:2});setTimeout(()=>{e.style.color='#f7931a'},500)}
    if(d.eth){document.getElementById('ep').innerText='$'+d.eth.toLocaleString(undefined,{minimumFractionDigits:2})}
    const u=document.getElementById('up');if(u&&d.up!==undefined){const v=d.up;u.innerText=(v>=0?'$+':'$')+Math.abs(v).toFixed(2);u.style.color=v>=0?'#3fb950':'#f85149'}
    const eu=document.getElementById('eup');if(eu&&d.ue!==undefined){const v=d.ue;eu.innerText=(v>=0?'$+':'$')+Math.abs(v).toFixed(2);eu.style.color=v>=0?'#3fb950':'#f85149'}
    document.getElementById('ls').innerText='LIVE';
  }).catch(()=>{document.getElementById('ls').innerText='OFFLINE'});
}
setInterval(up,5000);setInterval(()=>{location.reload()},30000);up();
</script>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/api/live":
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin","*")
            self.end_headers()
            btc,eth,up,ub,ue=live()
            _,_,_,_,_,_,r=db_stats()
            self.wfile.write(json.dumps({"btc":btc,"eth":eth,"up":up,"ub":ub,"ue":ue,"r":r,"ts":bj().strftime('%H:%M')}).encode())
            return
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        btc,eth,up,ub,ue=live()
        t,o,_,w,l,wr,r=db_stats()
        btc_s=f"${btc:,.2f}" if btc else"—"
        eth_s=f"${eth:,.2f}" if eth else"—"
        up_s=f"${up:+,.2f}" if up and abs(up)>=0.01 else"$0.00"
        up_c="#3fb950" if up and up>=0 else"#f85149"
        ub_s=f"${ub:+,.2f}" if ub and abs(ub)>=0.01 else"$0.00"
        ub_c="#3fb950" if ub and ub>=0 else"#f85149"
        ue_s=f"${ue:+,.2f}" if ue and abs(ue)>=0.01 else"$0.00"
        ue_c="#3fb950" if ue and ue>=0 else"#f85149"
        r_s=f"${r:+,.2f}" if abs(r)>=0.01 else"$0.00"
        r_c="#3fb950" if r>=0 else"#f85149"
        n=bj().strftime('%m-%d %H:%M')

        html=[f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LGR 交易看板</title><style>{CSS}</style></head><body>
<div class="top"><h1>LGR 交易看板</h1><span class="st" id="ls">LIVE</span></div>
<div class="pr">
  <div class="c"><div><div class="sy">BTC/USDT</div><div class="prc btc" id="bp">{btc_s}</div></div><div class="rt"><div class="rl">未实现</div><div class="rv" id="up" style="color:{ub_c}">{ub_s}</div></div></div>
  <div class="c"><div><div class="sy">ETH/USDT</div><div class="prc eth" id="ep">{eth_s}</div></div><div class="rt"><div class="rl">未实现</div><div class="rv" id="eup" style="color:{ue_c}">{ue_s}</div></div></div>
</div>
<div class="sg">
  <div class="s"><div class="l">交易</div><div class="v">{t}</div></div>
  <div class="s"><div class="l">持仓</div><div class="v">{o}</div></div>
  <div class="s"><div class="l">胜/负</div><div class="v sm">{w}<span class="gn">W</span> / {l}<span class="rd">L</span></div></div>
  <div class="s"><div class="l">胜率</div><div class="v">{wr}%</div></div>
  <div class="s"><div class="l">已实现</div><div class="v sm" style="color:{r_c}">{r_s}</div></div>
  <div class="s"><div class="l">杠杆</div><div class="v sm">5x</div></div>
</div>
<div class="tg">
  <span class="t">LGR v1.0</span><span class="t">SL 1.5x ATR</span><span class="t">TP 1.5x→0.2x</span><span class="t">15m / ADX≥20</span><span class="t">{n}</span>
</div>"""]

        if os.path.exists(DB_PATH):
            conn=sqlite3.connect(DB_PATH)
            conn.row_factory=sqlite3.Row
            cur=conn.cursor()
            cur.execute("SELECT id,pair,open_date,close_date,open_rate,close_rate,close_profit,is_open,is_short,exit_reason,leverage FROM trades ORDER BY id DESC LIMIT 30")
            rows=cur.fetchall()
            conn.close()
            if rows:
                html.append('<div class="stitle">📋 交易明细</div><table><thead><tr><th>#</th><th>对</th><th>方向</th><th>杠杆</th><th>开仓</th><th>开仓价</th><th>平仓</th><th>盈亏</th><th>结果</th></tr></thead><tbody>')
                for r in rows:
                    io=r["is_open"];sh=r["is_short"];op=r["open_rate"];cl=r["close_rate"]
                    pf=r["close_profit"];lv=r["leverage"] or 1
                    side="空" if sh else"多";sc="rd" if sh else"gn"
                    pp=pf
                    if pp is None and cl and op: r2=(cl-op)/op;pp=-r2 if sh else r2
                    if io:
                        badge='<span class="b b-op">持仓</span>';ps="—"
                    else:
                        rea=r["exit_reason"] or""
                        if"stoploss"in rea:badge='<span class="b b-sl">SL</span>'
                        elif pp and pp>0.005:badge='<span class="b b-tp">TP</span>'
                        else:badge='<span class="b b-rv">反转</span>'
                        ps=f"{'🟢'if pp and pp>0 else'🔴'}{pp*100:+.2f}%"if pp is not None else"—"
                    pair=r["pair"].split("/")[0]
                    html.append(f"<tr><td>#{r['id']}</td><td>{pair}</td><td class='{sc}'>{side}</td><td>{lv}x</td><td>{bj(r['open_date']).strftime('%m-%d %H:%M') if r['open_date'] else '-'}</td><td>${op:,.2f}</td><td>{bj(r['close_date']).strftime('%m-%d %H:%M') if r['close_date'] else '-'}</td><td class='{'gn' if pp and pp>0 else 'rd'}'>{ps}</td><td>{badge}</td></tr>")
                html.append("</tbody></table>")
        html.append(f'<div class="ft"><span>LGR v1.0 · {n}</span><span>30s自动刷新</span></div>{JS}</body></html>')
        self.wfile.write("".join(html).encode())
    def log_message(self,*a):pass

if __name__=="__main__":
    print(f"看板: http://0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0",PORT),H).serve_forever()
