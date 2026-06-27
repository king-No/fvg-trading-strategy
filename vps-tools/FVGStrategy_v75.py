"""
FVG v7.5 + RSI 多周期策略 — Freqtrade 版
=========================================
v6 基础 + 改进:
  - 4h FVG 方向共振（过滤逆势信号）
  - 4h ATR 收缩过滤（震荡市不交易）
  - ADX≥20 趋势强度确认
  - ATR 动态止损止盈
"""

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import pandas as pd
import numpy as np
from smartmoneyconcepts import smc
import pandas_ta as ta


class FVGStrategy(IStrategy):
    timeframe = "1h"
    can_short = True
    startup_candle_count = 100

    # Hyperopt 参数
    buy_params = {
        "fvg_window": 36,
        "fvg_ratio": 1.1,
        "rsi_ob": 73,
        "rsi_os": 35,
    }
    sell_params = {}

    fvg_window = IntParameter(15, 40, default=36, space="buy")
    fvg_ratio = DecimalParameter(1.0, 2.0, decimals=1, default=1.1, space="buy")
    rsi_ob = IntParameter(65, 80, default=73, space="buy")
    rsi_os = IntParameter(20, 35, default=35, space="buy")
    sl_mult = DecimalParameter(1.5, 4.0, decimals=1, default=1.9, space="sell")
    tp_mult = DecimalParameter(3.0, 7.0, decimals=1, default=5.1, space="sell")

    # 风控
    stoploss = -0.10
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    minimal_roi = {"0": 0.10}
    position_adjustment_enable = False
    max_entry_position_adjustment = -1

    # v7.5 新增参数
    adx_threshold = 20       # ADX 最低要求
    atr_contract_pct = 0.8   # ATR 收缩阈值（当前ATR < MA的80%视为收缩）

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, "4h") for pair in pairs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 4h 数据
        if self.dp:
            informative = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe="4h")
            if informative is not None and len(informative) > 50:
                fvg4 = smc.fvg(informative)
                sw4 = smc.swing_highs_lows(informative, 15)
                bos4 = smc.bos_choch(informative, sw4)

                # 4h FVG 方向（滚动4根）
                informative["fvg_dir"] = (
                    (fvg4["FVG"] == 1).rolling(4).sum()
                    - (fvg4["FVG"] == -1).rolling(4).sum()
                ).fillna(0)

                # 4h 趋势（v6 原有）
                informative["net_fvg"] = (
                    (fvg4["FVG"] == 1).rolling(8).sum()
                    - (fvg4["FVG"] == -1).rolling(8).sum()
                ).fillna(0)
                informative["trend"] = 0
                informative.loc[
                    (informative["net_fvg"] >= 2) | (bos4["CHOCH"] == 1) | (bos4["BOS"] == 1),
                    "trend",
                ] = 1
                informative.loc[
                    (informative["net_fvg"] <= -2) | (bos4["CHOCH"] == -1) | (bos4["BOS"] == -1),
                    "trend",
                ] = -1

                # 4h ATR 收缩检测
                informative["atr_4h"] = ta.atr(
                    informative["high"], informative["low"], informative["close"], length=14
                )
                informative["atr_ma"] = informative["atr_4h"].rolling(10).mean()
                informative["atr_tight"] = (
                    informative["atr_4h"] < informative["atr_ma"] * self.atr_contract_pct
                )

                # 合并到 1h
                dataframe = dataframe.merge(
                    informative[["date", "trend", "fvg_dir", "atr_tight"]],
                    on="date",
                    how="left",
                    suffixes=("", "_4h"),
                )
                dataframe["trend"] = dataframe["trend"].fillna(0)
                dataframe["fvg_dir"] = dataframe["fvg_dir"].fillna(0)
                dataframe["atr_tight"] = dataframe["atr_tight"].fillna(False)

        # 2. 1h FVG
        fvg1 = smc.fvg(dataframe)
        dataframe["FVG"] = fvg1["FVG"]

        # 3. Swing + BOS
        sw1 = smc.swing_highs_lows(dataframe, 20)
        bos1 = smc.bos_choch(dataframe, sw1)
        dataframe["BOS"] = bos1["BOS"]

        # 4. RSI + ATR + ADX
        dataframe["RSI"] = ta.rsi(dataframe["close"], length=14)
        dataframe["ATR"] = ta.atr(
            dataframe["high"], dataframe["low"], dataframe["close"], length=14
        )
        adx_raw = ta.adx(dataframe["high"], dataframe["low"], dataframe["close"])
        dataframe["ADX"] = adx_raw.get("ADX_14", adx_raw.iloc[:, 0] if adx_raw.shape[1] == 3 else 0)

        # 5. 滚动 FVG 偏度
        dataframe["bull_fvg"] = (
            (dataframe["FVG"] == 1).rolling(self.fvg_window.value).sum()
        )
        dataframe["bear_fvg"] = (
            (dataframe["FVG"] == -1).rolling(self.fvg_window.value).sum()
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_long"] = 0
        dataframe.loc[:, "enter_short"] = 0

        # v7.5 综合入场条件
        long_cond = (
            (dataframe["bull_fvg"] > dataframe["bear_fvg"] * self.fvg_ratio.value)
            & (dataframe["trend"] != -1)
            & (dataframe["RSI"] < self.rsi_ob.value)
            & (dataframe["volume"] > 0)
            & (dataframe["fvg_dir"] >= 0)           # 4h FVG 方向共振
            & (~dataframe["atr_tight"])              # ATR 未收缩
            & (dataframe["ADX"] >= self.adx_threshold)  # ADX 趋势确认
        )
        dataframe.loc[long_cond, "enter_long"] = 1

        short_cond = (
            (dataframe["bear_fvg"] > dataframe["bull_fvg"] * self.fvg_ratio.value)
            & (dataframe["trend"] != 1)
            & (dataframe["RSI"] > self.rsi_os.value)
            & (dataframe["volume"] > 0)
            & (dataframe["fvg_dir"] <= 0)           # 4h FVG 方向共振
            & (~dataframe["atr_tight"])              # ATR 未收缩
            & (dataframe["ADX"] >= self.adx_threshold)  # ADX 趋势确认
        )
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs) -> float:
        if trade.open_rate is None or trade.open_date is None:
            return self.stoploss
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            atr = last_candle.get("ATR", 0)
            if atr > 0:
                sl_price = trade.open_rate - (atr * self.sl_mult.value)
                if trade.is_short:
                    sl_price = trade.open_rate + (atr * self.sl_mult.value)
                return (sl_price / current_rate) - 1
        return self.stoploss
