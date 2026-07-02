#!/usr/bin/env python3
"""v9.4 — SL倍数扫描: 1.5x ~ 3.0x"""
import requests, time, pandas as pd, numpy as np
from datetime import datetime, timedelta
from smartmoneyconcepts import smc
import pandas_ta as ta

SYM="BTC/USDT";FW=36;FR=1.1;ROB=73;ROS=35;ADX_TH=20
LEV=5;POS=0.30

def fetch(t,lim=2000):
    s="BTC-USDT";b={"1h":"1H","4h":"4H"}[t];d=[];a=""
    while len(d)<lim:
        u=f"https://www.okx.com/api/v5/market/history-candles?instId={s}&limit=300&bar={b}"
        if a:u+=f"&after={a}"
        try:r=requests.get(u,timeout=10).json()
        except:break
        if r.get("code")!="0":break
        c=r.get("data",[]);d.extend(c);a=c[-1][0];time.sleep(0.1)
    rows=[[int(c[0]),float(c[1]),float(c[2]),float(c[3]),float(c[4]),float(c[5])] for c in d]
    df=pd.DataFrame(rows,columns=["ts","open","high","low","close","volume"])
    df["ts"]=pd.to_datetime(df["ts"],unit="ms")
    return df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)

print("="*60);print("  SL倍数扫描 — 1.5x ~ 3.5x");print("="*60)
df4=fetch("4h",1200);df1=fetch("1h",3000)

f4=smc.fvg(df4);s4=smc.swing_highs_lows(df4,15);b4=smc.bos_choch(df4,s4)
df4["fd"]=((f4["FVG"]==1).rolling(4).sum()-(f4["FVG"]==-1).rolling(4).sum()).fillna(0)
df4["a14"]=ta.atr(df4["high"],df4["low"],df4["close"],14)
df4["am"]=df4["a14"].rolling(10).mean();df4["at"]=df4["a14"]<df4["am"]*0.8
df4["nf"]=((f4["FVG"]==1).rolling(8).sum()-(f4["FVG"]==-1).rolling(8).sum()).fillna(0)
df4["tr"]=0
df4.loc[(df4["nf"]>=2)|(b4["CHOCH"]==1)|(b4["BOS"]==1),"tr"]=1
df4.loc[(df4["nf"]<=-2)|(b4["CHOCH"]==-1)|(b4["BOS"]==-1),"tr"]=-1

df1["tr"]=0;df1["fd"]=0;df1["at"]=False
for _,r in df4.iterrows():
    t=r["ts"];m=(df1["ts"]>=t)&(df1["ts"]<t+timedelta(hours=4))
    df1.loc[m,"tr"]=r["tr"];df1.loc[m,"fd"]=r["fd"];df1.loc[m,"at"]=r["at"]
df1["tr"]=df1["tr"].replace(0,method="ffill").fillna(0)

f1=smc.fvg(df1);s1=smc.swing_highs_lows(df1,20)
df1["FVG"]=f1["FVG"];df1["RSI"]=ta.rsi(df1["close"],14)
df1["ATR"]=ta.atr(df1["high"],df1["low"],df1["close"],14)
ax=ta.adx(df1["high"],df1["low"],df1["close"])
df1["ADX"]=ax.get("ADX_14",ax.iloc[:,0]if ax.shape[1]==3 else 0)
df1["bf"]=(df1["FVG"]==1).rolling(FW).sum()
df1["bef"]=(df1["FVG"]==-1).rolling(FW).sum()

df1["sig"]=0
for i in range(FW,len(df1)):
    w=df1.iloc[i-FW:i];r=df1.iloc[i];b=int((w["FVG"]==1).sum());s=int((w["FVG"]==-1).sum())
    if b>s*FR and r["tr"]!=-1 and r["RSI"]<ROB and r["fd"]>=0 and not r["at"]:
        df1.iloc[i,df1.columns.get_loc("sig")]=1
    elif s>b*FR and r["tr"]!=1 and r["RSI"]>ROS and r["fd"]<=0 and not r["at"]:
        df1.iloc[i,df1.columns.get_loc("sig")]=-1

def bt(sl_mult):
    cp=10000.0;po=0;ep=0;ea=0;td=[];bl=[cp]
    best=0.0;active=False
    for i in range(1,len(df1)):
        r=df1.iloc[i];sg=r["sig"];p=r["close"];h,l=r["high"],r["low"];av=max(r["ATR"],30)
        if po!=0:
            if po==1:best=max(best,h)
            else:best=min(best,l)
            sl=ep-(av*sl_mult)if po==1 else ep+(av*sl_mult)
            act=ep+(av*2.0)if po==1 else ep-(av*2.0)
            if(po==1 and p>=act)or(po==-1 and p<=act):active=True
            trail=best-(av*0.5)if po==1 else best+(av*0.5)
            tp=trail if active else(ep+(av*5.1)if po==1 else ep-(av*5.1))
            hs=(po==1 and l<=sl)or(po==-1 and h>=sl);ht=(po==1 and h>=tp)or(po==-1 and l<=tp)
            rv=sg!=0 and sg!=po
            if hs or ht or rv:
                xp=tp if ht else sl if hs else p
                pnl=cp*POS*LEV*((xp-ep)/ep)*(1if po==1else-1);cp+=pnl
                td.append({"pnl":round(pnl,2)});po=0;active=False;best=0
        if sg!=0 and po==0 and r["ADX"]>=ADX_TH:po=sg;ep=p;ea=av;best=p;active=False
        bl.append(cp)
    n=len(td);rt=(cp-10000)/10000*100
    if n==0:return None
    w=sum(1 for t in td if t["pnl"]>0)
    gw=sum(t["pnl"] for t in td if t["pnl"]>0);gl=abs(sum(t["pnl"] for t in td if t["pnl"]<=0))
    pk=np.maximum.accumulate(bl);dd=(np.array(bl)-pk)/pk*100;md=dd.min()
    rr=gw/w/(gl/(n-w))if(gl>0 and n-w>0)else 0
    return {"n":n,"wr":w/n*100,"pf":gw/gl if gl else 99,"rt":rt,"md":md,"kr":abs(rt/md)if md else 0,"rr":rr,"sl_cnt":n-w}

print("\n回测...")
res={}
for slm in [1.3,1.5,1.7,1.9,2.1,2.3,2.5,3.0]:
    r=bt(slm)
    if r:res[slm]=r

print(f"\n{'='*70}")
print(f"{'SL倍数':>8}{'交易':>6}{'胜率':>7}{'PF':>6}{'收益':>10}{'回撤':>7}{'卡玛':>6}{'RR':>7}{'SL笔':>5}")
print("-"*70)
for slm in sorted(res.keys()):
    r=res[slm]
    print(f"  {slm:.1f}x {r['n']:>5}{r['wr']:>6.1f}%{r['pf']:>6.2f}{r['rt']:>+9.2f}%{r['md']:>6.2f}%{r['kr']:>6.2f}{r['rr']:>6.2f}{r['sl_cnt']:>5}")
