import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import declarative_base, sessionmaker


# Load backend/.env without overriding explicitly supplied process variables.
load_dotenv()


# MySQL database configuration.
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "cargopilot")
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()


# Safety barrier: test-mode processes must never point at the live/dev DB.
if APP_ENV in {"test", "testing"} and not DB_NAME.lower().endswith("_test"):
    raise RuntimeError(
        "Refusing to start in test mode: DB_NAME must end with '_test'. "
        "Create and configure a separate disposable test database."
    )


# Verify required database settings.
if not DB_USER or not DB_PASSWORD:
    raise RuntimeError(
        "DB_USER and DB_PASSWORD must be configured in backend/.env."
    )


# Build the connection URL safely (credentials are not string-concatenated).
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)


# SQL logging is opt-in; pre-ping detects stale pooled MySQL connections.
SQL_ECHO = os.getenv("SQL_ECHO", "false").strip().lower() in {
    "1", "true", "yes", "on"
}

engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


def get_db():
    """Yield one request-scoped SQLAlchemy session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
