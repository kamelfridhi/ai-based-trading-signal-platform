# AI-Based Trading Signal Platform

Trading signal platform built as a semester project. The goal is to collect real market data, enrich it with technical indicators and news sentiment, and prepare labeled datasets for a machine learning model that will generate BUY/SELL/HOLD signals.

## Current status

| Layer | Description | Status |
|-------|-------------|--------|
| Bronze | Yahoo Finance prices + news via Kafka → PostgreSQL | Done |
| Silver | Technical indicators + FinBERT news sentiment | Done |
| Gold | BUY/SELL/HOLD labels from future returns | Done |
| ML model | BiLSTM + attention classifier on sequences | Done |
| Signals | `trading_signals` (confidence ≥ 0.8) | Done |
| API | FastAPI + OpenAPI docs | Done |
| Dashboard | React + Vite UI (`dashboard/`) | Done |

**Symbols:** AAPL, MSFT, GOOGL, TSLA, BTC-USD, ETH-USD, EUR-USD

**Models:** [FinBERT](https://huggingface.co/ProsusAI/finbert) for news sentiment; PyTorch **BiLSTM + temporal attention** for BUY/SELL/HOLD (sequence classifier).

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
                               │
                               ▼
                    model_runs + trading_signals
                    sequence classifier predictions
```

## Tech stack

- Python 3.11
- Apache Kafka + Zookeeper (Docker)
- PostgreSQL 15 (Docker)
- pandas, numpy — indicators and feature pipeline
- PyTorch + Hugging Face Transformers — FinBERT inference
- FastAPI + uvicorn — REST API
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
Get-Content sql\gold_signals.sql | docker exec -i trading-postgres psql -U trading -d trading_signals
```

## Phase 3 — Sequence classifier

Train a **BiLSTM with temporal attention** on sliding windows from `ml_training_data` (default window: 24 timesteps). Evaluation uses a **time-based train/test split** (no random shuffle). Predictions are written to `trading_signals` only when **confidence ≥ 0.8** (`ML_SIGNAL_CONFIDENCE`).

```powershell
pip install -r requirements.txt
python -m src.ml.run_train
python -m src.ml.run_predict
```

Check results:

```sql
SELECT id, metrics->>'macro_f1' AS macro_f1, trained_at
FROM model_runs ORDER BY trained_at DESC LIMIT 1;

SELECT symbol, timestamp, predicted_label, confidence, prob_buy, prob_sell, prob_hold
FROM trading_signals ORDER BY created_at DESC LIMIT 20;
```

Checkpoints are saved under `models/checkpoints/` (not committed to git).

## Phase 4 — FastAPI

Start the API (Postgres must be running):

```powershell
pip install -r requirements.txt
python -m src.api.run_server
```

Interactive docs: **http://localhost:8000/docs**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | API + database check |
| GET | `/api/v1/signals` | List signals (filters: `symbol`, `label`, `min_confidence`) |
| GET | `/api/v1/signals/latest` | Latest signal per symbol |
| GET | `/api/v1/models/latest` | Latest training run + metrics |
| GET | `/api/v1/prices/latest` | Latest close per symbol |
| GET | `/api/v1/analytics/{symbol}` | On-demand prediction + RSI/MACD/sentiment/news |
| POST | `/api/v1/pipeline/train` | Start training job (202, background) |
| POST | `/api/v1/pipeline/predict` | Start predict job (202, background) |
| GET | `/api/v1/pipeline/jobs/{job_id}` | Job status and result |

Pipeline jobs run in a **single background worker** (one train or predict at a time). Poll the job URL until `status` is `completed` or `failed`.

```powershell
curl http://localhost:8000/api/v1/signals/latest
```

## Phase 5 — React dashboard

Modern dark UI with live signals, prices, model metrics, probability bars, and pipeline controls.

**Terminal 1 — API:**

```powershell
python -m src.api.run_server
```

**Terminal 2 — Dashboard:**

```powershell
cd dashboard
npm install
npm run dev
```

Open **http://localhost:5173**. See `dashboard/README.md` for build details.

## Database

| Table / view | Layer | Content |
|--------------|-------|---------|
| `symbols` | Reference | Tracked tickers |
| `market_events` | Bronze | OHLCV prices |
| `market_news` | Bronze | News headlines + FinBERT scores |
| `market_tweets` | Bronze | Tweets (optional, needs X API token) |
| `processed_features` | Silver | Indicators + news context |
| `ml_training_data` | Gold | Features + label for ML training |
| `model_runs` | Serving | Training metrics + checkpoint path |
| `trading_signals` | Serving | High-confidence predictions |
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
│   ├── processing/        # Features, sentiment, labels
│   ├── ml/                # Train + predict sequence model
│   └── api/               # FastAPI routes
├── dashboard/             # React + Vite UI
├── sql/
│   ├── init.sql
│   ├── silver_features.sql
│   ├── silver_sentiment.sql
│   ├── silver_labels.sql
│   └── gold_signals.sql
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

- Push Phases 3–5 to GitHub
- Paper auto-trading (deferred)
- More ingestion data to improve BUY/SELL recall
