"""Yahoo Finance market data and news fetcher."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

# Display symbol -> Yahoo Finance ticker
YAHOO_TICKERS: dict[str, str] = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "TSLA": "TSLA",
    "BTC-USD": "BTC-USD",
    "ETH-USD": "ETH-USD",
    "EUR-USD": "EURUSD=X",
}


def _to_utc_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.isoformat()


def _yahoo_ticker(symbol: str) -> str:
    return YAHOO_TICKERS.get(symbol, symbol)


def _with_retries(action: str, symbol: str, fn: Any, max_retries: int = 3) -> Any:
    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            message = str(exc)
            is_rate_limited = "Too Many Requests" in message or "429" in message
            if attempt == max_retries or not is_rate_limited:
                logger.error("Failed to %s for %s: %s", action, symbol, exc)
                return None if "OHLCV" in action or "fast_info" in action else []
            wait = attempt * 5
            logger.warning(
                "Rate limited fetching %s for %s — retrying in %ss",
                action,
                symbol,
                wait,
            )
            time.sleep(wait)
    return None if "OHLCV" in action or "fast_info" in action else []


def _fetch_from_chart_api(symbol: str) -> dict[str, Any] | None:
    """Fetch latest OHLCV from Yahoo's public chart API."""
    ticker = _yahoo_ticker(symbol)
    response = _SESSION.get(
        CHART_URL.format(ticker=ticker),
        params={"interval": "1d", "range": "1d"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    results = payload.get("chart", {}).get("result") or []
    if not results:
        logger.warning("No chart data for %s (%s)", symbol, ticker)
        return None

    result = results[0]
    meta = result.get("meta", {})
    quotes = (result.get("indicators", {}).get("quote") or [{}])[0]
    timestamps = result.get("timestamp") or []

    close_values = [v for v in quotes.get("close", []) if v is not None]
    if close_values:
        close_price = float(close_values[-1])
        idx = len(close_values) - 1
        open_price = float(quotes.get("open", [close_price])[idx] or close_price)
        high_price = float(quotes.get("high", [close_price])[idx] or close_price)
        low_price = float(quotes.get("low", [close_price])[idx] or close_price)
        volume = float(quotes.get("volume", [0])[idx] or 0)
        if timestamps:
            ts = datetime.fromtimestamp(timestamps[min(idx, len(timestamps) - 1)], tz=timezone.utc)
        else:
            ts = datetime.now(timezone.utc)
    else:
        close_price = float(meta.get("regularMarketPrice") or 0)
        if not close_price:
            return None
        open_price = float(meta.get("regularMarketOpen") or close_price)
        high_price = float(meta.get("regularMarketDayHigh") or close_price)
        low_price = float(meta.get("regularMarketDayLow") or close_price)
        volume = float(meta.get("regularMarketVolume") or 0)
        ts = datetime.fromtimestamp(
            meta.get("regularMarketTime", datetime.now(timezone.utc).timestamp()),
            tz=timezone.utc,
        )

    return {
        "event_type": "ohlcv",
        "symbol": symbol,
        "timestamp": _to_utc_iso(ts),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


def fetch_ohlcv(symbol: str) -> dict[str, Any] | None:
    """Fetch the latest OHLCV candle for a symbol from Yahoo Finance."""
    return _with_retries(
        "fetch OHLCV",
        symbol,
        lambda: _fetch_from_chart_api(symbol),
    )


def fetch_ohlcv_batch(symbols: list[str]) -> list[dict[str, Any]]:
    """Fetch latest quotes for multiple symbols."""
    events: list[dict[str, Any]] = []
    for symbol in symbols:
        event = fetch_ohlcv(symbol)
        if isinstance(event, dict):
            events.append(event)
        time.sleep(2.0)
    return events


def fetch_news(symbol: str, max_items: int = 5) -> list[dict[str, Any]]:
    """Fetch recent news articles for a symbol from Yahoo Finance."""

    def _fetch() -> list[dict[str, Any]]:
        response = _SESSION.get(
            SEARCH_URL,
            params={
                "q": _yahoo_ticker(symbol),
                "newsCount": max_items,
                "quotesCount": 0,
            },
            timeout=20,
        )
        response.raise_for_status()
        raw_news = response.json().get("news") or []
        events: list[dict[str, Any]] = []

        for item in raw_news[:max_items]:
            news_id = item.get("uuid") or item.get("id") or item.get("link")
            title = item.get("title", "")
            if not news_id or not title:
                continue

            pub_time = item.get("providerPublishTime") or item.get("pubDate")
            if isinstance(pub_time, (int, float)):
                published_at = datetime.fromtimestamp(pub_time, tz=timezone.utc).isoformat()
            elif isinstance(pub_time, str):
                published_at = pub_time
            else:
                published_at = datetime.now(timezone.utc).isoformat()

            events.append(
                {
                    "event_type": "news",
                    "news_id": str(news_id),
                    "symbol": symbol,
                    "title": title,
                    "publisher": item.get("publisher", ""),
                    "link": item.get("link", ""),
                    "summary": item.get("summary", "") or item.get("description", ""),
                    "published_at": published_at,
                }
            )

        return events

    return _with_retries("fetch news", symbol, _fetch)
