"""Central configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC: str = os.getenv("KAFKA_TOPIC", "market.raw")
KAFKA_NEWS_TOPIC: str = os.getenv("KAFKA_NEWS_TOPIC", "market.news")
KAFKA_SOCIAL_TOPIC: str = os.getenv("KAFKA_SOCIAL_TOPIC", "market.social")

POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5433"))
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "trading")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "trading")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "trading_signals")

SYMBOLS: list[str] = [
    s.strip()
    for s in os.getenv(
        "SYMBOLS", "AAPL,MSFT,GOOGL,TSLA,BTC-USD,ETH-USD,EUR-USD"
    ).split(",")
    if s.strip()
]

PRODUCER_INTERVAL_SECONDS: float = float(os.getenv("PRODUCER_INTERVAL_SECONDS", "30"))
NEWS_INTERVAL_SECONDS: float = float(os.getenv("NEWS_INTERVAL_SECONDS", "300"))
TWEET_INTERVAL_SECONDS: float = float(os.getenv("TWEET_INTERVAL_SECONDS", "120"))

NEWS_MAX_PER_SYMBOL: int = int(os.getenv("NEWS_MAX_PER_SYMBOL", "5"))
TWEETS_MAX_PER_SYMBOL: int = int(os.getenv("TWEETS_MAX_PER_SYMBOL", "10"))

TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")

MIN_ROWS_FOR_FEATURES: int = int(os.getenv("MIN_ROWS_FOR_FEATURES", "20"))

FINBERT_MODEL: str = os.getenv("FINBERT_MODEL", "ProsusAI/finbert")
SENTIMENT_BATCH_SIZE: int = int(os.getenv("SENTIMENT_BATCH_SIZE", "16"))

LABEL_LOOKAHEAD_ROWS: int = int(os.getenv("LABEL_LOOKAHEAD_ROWS", "5"))
LABEL_BUY_THRESHOLD: float = float(os.getenv("LABEL_BUY_THRESHOLD", "2.0"))
LABEL_SELL_THRESHOLD: float = float(os.getenv("LABEL_SELL_THRESHOLD", "-2.0"))

ML_WINDOW_SIZE: int = int(os.getenv("ML_WINDOW_SIZE", "24"))
ML_TRAIN_RATIO: float = float(os.getenv("ML_TRAIN_RATIO", "0.8"))
ML_HIDDEN_SIZE: int = int(os.getenv("ML_HIDDEN_SIZE", "64"))
ML_NUM_LAYERS: int = int(os.getenv("ML_NUM_LAYERS", "2"))
ML_SYMBOL_EMBED_DIM: int = int(os.getenv("ML_SYMBOL_EMBED_DIM", "8"))
ML_DROPOUT: float = float(os.getenv("ML_DROPOUT", "0.3"))
ML_BATCH_SIZE: int = int(os.getenv("ML_BATCH_SIZE", "32"))
ML_EPOCHS: int = int(os.getenv("ML_EPOCHS", "50"))
ML_LEARNING_RATE: float = float(os.getenv("ML_LEARNING_RATE", "0.001"))
ML_FOCAL_GAMMA: float = float(os.getenv("ML_FOCAL_GAMMA", "2.0"))
ML_EARLY_STOP_PATIENCE: int = int(os.getenv("ML_EARLY_STOP_PATIENCE", "8"))
ML_SIGNAL_CONFIDENCE: float = float(os.getenv("ML_SIGNAL_CONFIDENCE", "0.8"))
ML_MODELS_DIR: str = os.getenv("ML_MODELS_DIR", "models/checkpoints")

API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv(
        "API_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

LABEL_TO_INDEX = {"BUY": 0, "SELL": 1, "HOLD": 2}
INDEX_TO_LABEL = {0: "BUY", 1: "SELL", 2: "HOLD"}


def postgres_dsn() -> str:
    """Return a PostgreSQL connection string."""
    return (
        f"host={POSTGRES_HOST} "
        f"port={POSTGRES_PORT} "
        f"dbname={POSTGRES_DB} "
        f"user={POSTGRES_USER} "
        f"password={POSTGRES_PASSWORD}"
    )
