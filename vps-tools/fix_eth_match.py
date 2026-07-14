with open("/root/fvg/trade_dashboard.py","r") as f:
    c=f.read()

# Replace ETH card HTML to match BTC card exactly
old_eth_card = """  <div class="pc">
    <div><div class="sym">ETH/USDT</div><div class="pr eth" id="ep">{eth_s}</div></div>
    <div class="rt"><div class="rtl">浮盈</div><div class="rtv" id="eupnl" style="font-size:14px;color:{ee_c}">$0.00</div></div>
  </div>"""

new_eth_card = """  <div class="pc">
    <div><div class="sym">ETH/USDT</div><div class="pr eth" id="ep">{eth_s}</div></div>
    <div class="rt"><div class="rtl">未实现</div><div class="rtv" id="eupnl" style="color:{ee_c}">$0.00</div></div>
  </div>"""

c = c.replace(old_eth_card, new_eth_card)

# Update JS for ETH P&L to match BTC style
old_js_eth = """if(d.upnl_e!==undefined){const eu=document.getElementById("eupnl");eu.innerText=(d.upnl_e>=0?"$+":"$")+Math.abs(d.upnl_e).toFixed(2);eu.style.color=d.upnl_e>=0?"#3fb950":"#f85149"}"""

new_js_eth = """if(d.upnl_e!==undefined){const eu=document.getElementById("eupnl");const v=d.upnl_e;eu.innerText=(v>=0?"$+":"$")+Math.abs(v).toFixed(2);eu.style.color=v>=0?"#3fb950":"#f85149"}"""

c = c.replace(old_js_eth, new_js_eth)

with open("/root/fvg/trade_dashboard.py","w") as f:
    f.write(c)
print("OK")
