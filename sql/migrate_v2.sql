-- Run this if you already have a Postgres volume from Phase 1 (init.sql only runs on first boot).
-- docker exec -i trading-postgres psql -U trading -d trading_signals < sql/migrate_v2.sql

CREATE TABLE IF NOT EXISTS market_news (
    id           SERIAL PRIMARY KEY,
    news_id      VARCHAR(255)   NOT NULL UNIQUE,
    symbol       VARCHAR(20)    NOT NULL,
    title        TEXT           NOT NULL,
    publisher    VARCHAR(255),
    link         TEXT,
    summary      TEXT,
    published_at TIMESTAMPTZ    NOT NULL,
    ingested_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_news_symbol
    ON market_news (symbol);

CREATE INDEX IF NOT EXISTS idx_market_news_published_at
    ON market_news (published_at DESC);

CREATE TABLE IF NOT EXISTS market_tweets (
    id            SERIAL PRIMARY KEY,
    tweet_id      VARCHAR(50)    NOT NULL UNIQUE,
    symbol        VARCHAR(20)    NOT NULL,
    author        VARCHAR(255),
    text          TEXT           NOT NULL,
    created_at    TIMESTAMPTZ,
    retweet_count INTEGER        NOT NULL DEFAULT 0,
    like_count    INTEGER        NOT NULL DEFAULT 0,
    ingested_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_tweets_symbol
    ON market_tweets (symbol);

CREATE INDEX IF NOT EXISTS idx_market_tweets_created_at
    ON market_tweets (created_at DESC);
