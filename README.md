# AI-Based Trading Signal Platform

Phase 1 of a trading signal platform. This repo implements the data ingestion layer: real market data and news are collected from Yahoo Finance, streamed through Kafka, and stored in PostgreSQL.

## Overview

The pipeline simulates the first step of a larger system where ML models will later generate trading signals from market data, news, and social sentiment.

```
Yahoo Finance API
       │
       ▼
  Python Producer ──► Kafka ──► Python Consumer ──► PostgreSQL
```

**What works in this phase:**
- Real OHLCV price data (Yahoo Finance)
- Market news per symbol (Yahoo Finance)
- Twitter ingestion is implemented but optional (requires paid X API token)

**Symbols tracked:** AAPL, MSFT, GOOGL, TSLA, BTC-USD, ETH-USD, EUR-USD

## Tech Stack

- Python 3.11
- Apache Kafka + Zookeeper (Docker)
- PostgreSQL 15 (Docker)
- `confluent-kafka`, `psycopg2`, `requests`

## Database

Tables are linked through a `symbols` reference table:

- `symbols` — list of tracked tickers
- `market_events` — OHLCV price data
- `market_news` — news articles
- `market_tweets` — tweets (empty if Twitter is not configured)
- `v_ml_features` — view that joins prices with news/social counts per symbol and 1-hour window

## Setup

### Requirements

- Docker Desktop
- Python 3.11+

### 1. Environment

```powershell
Copy-Item .env.example .env
```

Default values work for local development. Postgres runs on port **5433** (not 5432) to avoid conflicts with a local PostgreSQL installation.

### 2. Start Docker services

```powershell
docker compose up -d
```

### 3. Python dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Run the pipeline

Start the consumer first, then the producer (two separate terminals):

```powershell
python -m src.consumer.market_consumer
```

```powershell
python -m src.producer.market_producer
```

## Verify the data

**Command line:**

```powershell
docker exec trading-postgres psql -U trading -d trading_signals -c "SELECT symbol, close, timestamp FROM market_events ORDER BY timestamp DESC LIMIT 10;"
```

**pgAdmin connection:**

| Field    | Value            |
|----------|------------------|
| Host     | localhost        |
| Port     | 5433             |
| Database | trading_signals  |
| User     | trading          |
| Password | trading          |

Tables are under: `trading_signals` → Schemas → public → Tables

Example query:

```sql
SELECT symbol, price_time, close, news_count_1h
FROM v_ml_features
ORDER BY price_time DESC
LIMIT 20;
```

## Project structure

```
├── docker-compose.yml
├── src/
│   ├── config.py
│   ├── sources/          # Yahoo + Twitter fetchers
│   ├── producer/         # Publishes to Kafka
│   └── consumer/         # Writes to PostgreSQL
├── sql/
│   └── init.sql          # Database schema
└── scripts/
    ├── wait_for_kafka.py
    └── create_kafka_topics.py
```

## Kafka topics

| Topic           | Data        |
|-----------------|-------------|
| market.raw      | OHLCV       |
| market.news     | News        |
| market.social   | Tweets      |

## Stop services

```powershell
docker compose down
```

## Known issues

- Yahoo Finance may rate-limit if too many requests are sent quickly
- Twitter API is pay-per-use; left disabled in `.env` by default
- Consumer must be started before producer on first run

## Next steps

- Sentiment analysis on news (FinBERT)
- ML feature table with price-return labels
- Dockerize producer and consumer
- Dashboard and cloud deployment
