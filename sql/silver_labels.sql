-- ML training labels (BUY / SELL / HOLD)
-- CMD: type sql\silver_labels.sql | docker exec -i trading-postgres psql -U trading -d trading_signals

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
