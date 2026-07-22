# AI-Based Trading Signal Platform

Trading signal platform built as a semester project. The goal is to collect real market data, enrich it with technical indicators and news sentiment, and prepare labeled datasets for a machine learning model that will generate BUY/SELL/HOLD signals.

## Current status

| Layer | Description | Status |
|-------|-------------|--------|
| Bronze | Yahoo Finance prices + news via Kafka → PostgreSQL | Done |
| Silver | Technical indicators + FinBERT news sentiment | Done |
| Gold | BUY/SELL/HOLD labels from future returns | Done |
| ML model | Train classifier on `ml_training_data` | Planned |

**Symbols:** AAPL, MSFT, GOOGL, TSLA, BTC-USD, ETH-USD, EUR-USD

**AI model used so far:** [FinBERT](https://huggingface.co/ProsusAI/finbert) (`ProsusAI/finbert`) for financial news sentiment.

## Architecture

```
Yahoo Finance
      │
      ▼
 Producer ──► Kafka ──► Consumer ──► PostgreSQL (bronze)
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             market_events        market_news          market_tweets
                    │                    │
                    └──────────┬─────────┘
                               ▼
                    processed_features (silver)
                    RSI, MACD, SMA, returns, sentiment
                               │
                               ▼
                    ml_training_data (gold)
                    features + BUY/SELL/HOLD label
```

## Tech stack

- Python 3.11
- Apache Kafka + Zookeeper (Docker)
- PostgreSQL 15 (Docker)
- pandas, numpy — indicators and feature pipeline
- PyTorch + Hugging Face Transformers — FinBERT inference
- confluent-kafka, psycopg2, requests

## Setup

**Requirements:** Docker Desktop, Python 3.11+

```powershell
Copy-Item .env.example .env
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Postgres runs on port **5433** (not 5432) to avoid conflicts with a local PostgreSQL install.

On first `docker compose up`, `sql/init.sql` creates the full schema automatically.

## Run the pipeline

Start the **consumer first**, then the **producer** (two terminals):

```powershell
python -m src.consumer.market_consumer
python -m src.producer.market_producer
```

Let them run until each symbol has enough rows (~20+ for indicators).

Then run the processing jobs in order:

```powershell
python -m src.processing.run_features
python -m src.processing.run_sentiment
python -m src.processing.run_features
python -m src.processing.run_labels
```

`run_features` is executed twice: once for technical indicators, then again after sentiment scoring to fill `news_sentiment_avg_1h`.

### Existing database (created before silver/gold tables)

If the Postgres volume already existed from an earlier version, apply migrations:

```powershell
Get-Content sql\silver_features.sql | docker exec -i trading-postgres psql -U trading -d trading_signals
Get-Content sql\silver_sentiment.sql | docker exec -i trading-postgres psql -U trading -d trading_signals
Get-Content sql\silver_labels.sql | docker exec -i trading-postgres psql -U trading -d trading_signals
```

## Database

| Table / view | Layer | Content |
|--------------|-------|---------|
| `symbols` | Reference | Tracked tickers |
| `market_events` | Bronze | OHLCV prices |
| `market_news` | Bronze | News headlines + FinBERT scores |
| `market_tweets` | Bronze | Tweets (optional, needs X API token) |
| `processed_features` | Silver | Indicators + news context |
| `ml_training_data` | Gold | Features + label for ML training |
| `v_ml_features` | View | Prices joined with news/tweet counts |

Foreign keys link all event tables to `symbols(symbol)`.

### Label rules (default)

Configured in `.env`:

- **BUY** — future return ≥ +2%
- **SELL** — future return ≤ −2%
- **HOLD** — anything in between
- Lookahead: 5 price rows per symbol

### pgAdmin connection

| Field | Value |
|-------|-------|
| Host | localhost |
| Port | 5433 |
| Database | trading_signals |
| User | trading |
| Password | trading |

Example checks:

```sql
SELECT symbol, close, timestamp FROM market_events ORDER BY timestamp DESC LIMIT 10;

SELECT symbol, timestamp, close, rsi_14, sma_20, macd, news_sentiment_avg_1h
FROM processed_features ORDER BY timestamp DESC LIMIT 10;

SELECT label, COUNT(*) FROM ml_training_data GROUP BY label;
```

## Project structure

```
├── docker-compose.yml
├── src/
│   ├── config.py
│   ├── sources/           # Yahoo Finance + Twitter fetchers
│   ├── producer/          # Publishes to Kafka
│   ├── consumer/          # Writes to PostgreSQL
│   └── processing/        # Features, sentiment, labels
├── sql/
│   ├── init.sql
│   ├── silver_features.sql
│   ├── silver_sentiment.sql
│   └── silver_labels.sql
└── scripts/
    ├── wait_for_kafka.py
    └── create_kafka_topics.py
```

## Kafka topics

| Topic | Data |
|-------|------|
| `market.raw` | OHLCV prices |
| `market.news` | News articles |
| `market.social` | Tweets |

## Stop services

```powershell
docker compose down
```

## Known issues

- Yahoo Finance may rate-limit if requests are sent too quickly
- Twitter/X API is pay-per-use — left disabled by default (`TWITTER_BEARER_TOKEN` empty)
- Consumer should be started before the producer on first run
- FinBERT first run downloads ~400MB model weights + PyTorch dependencies

## Next steps

- Train a classifier (XGBoost or Random Forest) on `ml_training_data`
- Store predictions in a `trading_signals` table
- API + dashboard for live signals
