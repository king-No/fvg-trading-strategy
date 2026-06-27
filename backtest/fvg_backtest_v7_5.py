#!/usr/bin/env python3
"""
FVG v7.5 — ADX 阈值优化
"""
import requests, time, pandas as pd, numpy as np
from datetime import datetime, timedelta
from smartmoneyconcepts import smc
import pandas_ta as ta
SYM="BTC/USDT"; FW=36; FR=1.1; ROB=73; ROS=35; SM=1.9; TM=5.1

def fetch(t="1h"):
    s="BTC-USDT"; b={"1h":"1H","4h":"4H"}[t]; d=[]; a=""
    while len(d)<3000:
        u=f"https://www.okx.com/api/v5/market/history-candles?instId={s}&limit=300&bar={b}"
        if a:u+=f"&after={a}"
        try:r=requests.get(u,timeout=10).json()
        except:break
        if r.get("code")!="0":break
        c=r.get("data",[]);d.extend(c);a=c[-1][0];time.sleep(0.15)
    rows=[[int(c[0]),float(c[1]),float(c[2]),float(c[3]),float(c[4]),float(c[5])]for c in d]
    df=pd.DataFrame(rows,columns=["timestamp","open","high","low","close","volume"])
    df["timestamp"]=pd.to_datetime(df["timestamp"],unit="ms")
    return df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

print("="*55+"\n  FVG v7.5 — ADX 阈值优化\n"+"="*55)
print("下载数据..."); df4=fetch("4h"); df1=fetch("1h")

f4=smc.fvg(df4); s4=smc.swing_highs_lows(df4,15); b4=smc.bos_choch(df4,s4)
df4["fd"]=((f4["FVG"]==1).rolling(4).sum()-(f4["FVG"]==-1).rolling(4).sum()).fillna(0)
df4["a14"]=ta.atr(df4["high"],df4["low"],df4["close"],14)
df4["am"]=df4["a14"].rolling(10).mean();df4["at"]=df4["a14"]<df4["am"]*0.8
df4["nf"]=((f4["FVG"]==1).rolling(8).sum()-(f4["FVG"]==-1).rolling(8).sum()).fillna(0)
df4["tr"]=0
df4.loc[(df4["nf"]>=2)|(b4["CHOCH"]==1)|(b4["BOS"]==1),"tr"]=1
df4.loc[(df4["nf"]<=-2)|(b4["CHOCH"]==-1)|(b4["BOS"]==-1),"tr"]=-1

df1["tr"]=0;df1["fd"]=0;df1["at"]=False
for _,r in df4.iterrows():
    t=r["timestamp"];m=(df1["timestamp"]>=t)&(df1["timestamp"]<t+timedelta(hours=4))
    df1.loc[m,"tr"]=r["tr"];df1.loc[m,"fd"]=r["fd"];df1.loc[m,"at"]=r["at"]
df1["tr"]=df1["tr"].replace(0,method="ffill").fillna(0)

f1=smc.fvg(df1);s1=smc.swing_highs_lows(df1,20)
df1["FVG"]=f1["FVG"];df1["RSI"]=ta.rsi(df1["close"],14);df1["ATR"]=ta.atr(df1["high"],df1["low"],df1["close"],14)
ax=ta.adx(df1["high"],df1["low"],df1["close"])
df1["ADX"]=ax.get("ADX_14",ax.iloc[:,0]if ax.shape[1]==3 else 0)

df1["sig"]=0
for i in range(FW,len(df1)):
    w=df1.iloc[i-FW:i];r=df1.iloc[i]
    b=int((w["FVG"]==1).sum());s=int((w["FVG"]==-1).sum())
    if b>s*FR and r["tr"]!=-1 and r["RSI"]<ROB and r["fd"]>=0 and not r["at"]:
        df1.iloc[i,df1.columns.get_loc("sig")]=1
    elif s>b*FR and r["tr"]!=1 and r["RSI"]>ROS and r["fd"]<=0 and not r["at"]:
        df1.iloc[i,df1.columns.get_loc("sig")]=-1

def bt(th):
    cp=10000.0;po=0;ep=0;ea=0;td=[];bl=[cp]
    for i in range(1,len(df1)):
        r=df1.iloc[i];sg=r["sig"];p=r["close"];hi,lo=r["high"],r["low"];av=max(r["ATR"],30)
        if po!=0:
            sl=ep-(ea*SM)if po==1 else ep+(ea*SM)
            tp=ep+(ea*TM)if po==1 else ep-(ea*TM)
            hs=(po==1 and lo<=sl)or(po==-1 and hi>=sl)
            ht=(po==1 and hi>=tp)or(po==-1 and lo<=tp)
            rv=sg!=0 and sg!=po
            if hs or ht or rv:
                xp=tp if ht else sl if hs else p
                pp=(xp-ep)/ep*100*(-1 if po==-1 else 1);pn=cp*pp/100;cp+=pn
                td.append({"pp":round(pp,2),"pn":round(pn,2)});po=0
        if sg!=0 and po==0 and r["ADX"]>=th:
            po=sg;ep=p;ea=av
        bl.append(cp)
    n=len(td);rt=(cp-10000)/10000*100
    if n==0:return None
    w=sum(1 for t in td if t["pn"]>0);l=n-w
    pf=abs(sum(t["pn"]for t in td if t["pn"]>0))/abs(sum(t["pn"]for t in td if t["pn"]<=0))if sum(t["pn"]for t in td if t["pn"]<=0)else 99
    pk=np.maximum.accumulate(bl);dd=(np.array(bl)-pk)/pk*100;md=dd.min()
    return {"n":n,"wr":w/n*100,"pf":pf,"rt":rt,"md":md,"kr":abs(rt/md)if md else 0}

rs={}
for th in [0,10,15,18,20,22,25,30]:
    r=bt(th)
    if r:rs[f"ADX≥{th}"]=r

print("\nADX 阈值对比:")
print(f"{'阈值':<10}{'交易':>4}{'胜率':>6}{'PF':>6}{'收益':>8}{'回撤':>7}{'卡玛':>7}")
print("-"*55)
for k in sorted(rs.keys()):
    r=rs[k];print(f"{k:<10}{r['n']:>4}{r['wr']:>5.1f}%{r['pf']:>6.2f}{r['rt']:>+7.2f}%{r['md']:>6.2f}%{r['kr']:>6.2f}")
bk=max(rs,key=lambda k:rs[k]["kr"])
print(f"\n🏆 最佳: {bk} — 卡玛 {rs[bk]['kr']:.2f}, 收益 {rs[bk]['rt']:+.2f}%")
print("="*55)
