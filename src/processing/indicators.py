"""Technical indicator calculations."""

from __future__ import annotations

import pandas as pd


def compute_returns(close: pd.Series) -> pd.DataFrame:
    """Percentage returns over 1, 5, and 15 prior rows."""
    return pd.DataFrame(
        {
            "return_1": close.pct_change(1) * 100,
            "return_5": close.pct_change(5) * 100,
            "return_15": close.pct_change(15) * 100,
        }
    )


def compute_sma(close: pd.Series, windows: tuple[int, ...] = (10, 20)) -> pd.DataFrame:
    """Simple moving averages."""
    data: dict[str, pd.Series] = {}
    for window in windows:
        data[f"sma_{window}"] = close.rolling(window=window).mean()
    return pd.DataFrame(data)


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rsi = pd.Series(index=close.index, dtype=float)
    for idx in close.index:
        g = avg_gain.loc[idx]
        l = avg_loss.loc[idx]
        if pd.isna(g) or pd.isna(l):
            rsi.loc[idx] = pd.NA
        elif l == 0 and g > 0:
            rsi.loc[idx] = 100.0
        elif g == 0 and l == 0:
            rsi.loc[idx] = 50.0
        else:
            rs = g / l
            rsi.loc[idx] = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD line and signal line."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"macd": macd, "macd_signal": macd_signal})


def compute_volume_change_pct(volume: pd.Series) -> pd.Series:
    """Volume change versus the previous row."""
    previous = volume.shift(1)
    return ((volume - previous) / previous.replace(0, pd.NA)) * 100


def build_feature_frame(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical features for an OHLCV dataframe."""
    close = ohlcv["close"].astype(float)
    volume = ohlcv["volume"].astype(float)

    features = pd.concat(
        [
            ohlcv[["symbol", "timestamp", "close", "volume"]].copy(),
            compute_returns(close),
            compute_sma(close),
            compute_rsi(close).rename("rsi_14"),
            compute_macd(close),
            compute_volume_change_pct(volume).rename("volume_change_pct"),
        ],
        axis=1,
    )
    return features
