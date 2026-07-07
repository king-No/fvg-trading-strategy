#!/usr/bin/env python3
"""LGR 小资金参数优化扫描

扫描: 杠杆 × 仓位 × SL × TP激活 × TP跟随
目标: 小资金(~$150)下最佳参数组合
"""
import requests, time, pandas as pd, numpy as np
from datetime import datetime, timedelta
from smartmoneyconcepts import smc
import pandas_ta as ta

SWING_W=3;ADX_TH=20;FVG_W=5

def fetch(lim,bar):
    s="BTC-USDT";d=[];a=""
    while len(d)<lim:
        u=f"https://www.okx.com/api/v5/market/history-candles?instId={s}&limit=300&bar={bar}"
        if a:u+=f"&after={a}"
        try:r=requests.get(u,timeout=10).json()
        except:break
        if r.get("code")!="0":break
        c=r.get("data",[]);d.extend(c);a=c[-1][0];time.sleep(0.05)
    rows=[[int(c[0]),float(c[1]),float(c[2]),float(c[3]),float(c[4]),float(c[5])] for c in d]
    df=pd.DataFrame(rows,columns=["ts","open","high","low","close","volume"])
    df["ts"]=pd.to_datetime(df["ts"],unit="ms")
    return df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)

print("="*60)
print(" LGR 小资金参数优化扫描")
print("="*60)

df=fetch(8700,"15m")
print(f"数据: {len(df)}/15m ({df['ts'].iloc[0].strftime('%m-%d')}~{df['ts'].iloc[-1].strftime('%m-%d')})")

# 指标 (只算一次)
s1=smc.swing_highs_lows(df,SWING_W);f1=smc.fvg(df)
df["sw_h"]=(s1["HighLow"]==1.0).astype(int);df["sw_l"]=(s1["HighLow"]==-1.0).astype(int)
df["FVG"]=f1["FVG"].fillna(0).astype(int)
df["ATR"]=ta.atr(df["high"],df["low"],df["close"],14)
adx=ta.adx(df["high"],df["low"],df["close"]);df["ADX"]=adx.get("ADX_14",0)if adx is not None else 0

# Sweep
sh,sl=[],[]
sw=np.zeros(len(df),dtype=int)
for i in range(20,len(df)):
    r=df.iloc[i]
    if r["sw_h"]==1:sh.append((i,r["high"]))
    if r["sw_l"]==1:sl.append((i,r["low"]))
    sh=[(idx,p)for idx,p in sh if idx>i-20];sl=[(idx,p)for idx,p in sl if idx>i-20]
    for si,sp in sh:
        if si>=i:continue
        if r["high"]>sp and r["close"]<sp:sw[i]=-1;break
    for si,sp in sl:
        if si>=i:continue
        if r["low"]<sp and r["close"]>sp:sw[i]=1;break
df["cus_sweep"]=sw

# LGR信号
sig=np.zeros(len(df),dtype=int)
for i in range(30,len(df)):
    s=sw[i]
    if s==0:continue
    if df.iloc[i]["ADX"]<ADX_TH:continue
    st,end=max(0,i-FVG_W),min(len(df),i+FVG_W+1)
    w=df.iloc[st:end]
    if s==-1 and (w["FVG"]==-1).any():sig[i]=-1
    elif s==1 and (w["FVG"]==1).any():sig[i]=1
df["signal"]=sig

def bt(POS,LEV,SL_M,TP_ACT,TP_TR):
    cp=10000.0;po=0;ep=0;ea=0;td=[];bl=[cp];best=0.0;active=False
    for i in range(1,len(df)):
        r=df.iloc[i];sg=r["signal"];p=r["close"];h,l=r["high"],r["low"];av=max(r["ATR"],30)
        if po!=0:
            if po==1:best=max(best,h)
            else:best=min(best,l)
            sl=ep-(av*SL_M)if po==1 else ep+(av*SL_M);ap=ep+(av*TP_ACT)if po==1 else ep-(av*TP_ACT)
            if(po==1 and p>=ap)or(po==-1 and p<=ap):active=True
            trail=best-(av*TP_TR)if po==1 else best+(av*TP_TR)
            tp=trail if active else None
            hs=(po==1 and l<=sl)or(po==-1 and h>=sl);ht=tp and((po==1 and h>=tp)or(po==-1 and l<=tp))
            rv=sg!=0 and sg!=po
            if hs or ht or rv:
                xp=tp if ht else sl if hs else p
                pnl=cp*POS*LEV*((xp-ep)/ep)*(1if po==1 else-1);cp+=pnl
                td.append({"pnl":round(pnl,2)});po=0;active=False;best=0
        if sg!=0 and po==0:po=sg;ep=p;ea=av;best=p;active=False
        bl.append(cp)
    n=len(td);rt=(cp-10000)/10000*100
    if n==0:return{"n":0,"wr":0,"pf":0,"rt":0,"md":0,"kr":0,"avg_pnl":0}
    w=sum(1for t in td if t["pnl"]>0);gw=sum(t["pnl"]for t in td if t["pnl"]>0);gl=abs(sum(t["pnl"]for t in td if t["pnl"]<=0))
    pk=np.maximum.accumulate(bl);dd=(np.array(bl)-pk)/pk*100;md=dd.min()
    avg_pnl = np.mean([t["pnl"] for t in td])
    return{"n":n,"wr":w/n*100,"pf":gw/gl if gl else 99,"rt":rt,"md":md,"kr":abs(rt/md)if md else 0,"avg_pnl":avg_pnl}

# ═══ 扫描 ═══
results=[]

# 杠杆 × 仓位组合 (有效杠杆 = LEV × POS)
lev_opts=[5,10,15,20]
pos_opts=[0.15,0.20,0.30,0.50]
sl_opts=[1.5,1.9,2.3,3.0]
tp_act_opts=[1.5,2.0,2.5]
tp_tr_opts=[0.3,0.5]

total=len(lev_opts)*len(pos_opts)*len(sl_opts)*len(tp_act_opts)*len(tp_tr_opts)
done=0

print(f"\n扫描中 ({total}组合)...")
print(f"\n{'有效杠杆':>8} {'仓位':>6} {'杠杆':>4} {'SL':>4} {'TP激活':>6} {'TP跟随':>6} {'交易':>5} {'胜率':>6} {'PF':>5} {'收益':>10} {'回撤':>6} {'卡玛':>7} {'平均盈亏':>8}")
print("-"*95)

for lev in lev_opts:
    for pos in pos_opts:
        eff=lev*pos
        for sl_m in sl_opts:
            for tp_a in tp_act_opts:
                for tp_t in tp_tr_opts:
                    r=bt(pos,lev,sl_m,tp_a,tp_t)
                    done+=1
                    if r["n"]>0:
                        print(f"{eff:>6.2f}x {pos:>5.0%} {lev:>4}x {sl_m:>3.1f}x {tp_a:>5.1f}x {tp_t:>4.1f}x {r['n']:>5} {r['wr']:>5.1f}% {r['pf']:>4.2f} {r['rt']:>+8.2f}% {r['md']:>5.1f}% {r['kr']:>6.2f} {r['avg_pnl']:>+7.2f}%")
                    results.append((eff,pos,lev,sl_m,tp_a,tp_t,r))

# Top 15 按卡玛
print(f"\n{'='*95}")
print(" Top 15 按卡玛排序")
print("-"*95)
results.sort(key=lambda x:x[6]["kr"], reverse=True)
for eff,pos,lev,sl_m,tp_a,tp_t,r in results[:15]:
    print(f"有效{eff:>4.2f}x 仓{pos:>4.0%} 杠{lev:>2}x SL{sl_m:>3.1f}x 激{tp_a:>3.1f}x 跟{tp_t:>3.1f}x → {r['n']:>4}笔 | {r['wr']:>5.1f}% | PF{r['pf']:>4.2f} | 收益{r['rt']:>+8.2f}% | 回撤{r['md']:>5.1f}% | 卡玛{r['kr']:>5.2f} | 均盈{r['avg_pnl']:>+5.2f}%")

# Top 15 按总收益
print(f"\n{'='*95}")
print(" Top 15 按总收益排序")
print("-"*95)
results.sort(key=lambda x:x[6]["rt"], reverse=True)
for eff,pos,lev,sl_m,tp_a,tp_t,r in results[:15]:
    print(f"有效{eff:>4.2f}x 仓{pos:>4.0%} 杠{lev:>2}x SL{sl_m:>3.1f}x 激{tp_a:>3.1f}x 跟{tp_t:>3.1f}x → {r['n']:>4}笔 | {r['wr']:>5.1f}% | PF{r['pf']:>4.2f} | 收益{r['rt']:>+8.2f}% | 回撤{r['md']:>5.1f}% | 卡玛{r['kr']:>5.2f} | 均盈{r['avg_pnl']:>+5.2f}%")

# 低回撤方案 (< -8%)
print(f"\n{'='*95}")
print(" 低回撤方案 (回撤 < -8%) 按收益排序")
print("-"*95)
results2=[x for x in results if x[6]["md"]>-8]
results2.sort(key=lambda x:x[6]["rt"], reverse=True)
for eff,pos,lev,sl_m,tp_a,tp_t,r in results2[:10]:
    print(f"有效{eff:>4.2f}x 仓{pos:>4.0%} 杠{lev:>2}x SL{sl_m:>3.1f}x 激{tp_a:>3.1f}x 跟{tp_t:>3.1f}x → {r['n']:>4}笔 | {r['wr']:>5.1f}% | PF{r['pf']:>4.2f} | 收益{r['rt']:>+8.2f}% | 回撤{r['md']:>5.1f}% | 卡玛{r['kr']:>5.2f} | 均盈{r['avg_pnl']:>+5.2f}%")
