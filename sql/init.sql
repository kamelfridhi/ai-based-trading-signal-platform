-- Reference table: tracked symbols
CREATE TABLE IF NOT EXISTS symbols (
    symbol      VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    asset_type  VARCHAR(20)  NOT NULL CHECK (asset_type IN ('stock', 'crypto', 'forex'))
);

INSERT INTO symbols (symbol, name, asset_type) VALUES
    ('AAPL',    'Apple Inc',           'stock'),
    ('MSFT',    'Microsoft Corp',      'stock'),
    ('GOOGL',   'Alphabet Inc',        'stock'),
    ('TSLA',    'Tesla Inc',           'stock'),
    ('BTC-USD', 'Bitcoin USD',         'crypto'),
    ('ETH-USD', 'Ethereum USD',        'crypto'),
    ('EUR-USD', 'Euro / US Dollar',    'forex')
ON CONFLICT (symbol) DO NOTHING;

-- Bronze layer: raw market events ingested from Kafka
CREATE TABLE IF NOT EXISTS market_events (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)    NOT NULL REFERENCES symbols(symbol),
    timestamp   TIMESTAMPTZ    NOT NULL,
    open        NUMERIC(18, 8) NOT NULL,
    high        NUMERIC(18, 8) NOT NULL,
    low         NUMERIC(18, 8) NOT NULL,
    close       NUMERIC(18, 8) NOT NULL,
    volume      NUMERIC(24, 8) NOT NULL,
    ingested_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_events_symbol
    ON market_events (symbol);

CREATE INDEX IF NOT EXISTS idx_market_events_timestamp
    ON market_events (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_market_events_ingested_at
    ON market_events (ingested_at DESC);

-- Bronze layer: market news from Yahoo Finance
CREATE TABLE IF NOT EXISTS market_news (
    id           SERIAL PRIMARY KEY,
    news_id      VARCHAR(255)   NOT NULL UNIQUE,
    symbol       VARCHAR(20)    NOT NULL REFERENCES symbols(symbol),
    title        TEXT           NOT NULL,
    publisher    VARCHAR(255),
    link         TEXT,
    summary      TEXT,
    published_at TIMESTAMPTZ    NOT NULL,
    ingested_at  TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    sentiment_label VARCHAR(20),
    sentiment_score NUMERIC(18, 8),
    sentiment_value NUMERIC(18, 8)
);

CREATE INDEX IF NOT EXISTS idx_market_news_symbol
    ON market_news (symbol);

CREATE INDEX IF NOT EXISTS idx_market_news_published_at
    ON market_news (published_at DESC);

-- Bronze layer: symbol-related tweets from Twitter/X
CREATE TABLE IF NOT EXISTS market_tweets (
    id            SERIAL PRIMARY KEY,
    tweet_id      VARCHAR(50)    NOT NULL UNIQUE,
    symbol        VARCHAR(20)    NOT NULL REFERENCES symbols(symbol),
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

-- Silver layer: ML-ready view joining prices with news/social counts
CREATE OR REPLACE VIEW v_ml_features AS
SELECT
    m.id                                            AS event_id,
    m.symbol,
    s.name                                          AS symbol_name,
    s.asset_type,
    m.timestamp                                     AS price_time,
    m.open,
    m.high,
    m.low,
    m.close,
    m.volume,
    COALESCE(news.news_count, 0)                    AS news_count_1h,
    COALESCE(news.latest_news_title, '')            AS latest_news_title,
    COALESCE(tweets.tweet_count, 0)                 AS tweet_count_1h,
    COALESCE(tweets.total_likes, 0)                 AS tweet_likes_1h,
    m.ingested_at
FROM market_events m
JOIN symbols s
    ON m.symbol = s.symbol
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)                                    AS news_count,
        MAX(n.title)                                AS latest_news_title
    FROM market_news n
    WHERE n.symbol = m.symbol
      AND n.published_at BETWEEN m.timestamp - INTERVAL '1 hour' AND m.timestamp
) news ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)                                    AS tweet_count,
        SUM(t.like_count)                           AS total_likes
    FROM market_tweets t
    WHERE t.symbol = m.symbol
      AND t.created_at BETWEEN m.timestamp - INTERVAL '1 hour' AND m.timestamp
) tweets ON TRUE;

COMMENT ON VIEW v_ml_features IS
    'Joins prices with news/social counts by symbol and 1-hour time window.';

-- Engineered features (silver layer)
CREATE TABLE IF NOT EXISTS processed_features (
    id                  SERIAL PRIMARY KEY,
    symbol              VARCHAR(20)    NOT NULL REFERENCES symbols(symbol),
    timestamp           TIMESTAMPTZ    NOT NULL,
    close               NUMERIC(18, 8) NOT NULL,
    volume              NUMERIC(24, 8) NOT NULL,
    return_1            NUMERIC(18, 8),
    return_5            NUMERIC(18, 8),
    return_15           NUMERIC(18, 8),
    sma_10              NUMERIC(18, 8),
    sma_20              NUMERIC(18, 8),
    rsi_14              NUMERIC(18, 8),
    macd                NUMERIC(18, 8),
    macd_signal         NUMERIC(18, 8),
    volume_change_pct   NUMERIC(18, 8),
    news_count_1h       INTEGER        NOT NULL DEFAULT 0,
    news_sentiment_avg_1h NUMERIC(18, 8),
    processed_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_processed_features_symbol
    ON processed_features (symbol);

CREATE INDEX IF NOT EXISTS idx_processed_features_timestamp
    ON processed_features (timestamp DESC);

COMMENT ON TABLE processed_features IS
    'Silver layer: technical indicators and news context per symbol and timestamp.';

-- ML training data with labels (gold layer)
CREATE TABLE IF NOT EXISTS ml_training_data (
    id                      SERIAL PRIMARY KEY,
    symbol                  VARCHAR(20)    NOT NULL REFERENCES symbols(symbol),
    timestamp               TIMESTAMPTZ    NOT NULL,
    close                   NUMERIC(18, 8) NOT NULL,
    volume                  NUMERIC(24, 8) NOT NULL,
    return_1                NUMERIC(18, 8),
    return_5                NUMERIC(18, 8),
    return_15               NUMERIC(18, 8),
    sma_10                  NUMERIC(18, 8),
    sma_20                  NUMERIC(18, 8),
    rsi_14                  NUMERIC(18, 8),
    macd                    NUMERIC(18, 8),
    macd_signal             NUMERIC(18, 8),
    volume_change_pct       NUMERIC(18, 8),
    news_count_1h           INTEGER        NOT NULL DEFAULT 0,
    news_sentiment_avg_1h   NUMERIC(18, 8),
    future_close            NUMERIC(18, 8) NOT NULL,
    future_return_pct       NUMERIC(18, 8) NOT NULL,
    label                   VARCHAR(10)    NOT NULL CHECK (label IN ('BUY', 'SELL', 'HOLD')),
    labeled_at              TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_ml_training_data_symbol
    ON ml_training_data (symbol);

CREATE INDEX IF NOT EXISTS idx_ml_training_data_label
    ON ml_training_data (label);

CREATE INDEX IF NOT EXISTS idx_ml_training_data_timestamp
    ON ml_training_data (timestamp DESC);

COMMENT ON TABLE ml_training_data IS
    'Gold layer: processed features with future-return labels for ML training.';
