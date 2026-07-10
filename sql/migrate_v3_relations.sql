-- Add relational structure for ML: symbols dimension + foreign keys + ML view.
-- Run: Get-Content sql\migrate_v3_relations.sql | docker exec -i trading-postgres psql -U trading -d trading_signals

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

-- Ensure all existing rows use known symbols
INSERT INTO symbols (symbol, name, asset_type)
SELECT DISTINCT e.symbol, e.symbol, 'stock'
FROM market_events e
WHERE e.symbol NOT IN (SELECT symbol FROM symbols)
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO symbols (symbol, name, asset_type)
SELECT DISTINCT n.symbol, n.symbol, 'stock'
FROM market_news n
WHERE n.symbol NOT IN (SELECT symbol FROM symbols)
ON CONFLICT (symbol) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_market_events_symbol'
    ) THEN
        ALTER TABLE market_events
            ADD CONSTRAINT fk_market_events_symbol
            FOREIGN KEY (symbol) REFERENCES symbols(symbol);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_market_news_symbol'
    ) THEN
        ALTER TABLE market_news
            ADD CONSTRAINT fk_market_news_symbol
            FOREIGN KEY (symbol) REFERENCES symbols(symbol);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_market_tweets_symbol'
    ) THEN
        ALTER TABLE market_tweets
            ADD CONSTRAINT fk_market_tweets_symbol
            FOREIGN KEY (symbol) REFERENCES symbols(symbol);
    END IF;
END $$;

-- ML-ready view: one price row with related news/tweet counts in a 1-hour window
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
    'Silver-layer view joining prices with news/social counts by symbol and 1-hour time window.';
