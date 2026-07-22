-- Engineered features for ML
-- Run on existing DB: Get-Content sql\silver_features.sql | docker exec -i trading-postgres psql -U trading -d trading_signals

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
    processed_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_processed_features_symbol
    ON processed_features (symbol);

CREATE INDEX IF NOT EXISTS idx_processed_features_timestamp
    ON processed_features (timestamp DESC);

COMMENT ON TABLE processed_features IS
    'Silver layer: technical indicators and news context per symbol and timestamp.';
