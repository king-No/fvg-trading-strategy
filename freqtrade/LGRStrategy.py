"""
LGRStrategy — 流动性掠夺反转 (生产版)
=======================================
入场: Sweep+FVG+ADX≥20 (15m)
出场: custom_stoploss (ATR固定) + custom_exit (trailing TP+限时反转)

回测(3个月): 293笔 | 62.8%胜率 | PF2.32 | +145% | 回撤-4.56% | 卡玛31.85
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import pandas_ta as ta
from smartmoneyconcepts import smc
import numpy as np


class LGRStrategy(IStrategy):
    timeframe = "15m"
    can_short = True
    startup_candle_count = 60

    stoploss = -0.08
    minimal_roi = {}
    use_custom_stoploss = True
    position_adjustment_enable = False

    # --- LGR参数 ---
    swing_window = 3
    adx_threshold = 20
    fvg_lookback = 5
    sweep_lookback = 20

    # --- 出场参数 ---
    sl_mult = 1.5
    tp_activate_mult = 1.5
    tp_trail_mult = 0.2
    atr_floor = 30

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        s1 = smc.swing_highs_lows(dataframe, self.swing_window)
        f1 = smc.fvg(dataframe)
        dataframe["sw_h"] = (s1["HighLow"] == 1.0).astype(int)
        dataframe["sw_l"] = (s1["HighLow"] == -1.0).astype(int)
        dataframe["FVG"] = f1["FVG"].fillna(0).astype(int)
        dataframe["ATR"] = ta.atr(dataframe["high"], dataframe["low"], dataframe["close"], 14)
        adx_df = ta.adx(dataframe["high"], dataframe["low"], dataframe["close"])
        dataframe["ADX"] = adx_df.get("ADX_14", 0) if adx_df is not None else 0

        # --- Sweep检测 ---
        recent_sh, recent_sl = [], []
        sweeps = np.zeros(len(dataframe), dtype=int)
        for i in range(20, len(dataframe)):
            r = dataframe.iloc[i]
            if r["sw_h"] == 1: recent_sh.append((i, r["high"]))
            if r["sw_l"] == 1: recent_sl.append((i, r["low"]))
            recent_sh = [(idx, p) for idx, p in recent_sh if idx > i - self.sweep_lookback]
            recent_sl = [(idx, p) for idx, p in recent_sl if idx > i - self.sweep_lookback]
            for si, sp in recent_sh:
                if si >= i: continue
                if r["high"] > sp and r["close"] < sp: sweeps[i] = -1; break
            for si, sp in recent_sl:
                if si >= i: continue
                if r["low"] < sp and r["close"] > sp: sweeps[i] = 1; break
        dataframe["cus_sweep"] = sweeps

        # --- LGR信号 ---
        signals = np.zeros(len(dataframe), dtype=int)
        for i in range(30, len(dataframe)):
            swp = sweeps[i]
            if swp == 0: continue
            if dataframe.iloc[i]["ADX"] < self.adx_threshold: continue
            start, end = max(0, i - self.fvg_lookback), min(len(dataframe), i + self.fvg_lookback + 1)
            w = dataframe.iloc[start:end]
            if swp == -1 and (w["FVG"] == -1).any(): signals[i] = -1
            elif swp == 1 and (w["FVG"] == 1).any(): signals[i] = 1
        dataframe["lgr_signal"] = signals

        # --- 信号距今K线数(限时反转用) ---
        age = np.full(len(dataframe), 999, dtype=int)
        last_sig = -999
        for i in range(len(dataframe)):
            if signals[i] != 0: last_sig = i
            age[i] = i - last_sig
        dataframe["age"] = age
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_long"] = 0
        dataframe.loc[:, "enter_short"] = 0
        dataframe.loc[dataframe["lgr_signal"] == 1, "enter_long"] = 1
        dataframe.loc[dataframe["lgr_signal"] == -1, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                        current_profit: float, **kwargs) -> float:
        """ATR固定止损 — 入场时记录ATR, 不随行情移动"""
        if not hasattr(self, "_entry_atr"): self._entry_atr = {}
        tid = trade.id
        if tid not in self._entry_atr:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is not None and len(df) > 0:
                atr = df.iloc[-1].get("ATR", 0)
                self._entry_atr[tid] = max(atr if atr and atr > 0 else self.atr_floor, self.atr_floor)
        atr = self._entry_atr.get(tid, self.atr_floor)
        if not trade.is_short:
            return max((trade.open_rate - atr * self.sl_mult) / current_rate - 1, -0.08)
        else:
            # 空单: 若当前价已超止损位, 返回极小值触发止损
            sl_price = trade.open_rate + atr * self.sl_mult
            if current_rate > sl_price:
                return 0.001
            return max((sl_price / current_rate) - 1, -0.08)

    def custom_exit(self, pair: str, trade, current_time, current_rate,
                    current_profit: float, **kwargs):
        """移动止盈 + 限时反转退出"""
        if not hasattr(self, "_best_prices"): self._best_prices = {}
        if not hasattr(self, "_tp_active"): self._tp_active = {}
        if not hasattr(self, "_entry_atr"): self._entry_atr = {}

        tid = trade.id
        if tid not in self._best_prices:
            self._best_prices[tid] = trade.open_rate
            self._tp_active[tid] = False

        atr = self._entry_atr.get(tid, self.atr_floor)
        side = -1 if trade.is_short else 1

        # 更新最佳价
        if side == 1: self._best_prices[tid] = max(self._best_prices[tid], current_rate)
        else: self._best_prices[tid] = min(self._best_prices[tid], current_rate)

        # TP激活: 价格朝有利方向移动1.5x ATR
        if not self._tp_active[tid]:
            target = trade.open_rate + atr * self.tp_activate_mult
            if side == 1 and current_rate >= target: self._tp_active[tid] = True
            target = trade.open_rate - atr * self.tp_activate_mult
            if side == -1 and current_rate <= target: self._tp_active[tid] = True

        # 跟随止盈: 从最高点回撤0.2x ATR即锁利
        if self._tp_active[tid]:
            if side == 1:
                if current_rate <= self._best_prices[tid] - atr * self.tp_trail_mult:
                    return "trailing_tp"
            else:
                if current_rate >= self._best_prices[tid] + atr * self.tp_trail_mult:
                    return "trailing_tp"

        # 限时反转退出 — 仅前8根K线(2h)内允许
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is not None and len(df) > 0:
            age = df.iloc[-1].get("age", 999)
            if age <= 8:
                sig = df.iloc[-1].get("lgr_signal", 0)
                if sig != 0 and ((sig == 1 and trade.is_short) or (sig == -1 and not trade.is_short)):
                    return "reversal"

        return None

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return 5.0

    def custom_stake_amount(self, pair, current_time, current_rate,
                            proposed_stake, min_stake, max_stake, leverage,
                            entry_tag, side, **kwargs) -> float:
        wallet = self.wallets.get_total_stake_amount()
        return min(wallet * 0.30, max_stake)
