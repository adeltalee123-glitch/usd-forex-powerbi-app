from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "forex.db"


PAIR_CATALOG = [
    ("AUD/USD", "Australian Dollar vs US Dollar"),
    ("EUR/USD", "Euro vs US Dollar"),
    ("GBP/USD", "Pound Sterling vs US Dollar"),
    ("NZD/USD", "New Zealand Dollar vs US Dollar"),
    ("USD/CAD", "US Dollar vs Canadian Dollar"),
    ("USD/CHF", "US Dollar vs Swiss Franc"),
    ("USD/CNH", "US Dollar vs Chinese Yuan"),
    ("USD/CZK", "US Dollar vs Czech Koruna"),
    ("USD/DKK", "US Dollar vs Danish Krone"),
    ("USD/HKD", "US Dollar vs Hong Kong Dollar"),
    ("USD/HUF", "US Dollar vs Hungarian Forint"),
    ("USD/ILS", "US Dollar vs Israeli Shekel"),
    ("USD/JPY", "US Dollar vs Yen"),
    ("USD/MXN", "US Dollar vs Mexican Peso"),
    ("USD/NOK", "US Dollar vs Norwegian Krone"),
    ("USD/PLN", "US Dollar vs Zloty"),
    ("USD/RON", "US Dollar vs Romanian Leu"),
    ("USD/SEK", "US Dollar vs Swedish Krona"),
    ("USD/SGD", "US Dollar vs Singapore Dollar"),
    ("USD/THB", "US Dollar vs Thai Baht"),
    ("USD/TRY", "US Dollar vs Turkish Lira"),
    ("USD/ZAR", "US Dollar vs Rand"),
]


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pair_catalog (
                pair TEXT PRIMARY KEY,
                pair_name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS forex_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL,
                granularity TEXT NOT NULL DEFAULT 'daily',
                source TEXT NOT NULL DEFAULT 'Dukascopy',
                loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (pair, timestamp_utc, granularity),
                FOREIGN KEY (pair) REFERENCES pair_catalog(pair)
            );

            CREATE TABLE IF NOT EXISTS update_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                pair TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT NOT NULL,
                records_inserted INTEGER NOT NULL DEFAULT 0,
                message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_forex_prices_pair
            ON forex_prices(pair);

            CREATE INDEX IF NOT EXISTS idx_forex_prices_timestamp
            ON forex_prices(timestamp_utc);

            CREATE INDEX IF NOT EXISTS idx_forex_prices_pair_timestamp
            ON forex_prices(pair, timestamp_utc);
            """
        )


def seed_pair_catalog() -> None:
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO pair_catalog (pair, pair_name)
            VALUES (?, ?)
            ON CONFLICT(pair) DO UPDATE SET pair_name = excluded.pair_name
            """,
            PAIR_CATALOG,
        )
