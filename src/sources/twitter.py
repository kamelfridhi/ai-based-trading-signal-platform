"""Twitter/X search for symbol-related tweets."""

from __future__ import annotations

import logging
from typing import Any

import tweepy

from src.config import TWITTER_BEARER_TOKEN

logger = logging.getLogger(__name__)


def _twitter_query(symbol: str) -> str:
    """Build a search query for tweets related to a symbol."""
    base = symbol.replace("-USD", "").replace("-", "")
    if symbol.endswith("-USD") and len(base) <= 5:
        return f"(${base} OR #{base}) -is:retweet lang:en"
    return f"(${symbol} OR #{symbol}) -is:retweet lang:en"


def fetch_tweets(symbol: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Search recent tweets related to a symbol via the Twitter API v2."""
    if not TWITTER_BEARER_TOKEN:
        return []

    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        response = client.search_recent_tweets(
            query=_twitter_query(symbol),
            max_results=max(min(max_results, 100), 10),
            tweet_fields=["created_at", "public_metrics", "author_id"],
            expansions=["author_id"],
            user_fields=["username"],
        )
        if not response.data:
            return []

        users: dict[int, str] = {}
        if response.includes and response.includes.get("users"):
            users = {user.id: user.username for user in response.includes["users"]}

        events: list[dict[str, Any]] = []
        for tweet in response.data:
            metrics = tweet.public_metrics or {}
            created_at = None
            if tweet.created_at:
                created_at = tweet.created_at.astimezone().isoformat()

            events.append(
                {
                    "event_type": "tweet",
                    "tweet_id": str(tweet.id),
                    "symbol": symbol,
                    "author": users.get(tweet.author_id, str(tweet.author_id)),
                    "text": tweet.text,
                    "created_at": created_at,
                    "retweet_count": metrics.get("retweet_count", 0),
                    "like_count": metrics.get("like_count", 0),
                }
            )

        return events
    except tweepy.TweepyException as exc:
        logger.error("Twitter API error for %s: %s", symbol, exc)
        return []
    except Exception as exc:
        logger.error("Failed to fetch tweets for %s: %s", symbol, exc)
        return []
