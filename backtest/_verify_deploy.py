"""
LGRStrategy — 流动性掠夺反转 (生产版)
=======================================
基于 SMC LGR v2.4

入场: Sweep+FVG+ADX≥20 (15m)
出场: custom_stoploss (ATR固定) + custom_exit (trailing TP+反转)

回测(独立引擎): 95笔 +62.6% 胜率74.7% 卡玛13.17
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

    # --- 出场 ---
    sl_mult = 1.5
    tp_activate_mult = 2.0
    tp_trail_mult = 0.3
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

        # ─── Sweep检测 ───
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

        # ─── 结构分析 — SMC结构破位检测 ───
        # 收集摆动点序列
        swing_high_prices = [(i, dataframe.iloc[i]["high"]) for i in range(len(dataframe)) if dataframe.iloc[i]["sw_h"] == 1]
        swing_low_prices = [(i, dataframe.iloc[i]["low"]) for i in range(len(dataframe)) if dataframe.iloc[i]["sw_l"] == 1]

        hi_ptr = lo_ptr = 0
        last_h = None; prev_h = None
        last_l = None; prev_l = None
        cur_struct = 0
        struct_breaks = np.zeros(len(dataframe), dtype=int)

        for i in range(30, len(dataframe)):
            # 更新摆动点
            while hi_ptr < len(swing_high_prices) and swing_high_prices[hi_ptr][0] <= i:
                h = swing_high_prices[hi_ptr]
                if last_h is not None: prev_h = last_h
                last_h = h; hi_ptr += 1
            while lo_ptr < len(swing_low_prices) and swing_low_prices[lo_ptr][0] <= i:
                l_ = swing_low_prices[lo_ptr]
                if last_l is not None: prev_l = last_l
                last_l = l_; lo_ptr += 1

            # 判定结构: HH+HL=多头, LH+LL=空头
            if last_h and prev_h and last_l and prev_l:
                hh = last_h[1] > prev_h[1]; hl = last_l[1] > prev_l[1]
                lh = last_h[1] < prev_h[1]; ll = last_l[1] < prev_l[1]
                if hh and hl: cur_struct = 1
                elif lh and ll: cur_struct = -1

            # 结构破位: 多头收盘破前低 / 空头收盘破前高
            r = dataframe.iloc[i]
            if cur_struct == 1 and last_l is not None:
                if r["close"] < last_l[1] and r["close"] < r["open"]:
                    struct_breaks[i] = -1
            if cur_struct == -1 and last_h is not None:
                if r["close"] > last_h[1] and r["close"] > r["open"]:
                    struct_breaks[i] = 1
        dataframe["struct_break"] = struct_breaks

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
        """ATR固定止损 (存储入场ATR)"""
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
            if current_rate > trade.open_rate + atr * self.sl_mult:
                return 0.001
            return max((trade.open_rate + atr * self.sl_mult) / current_rate - 1, -0.08)

    def custom_exit(self, pair: str, trade, current_time, current_rate,
                    current_profit: float, **kwargs):
        """移动止盈 + 反转退出"""
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

        # TP激活
        if not self._tp_active[tid]:
            target = trade.open_rate + atr * self.tp_activate_mult
            if side == 1 and current_rate >= target: self._tp_active[tid] = True
            target = trade.open_rate - atr * self.tp_activate_mult
            if side == -1 and current_rate <= target: self._tp_active[tid] = True

        # 跟随止盈
        if self._tp_active[tid]:
            if side == 1:
                if current_rate <= self._best_prices[tid] - atr * self.tp_trail_mult:
                    return "trailing_tp"
            else:
                if current_rate >= self._best_prices[tid] + atr * self.tp_trail_mult:
                    return "trailing_tp"

        # 结构反转退出 (SMC破位, 最高权重)
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is not None and len(df) > 0:
            sb = df.iloc[-1].get("struct_break", 0)
            if sb != 0:
                if (sb == -1 and not trade.is_short) or (sb == 1 and trade.is_short):
                    return "structure_reversal"

        return None

    def leverage(self, pair, current_time, current_rate, proposed_leverage,
                 max_leverage, entry_tag, side, **kwargs) -> float:
        return 5.0

    def custom_stake_amount(self, pair, current_time, current_rate,
                            proposed_stake, min_stake, max_stake, leverage,
                            entry_tag, side, **kwargs) -> float:
        wallet = self.wallets.get_total_stake_amount()
        return min(wallet * 0.30, max_stake)
