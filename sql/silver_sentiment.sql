-- FinBERT sentiment columns
-- CMD: type sql\silver_sentiment.sql | docker exec -i trading-postgres psql -U trading -d trading_signals

ALTER TABLE market_news
    ADD COLUMN IF NOT EXISTS sentiment_label VARCHAR(20),
    ADD COLUMN IF NOT EXISTS sentiment_score NUMERIC(18, 8),
    ADD COLUMN IF NOT EXISTS sentiment_value NUMERIC(18, 8);

ALTER TABLE processed_features
    ADD COLUMN IF NOT EXISTS news_sentiment_avg_1h NUMERIC(18, 8);

COMMENT ON COLUMN market_news.sentiment_label IS 'FinBERT label: positive, negative, or neutral.';
COMMENT ON COLUMN market_news.sentiment_value IS 'Numeric sentiment from -1 (negative) to +1 (positive).';
COMMENT ON COLUMN processed_features.news_sentiment_avg_1h IS 'Average news sentiment in the 1-hour window before timestamp.';
