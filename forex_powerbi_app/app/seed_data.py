from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from .database import PAIR_CATALOG, get_connection, initialize_database, seed_pair_catalog


BASE_PRICES = {
    "AUD/USD": 0.66,
    "EUR/USD": 1.09,
    "GBP/USD": 1.28,
    "NZD/USD": 0.61,
    "USD/CAD": 1.35,
    "USD/CHF": 0.89,
    "USD/CNH": 7.18,
    "USD/CZK": 23.15,
    "USD/DKK": 6.95,
    "USD/HKD": 7.81,
    "USD/HUF": 360.0,
    "USD/ILS": 3.65,
    "USD/JPY": 149.5,
    "USD/MXN": 16.9,
    "USD/NOK": 10.6,
    "USD/PLN": 3.98,
    "USD/RON": 4.56,
    "USD/SEK": 10.4,
    "USD/SGD": 1.34,
    "USD/THB": 35.8,
    "USD/TRY": 32.2,
    "USD/ZAR": 18.4,
}


def build_daily_rows(days: int = 365 * 5) -> list[tuple]:
    rows: list[tuple] = []
    end_day = date.today()
    start_day = end_day - timedelta(days=days - 1)

    for pair, _pair_name in PAIR_CATALOG:
        base_price = BASE_PRICES[pair]
        pair_seed = sum(ord(char) for char in pair)

        for offset in range(days):
            current_day = start_day + timedelta(days=offset)
            timestamp_utc = datetime.combine(current_day, datetime.min.time()).isoformat() + "Z"

            seasonal = math.sin((offset + pair_seed) / 18.0) * 0.012
            drift = (offset / days) * 0.015
            wave = math.cos((offset + pair_seed) / 7.0) * 0.004

            close_price = base_price * (1 + seasonal + drift + wave)
            open_price = close_price * (1 - 0.0025)
            high_price = close_price * (1 + 0.004)
            low_price = close_price * (1 - 0.0045)
            volume = 1000 + (pair_seed % 250) + (offset % 200)

            rows.append(
                (
                    pair,
                    timestamp_utc,
                    round(open_price, 6),
                    round(high_price, 6),
                    round(low_price, 6),
                    round(close_price, 6),
                    float(volume),
                    "daily",
                    "Dukascopy",
                )
            )

    return rows


def seed_prices() -> int:
    rows = build_daily_rows()
    with get_connection() as conn:
        conn.execute("DELETE FROM forex_prices")
        conn.executemany(
            """
            INSERT INTO forex_prices (
                pair,
                timestamp_utc,
                open,
                high,
                low,
                close,
                volume,
                granularity,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        conn.execute("DELETE FROM update_log")
        conn.execute(
            """
            INSERT INTO update_log (
                job_type,
                pair,
                start_time,
                end_time,
                status,
                records_inserted,
                message
            )
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            ("seed_backfill", None, "success", len(rows), "Seeded sample daily data"),
        )
    return len(rows)


def main() -> None:
    initialize_database()
    seed_pair_catalog()
    inserted = seed_prices()
    print(f"Seeded database with {inserted} forex price rows.")


if __name__ == "__main__":
    main()
