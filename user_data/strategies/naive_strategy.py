# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe helpers
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # Strategy helper functions
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib


# This class is a sample. Feel free to customize it.
class NaiveStrategy(IStrategy):
    """
    This is a sample strategy to inspire you.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_entry_trend, populate_exit_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 5

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "120": 0.01,
        "60": 0.02,
        "30": 0.03,
        "0": 0.04,
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.10

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Optimal timeframe for the strategy.
    timeframe = "1m"

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    buy_rsi = IntParameter(
        low=1, high=50, default=30, space="buy", optimize=True, load=True
    )
    sell_rsi = IntParameter(
        low=50, high=100, default=70, space="sell", optimize=True, load=True
    )
    short_rsi = IntParameter(
        low=51, high=100, default=70, space="sell", optimize=True, load=True
    )
    exit_short_rsi = IntParameter(
        low=1, high=50, default=30, space="buy", optimize=True, load=True
    )

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # Optional order time in force.
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    plot_config = {
        "main_plot": {
            "tema": {},
            "sar": {"color": "white"},
        },
        "subplots": {
            "MACD": {
                "macd": {"color": "blue"},
                "macdsignal": {"color": "orange"},
            },
            "RSI": {
                "rsi": {"color": "red"},
            },
        },
    }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Stochastic Fast
        stoch_fast = ta.STOCHF(dataframe)
        dataframe["fastd"] = stoch_fast["fastd"]
        dataframe["fastk"] = stoch_fast["fastk"]

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        dataframe["macdhist"] = macd["macdhist"]

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]

        # Calculate OBV
        dataframe["obv"] = ta.OBV(dataframe)

        # Calculate VWAP
        dataframe["vwap"] = (
            dataframe["volume"]
            * (dataframe["high"] + dataframe["low"] + dataframe["close"])
            / 3
        ).cumsum() / dataframe["volume"].cumsum()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["macd"] > dataframe["macdsignal"])
                & (dataframe["rsi"] < 70)
                & (dataframe["close"] < dataframe["bb_upperband"])
                & (dataframe["fastk"] < 80)
                & (dataframe["macdhist"] > 0)
                & (dataframe["close"] > dataframe["vwap"])
                & (dataframe["obv"] > dataframe["obv"].shift(1))
            ),
            "enter_long",
        ] = 1

        dataframe.loc[
            (
                (dataframe["macd"] < dataframe["macdsignal"])
                & (dataframe["rsi"] > 30)
                & (dataframe["close"] > dataframe["bb_lowerband"])
                & (dataframe["fastk"] > 20)
                & (dataframe["macdhist"] < 0)
                & (dataframe["close"] < dataframe["vwap"])
                & (dataframe["obv"] < dataframe["obv"].shift(1))
            ),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["macd"] < dataframe["macdsignal"])
                & (dataframe["rsi"] > 70)
                & (dataframe["close"] > dataframe["bb_upperband"])
                & (dataframe["fastk"] > 80)
                & (dataframe["macdhist"] < 0)
                & (dataframe["close"] < dataframe["vwap"])
                & (dataframe["obv"] < dataframe["obv"].shift(1))
            ),
            "exit_long",
        ] = 1

        dataframe.loc[
            (
                (dataframe["macd"] > dataframe["macdsignal"])
                & (dataframe["rsi"] < 30)
                & (dataframe["close"] < dataframe["bb_lowerband"])
                & (dataframe["fastk"] < 20)
                & (dataframe["macdhist"] > 0)
                & (dataframe["close"] > dataframe["vwap"])
                & (dataframe["obv"] > dataframe["obv"].shift(1))
            ),
            "exit_short",
        ] = 1

        return dataframe
