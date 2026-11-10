-- Phase 3: model training runs and trading signals

CREATE TABLE IF NOT EXISTS model_runs (
    id              SERIAL PRIMARY KEY,
    model_path      TEXT           NOT NULL,
    hyperparams     JSONB          NOT NULL DEFAULT '{}',
    metrics         JSONB          NOT NULL DEFAULT '{}',
    trained_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trading_signals (
    id              SERIAL PRIMARY KEY,
    model_run_id    INTEGER        NOT NULL REFERENCES model_runs(id) ON DELETE CASCADE,
    symbol          VARCHAR(20)    NOT NULL REFERENCES symbols(symbol),
    timestamp       TIMESTAMPTZ    NOT NULL,
    predicted_label VARCHAR(10)    NOT NULL CHECK (predicted_label IN ('BUY', 'SELL', 'HOLD')),
    prob_buy        NUMERIC(8, 6)  NOT NULL,
    prob_sell       NUMERIC(8, 6)  NOT NULL,
    prob_hold       NUMERIC(8, 6)  NOT NULL,
    confidence      NUMERIC(8, 6)  NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    UNIQUE (model_run_id, symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol
    ON trading_signals (symbol);

CREATE INDEX IF NOT EXISTS idx_trading_signals_timestamp
    ON trading_signals (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trading_signals_label
    ON trading_signals (predicted_label);

COMMENT ON TABLE model_runs IS 'Registered ML training runs and stored checkpoint paths.';
COMMENT ON TABLE trading_signals IS 'Predictions from the sequence classifier (confidence >= threshold).';
