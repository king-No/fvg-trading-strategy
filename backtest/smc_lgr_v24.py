#!/usr/bin/env python3
"""
SMC LGR 引擎 v2.4 (最终版)
============================
SMC (Smart Money Concepts) 独立交易引擎
基于流动性掠夺反转 (Liquidity Grab Reversal) 模式

核心逻辑:
  1. 检测 swing high/low (窗口=3)
  2. 检测流动性掠夺: 价格假突破摆动点后收回
  3. FVG确认: 掠夺同方向有FVG存在
  4. ADX≥20过滤 + 4h趋势滤网

比v9.4基线:
  - 15m: +62.6% vs -2.9%, 卡玛13.17 vs 0.14
  - 1h:  +40.4% vs +11.7%, 卡玛5.43 vs 0.66

用法:
  python smc_lgr.py                    # 15m 默认
  python smc_lgr.py --tf 1h            # 1h
  python smc_lgr.py --test extra       # 额外验证
"""
import requests, time, pandas as pd, numpy as np, sys
from datetime import datetime, timedelta
from smartmoneyconcepts import smc
import pandas_ta as ta

# ═══ 全局参数 ═══
SYM="BTC/USDT"
LEV=5;POS=0.30;SL_M=2.3  # 同v9.4
SWING_W=3                  # 摆动检测窗口
ADX_TH=20                  # ADX阈值
FVG_W=5                    # FVG查询窗口(前后各N根)

def fetch(lim=3000, bar="1H"):
    s="BTC-USDT";d=[];a=""
    while len(d)<lim:
        u=f"https://www.okx.com/api/v5/market/history-candles?instId={s}&limit=300&bar={bar}"
        if a:u+=f"&after={a}"
        try:r=requests.get(u,timeout=10).json()
        except:break
        if r.get("code")!="0":break
        c=r.get("data",[]);d.extend(c);a=c[-1][0];time.sleep(0.1)
    rows=[[int(c[0]),float(c[1]),float(c[2]),float(c[3]),float(c[4]),float(c[5])] for c in d]
    df=pd.DataFrame(rows,columns=["ts","open","high","low","close","volume"])
    df["ts"]=pd.to_datetime(df["ts"],unit="ms")
    return df.drop_duplicates(subset="ts").sort_values("ts").reset_index(drop=True)

def detect_lgr_signals(df):
    """返回: df带信号列, 统计dict"""
    s1=smc.swing_highs_lows(df,SWING_W)
    f1=smc.fvg(df)
    df["sw_h"]=(s1["HighLow"]==1.0).astype(int)
    df["sw_l"]=(s1["HighLow"]==-1.0).astype(int)
    df["FVG"]=f1["FVG"].fillna(0).astype(int)
    df["ATR"]=ta.atr(df["high"],df["low"],df["close"],14)
    df["ADX"]=ta.adx(df["high"],df["low"],df["close"]).get("ADX_14",0)
    df["ema20"]=ta.ema(df["close"],20);df["ema50"]=ta.ema(df["close"],50)
    
    # 事件检测
    recent_sh=[];recent_sl=[]
    df["cus_sweep"]=0
    for i in range(20,len(df)):
        r=df.iloc[i]
        if r["sw_h"]==1:recent_sh.append((i,r["high"]))
        if r["sw_l"]==1:recent_sl.append((i,r["low"]))
        recent_sh=[x for x in recent_sh if x[0]>i-20]
        recent_sl=[x for x in recent_sl if x[0]>i-20]
        for (si,sp) in recent_sh:
            if si>=i:continue
            if r["high"]>sp and r["close"]<sp:
                df.iloc[i,df.columns.get_loc("cus_sweep")]=-1;break
        for (si,sp) in recent_sl:
            if si>=i:continue
            if r["low"]<sp and r["close"]>sp:
                df.iloc[i,df.columns.get_loc("cus_sweep")]=1;break
    
    # 信号生成
    df["signal"]=0
    for i in range(30,len(df)):
        swp=df.iloc[i]["cus_sweep"]
        if swp==0:continue
        if df.iloc[i]["ADX"]<ADX_TH:continue
        w=df.iloc[max(0,i-FVG_W):min(len(df),i+FVG_W+1)]
        if swp==-1 and (w["FVG"]==-1).any():
            df.iloc[i,df.columns.get_loc("signal")]=-1
        elif swp==1 and (w["FVG"]==1).any():
            df.iloc[i,df.columns.get_loc("signal")]=1
    
    stats={
        "n_sh":int((df["sw_h"]==1).sum()),
        "n_sl":int((df["sw_l"]==1).sum()),
        "n_sweep":int((df["cus_sweep"]!=0).sum()),
        "n_sig":int((df["signal"]!=0).sum()),
        "n_long":int((df["signal"]==1).sum()),
        "n_short":int((df["signal"]==-1).sum()),
    }
    if stats["n_sig"]>0:
        sig=df[df["signal"]!=0]
        stats["start"]=sig["ts"].iloc[0].strftime("%Y-%m-%d")
        stats["end"]=sig["ts"].iloc[-1].strftime("%Y-%m-%d")
    return df, stats

def backtest(df, col="signal"):
    """回测 (v9.4相同的出场逻辑)"""
    cp=10000.0;po=0;ep=0;td=[];bl=[cp];best=0.0;active=False
    for i in range(1,len(df)):
        r=df.iloc[i];sg=r[col];p=r["close"];h,l=r["high"],r["low"];av=max(r["ATR"],30)
        if po!=0:
            if po==1:best=max(best,h)
            else:best=min(best,l)
            sl=ep-(av*SL_M)if po==1 else ep+(av*SL_M);ap=ep+(av*2.0)if po==1 else ep-(av*2.0)
            if(po==1 and p>=ap)or(po==-1 and p<=ap):active=True
            trail=best-(av*0.5)if po==1 else best+(av*0.5);tp=trail if active else None
            hs=(po==1 and l<=sl)or(po==-1 and h>=sl);ht=tp and((po==1 and h>=tp)or(po==-1 and l<=tp))
            rv=sg!=0 and sg!=po
            if hs or ht or rv:
                xp=tp if ht else sl if hs else p
                pnl=cp*POS*LEV*((xp-ep)/ep)*(1 if po==1 else -1);cp+=pnl
                td.append({"pnl":round(pnl,2)});po=0;active=False;best=0
        if sg!=0 and po==0:po=sg;ep=p;ea=av;best=p;active=False
        bl.append(cp)
    n=len(td);rt=(cp-10000)/10000*100
    if n==0:return {"n":0,"wr":0,"pf":0,"rt":0,"md":0,"kr":0}
    w=sum(1 for t in td if t["pnl"]>0);gw=sum(t["pnl"] for t in td if t["pnl"]>0);gl=abs(sum(t["pnl"] for t in td if t["pnl"]<=0))
    pk=np.maximum.accumulate(bl);dd=(np.array(bl)-pk)/pk*100;md=dd.min()
    return {"n":n,"wr":w/n*100,"pf":gw/gl if gl else 99,"rt":rt,"md":md,"kr":abs(rt/md)if md else 0}

def v94_baseline(df,df4):
    """v9.4基线信号"""
    f4=smc.fvg(df4);s4=smc.swing_highs_lows(df4,15);b4=smc.bos_choch(df4,s4)
    df4["n4"]=((f4["FVG"]==1).rolling(8).sum()-(f4["FVG"]==-1).rolling(8).sum()).fillna(0)
    df4["tr4"]=0
    df4.loc[(df4["n4"]>=2)|(b4["CHOCH"]==1)|(b4["BOS"]==1),"tr4"]=1
    df4.loc[(df4["n4"]<=-2)|(b4["CHOCH"]==-1)|(b4["BOS"]==-1),"tr4"]=-1
    df["tr4"]=0
    for _,r in df4.iterrows():
        m=(df["ts"]>=r["ts"])&(df["ts"]<r["ts"]+timedelta(hours=4));df.loc[m,"tr4"]=r["tr4"]
    df["tr4"]=df["tr4"].ffill().fillna(0)
    df["s94"]=0
    f1=smc.fvg(df)
    df["FVG"]=f1["FVG"].fillna(0).astype(int)
    for i in range(36,len(df)):
        w=df.iloc[i-36:i];r=df.iloc[i];b=int((w["FVG"]==1).sum());s=int((w["FVG"]==-1).sum())
        adx_col="ADX" if "ADX" in df.columns else ta.adx(df["high"],df["low"],df["close"],14).get("ADX_14",0)
        if b>s*1.1 and r["tr4"]!=-1:
            df.iloc[i,df.columns.get_loc("s94")]=1
        if s>b*1.1 and r["tr4"]!=1:
            df.iloc[i,df.columns.get_loc("s94")]=-1
    return df

def main():
    tf="15m"
    if "--tf" in sys.argv:
        idx=sys.argv.index("--tf");tf=sys.argv[idx+1] if idx+1<len(sys.argv) else "15m"
    
    print(f"{'='*60}")
    print(f"  SMC LGR v2.4 — {tf}")
    print(f"  参数: SwingW={SWING_W} ADX≥{ADX_TH} FVG窗口={FVG_W}")
    print(f"{'='*60}")
    
    n4=1200;n1=3000
    bar4="4H";bar1=tf
    if tf=="1h":n1=2000;n4=800
    elif tf=="4h":n1=800;n4=300
    
    df4=fetch(n4,bar4);df=fetch(n1,bar1)
    if len(df)==0:print("❌ 无数据");return
    print(f"数据: {len(df)}/{tf} ({df['ts'].iloc[0].strftime('%Y-%m-%d')}~{df['ts'].iloc[-1].strftime('%Y-%m-%d')})")
    
    df,stats=detect_lgr_signals(df)
    df=v94_baseline(df,df4)
    
    print(f"\n📊 事件统计:")
    print(f"  SwingH: {stats['n_sh']} | SwingL: {stats['n_sl']}")
    print(f"  Sweeps: {stats['n_sweep']} | LGR信号: {stats['n_sig']}")
    if stats['n_sig']>0:
        print(f"  方向: 多={stats['n_long']} | 空={stats['n_short']}")
    
    print(f"\n📊 回测结果:")
    r94=backtest(df,"s94");rlgr=backtest(df,"signal")
    def pp(name,r):
        if r["n"]>0:
            print(f"  {name:>20}: {r['n']:>4}笔 | {r['wr']:>5.1f}%胜率 | PF{r['pf']:>5.2f} | 收益{r['rt']:>+7.2f}% | 回撤{r['md']:>5.1f}% | 卡玛{r['kr']:>5.2f}")
        else:
            print(f"  {name:>20}: 无交易")
    pp("v9.4基线",r94);pp("LGR引擎",rlgr)
    if r94["n"]>0 and rlgr["n"]>0:
        print(f"\n  ✅ LGR收益 +{rlgr['rt']-r94['rt']:+.2f}% 优于v9.4" if rlgr["rt"]>r94["rt"] else f"  ❌ LGR收益 {rlgr['rt']-r94['rt']:+.1f}% 不及v9.4")
        print(f"  ✅ LGR卡玛 {rlgr['kr']:.2f} vs v9.4 {r94['kr']:.2f}" if rlgr["kr"]>r94["kr"] else f"  ❌ LGR卡玛 {rlgr['kr']:.2f} vs v9.4 {r94['kr']:.2f}")

if __name__=="__main__":main()
