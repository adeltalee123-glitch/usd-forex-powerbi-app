from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .database import BASE_DIR, get_connection, initialize_database, seed_pair_catalog
from .dukascopy_provider import GRANULARITY_MAP, DukascopyProvider, DukascopyProviderError, DukascopyQuery
from .seed_data import seed_prices


STATIC_DIR = BASE_DIR / "app" / "static"
PROVIDER = DukascopyProvider()


def parse_date_or_none(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def compute_date_range(query: dict[str, list[str]]) -> tuple[str, str]:
    start_date = parse_date_or_none(query.get("start_date", [None])[0])
    end_date = parse_date_or_none(query.get("end_date", [None])[0]) or date.today()
    years_raw = query.get("years", [None])[0]

    if start_date and end_date:
        return start_date.isoformat(), end_date.isoformat()

    years = 1
    if years_raw:
        years = min(10, max(1, int(years_raw)))
    start_date = end_date - timedelta(days=(365 * years) - 1)
    return start_date.isoformat(), end_date.isoformat()


def compute_datetime_range(query: dict[str, list[str]]) -> tuple[datetime, datetime]:
    start_date, end_date = compute_date_range(query)
    start_dt = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, microsecond=999000, tzinfo=timezone.utc)
    return start_dt, end_dt


def synthetic_spread_for_pair(pair: str) -> float:
    if "JPY" in pair:
        return 0.02
    if pair in {"USD/HUF", "USD/CZK", "USD/THB"}:
        return 0.002
    return 0.0002


def seed_row_to_strategy_row(row: dict, offer_side: str) -> dict:
    spread = synthetic_spread_for_pair(row["pair"])
    bid_open = float(row["open"])
    bid_high = float(row["high"])
    bid_low = float(row["low"])
    bid_close = float(row["close"])
    ask_open = round(bid_open + spread, 6)
    ask_high = round(bid_high + spread, 6)
    ask_low = round(bid_low + spread, 6)
    ask_close = round(bid_close + spread, 6)
    bid_volume = row.get("volume")
    ask_volume = row.get("volume")

    strategy_row = {
        "pair": row["pair"],
        "timestamp_utc": row["timestamp_utc"],
        "bid_open": round(bid_open, 6),
        "bid_high": round(bid_high, 6),
        "bid_low": round(bid_low, 6),
        "bid_close": round(bid_close, 6),
        "ask_open": ask_open,
        "ask_high": ask_high,
        "ask_low": ask_low,
        "ask_close": ask_close,
        "bid_volume": bid_volume,
        "ask_volume": ask_volume,
        "spread": round(spread, 6),
        "granularity": row["granularity"],
        "source": row["source"],
    }
    if offer_side == "BID":
        strategy_row.update(
            {
                "ask_open": None,
                "ask_high": None,
                "ask_low": None,
                "ask_close": None,
                "ask_volume": None,
            }
        )
    elif offer_side == "ASK":
        strategy_row.update(
            {
                "bid_open": None,
                "bid_high": None,
                "bid_low": None,
                "bid_close": None,
                "bid_volume": None,
            }
        )
    return strategy_row


def granularity_minutes(granularity_key: str) -> int:
    granularity = GRANULARITY_MAP.get(granularity_key)
    if not granularity:
        raise ValueError(f"Unsupported granularity: {granularity_key}")

    candle_type = granularity["candle_type"]
    candle_time = int(granularity["candle_time"])
    if candle_type == "Minute":
        return candle_time
    if candle_type == "Hour":
        return candle_time * 60
    if candle_type == "Day" and candle_time == 1:
        return 1440
    raise ValueError("Granularity must be between 1 minute and 1 day")


def interpolate_segment(start_value: float, end_value: float, ratio: float) -> float:
    return round(start_value + (end_value - start_value) * ratio, 6)


def synthetic_path_value(open_value: float, high_value: float, low_value: float, close_value: float, ratio: float) -> float:
    if ratio <= 0.25:
        return interpolate_segment(open_value, high_value, ratio / 0.25)
    if ratio <= 0.75:
        return interpolate_segment(high_value, low_value, (ratio - 0.25) / 0.5)
    return interpolate_segment(low_value, close_value, (ratio - 0.75) / 0.25)


def expand_seed_strategy_rows(rows: list[dict], granularity_key: str) -> list[dict]:
    minutes_per_bar = granularity_minutes(granularity_key)
    if minutes_per_bar >= 1440:
        expanded = []
        for row in rows:
            item = dict(row)
            item["granularity"] = granularity_key
            expanded.append(item)
        return expanded

    bars_per_day = max(1, 1440 // minutes_per_bar)
    expanded: list[dict] = []

    for row in rows:
        base_dt = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
        bid_volume_total = float(row["bid_volume"] or 0)
        ask_volume_total = float(row["ask_volume"] or 0)
        spread = row["spread"]

        for bar_index in range(bars_per_day):
            start_ratio = bar_index / bars_per_day
            end_ratio = (bar_index + 1) / bars_per_day
            bid_open = synthetic_path_value(row["bid_open"], row["bid_high"], row["bid_low"], row["bid_close"], start_ratio) if row["bid_open"] is not None else None
            bid_close = synthetic_path_value(row["bid_open"], row["bid_high"], row["bid_low"], row["bid_close"], end_ratio) if row["bid_open"] is not None else None
            ask_open = synthetic_path_value(row["ask_open"], row["ask_high"], row["ask_low"], row["ask_close"], start_ratio) if row["ask_open"] is not None else None
            ask_close = synthetic_path_value(row["ask_open"], row["ask_high"], row["ask_low"], row["ask_close"], end_ratio) if row["ask_open"] is not None else None

            expanded.append(
                {
                    "pair": row["pair"],
                    "timestamp_utc": (base_dt + timedelta(minutes=bar_index * minutes_per_bar)).isoformat().replace("+00:00", "Z"),
                    "bid_open": bid_open,
                    "bid_high": max(value for value in [bid_open, bid_close] if value is not None) if bid_open is not None and bid_close is not None else None,
                    "bid_low": min(value for value in [bid_open, bid_close] if value is not None) if bid_open is not None and bid_close is not None else None,
                    "bid_close": bid_close,
                    "ask_open": ask_open,
                    "ask_high": max(value for value in [ask_open, ask_close] if value is not None) if ask_open is not None and ask_close is not None else None,
                    "ask_low": min(value for value in [ask_open, ask_close] if value is not None) if ask_open is not None and ask_close is not None else None,
                    "ask_close": ask_close,
                    "bid_volume": round(bid_volume_total / bars_per_day, 6) if row["bid_volume"] is not None else None,
                    "ask_volume": round(ask_volume_total / bars_per_day, 6) if row["ask_volume"] is not None else None,
                    "spread": spread,
                    "granularity": granularity_key,
                    "source": row["source"],
                }
            )

    return expanded


def merge_side_rows(
    bid_rows: list[dict],
    ask_rows: list[dict],
    requested_side: str,
) -> list[dict]:
    merged: dict[tuple[str, str, str], dict] = {}

    def ensure_entry(row: dict) -> dict:
        key = (row["pair"], row["timestamp_utc"], row["granularity"])
        if key not in merged:
            merged[key] = {
                "pair": row["pair"],
                "timestamp_utc": row["timestamp_utc"],
                "bid_open": None,
                "bid_high": None,
                "bid_low": None,
                "bid_close": None,
                "ask_open": None,
                "ask_high": None,
                "ask_low": None,
                "ask_close": None,
                "bid_volume": None,
                "ask_volume": None,
                "spread": None,
                "granularity": row["granularity"],
                "source": row["source"],
            }
        return merged[key]

    if requested_side in {"BID", "BOTH"}:
        for row in bid_rows:
            item = ensure_entry(row)
            item["bid_open"] = row["open"]
            item["bid_high"] = row["high"]
            item["bid_low"] = row["low"]
            item["bid_close"] = row["close"]
            item["bid_volume"] = row.get("volume")

    if requested_side in {"ASK", "BOTH"}:
        for row in ask_rows:
            item = ensure_entry(row)
            item["ask_open"] = row["open"]
            item["ask_high"] = row["high"]
            item["ask_low"] = row["low"]
            item["ask_close"] = row["close"]
            item["ask_volume"] = row.get("volume")

    for item in merged.values():
        if item["bid_close"] is not None and item["ask_close"] is not None:
            item["spread"] = round(item["ask_close"] - item["bid_close"], 6)

    return sorted(merged.values(), key=lambda item: (item["timestamp_utc"], item["pair"]))


class ForexRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_request(parsed)
            return

        if parsed.path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def handle_api_request(self, parsed) -> None:
        try:
            if parsed.path == "/api/pairs":
                self.handle_pairs(parsed)
            elif parsed.path == "/api/forex/usd-pairs":
                self.handle_prices(parsed, selected_pairs=None)
            elif parsed.path == "/api/forex/pairs":
                query = parse_qs(parsed.query)
                symbols = query.get("symbols", [""])[0]
                selected_pairs = [item.strip() for item in symbols.split(",") if item.strip()]
                if not selected_pairs:
                    self.send_json({"error": "symbols query parameter is required"}, HTTPStatus.BAD_REQUEST)
                    return
                self.handle_prices(parsed, selected_pairs=selected_pairs)
            elif parsed.path == "/api/status":
                self.handle_status()
            else:
                self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except DukascopyProviderError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
        except sqlite3.Error as exc:
            self.send_json({"error": f"Database error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_pairs(self, parsed) -> None:
        query = parse_qs(parsed.query)
        source_mode = query.get("source", ["live"])[0].lower()
        if source_mode == "seed":
            with get_connection() as conn:
                rows = conn.execute("SELECT pair, pair_name FROM pair_catalog ORDER BY pair").fetchall()
            self.send_json([dict(row) for row in rows])
            return
        self.send_json(PROVIDER.get_pairs())

    def handle_prices(self, parsed, selected_pairs: list[str] | None) -> None:
        query = parse_qs(parsed.query)
        source_mode = query.get("source", ["live"])[0].lower()
        granularity = query.get("granularity", ["1d"])[0]
        output_format = query.get("format", ["json"])[0].lower()
        offer_side = query.get("offer_side", ["BOTH"])[0].upper()
        start_date, end_date = compute_date_range(query)
        self.validate_offer_side(offer_side)

        if source_mode == "seed":
            seed_rows = self.load_seed_rows(selected_pairs=selected_pairs, start_date=start_date, end_date=end_date)
            normalized_seed_rows = self.normalize_seed_rows(seed_rows, offer_side=offer_side)
            payload = expand_seed_strategy_rows(normalized_seed_rows, granularity_key=granularity)
        else:
            payload = self.load_live_rows(query=query, selected_pairs=selected_pairs, granularity=granularity, offer_side=offer_side)

        if output_format == "csv":
            self.send_csv(payload, filename="forex_data.csv")
            return

        self.send_json(
            {
                "meta": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "granularity": granularity,
                    "row_count": len(payload),
                    "selected_pairs": selected_pairs or "all_usd_pairs",
                    "source_mode": source_mode,
                    "offer_side": offer_side,
                },
                "data": payload,
            }
        )

    def load_seed_rows(self, selected_pairs: list[str] | None, start_date: str, end_date: str) -> list[dict]:
        sql = """
            SELECT pair, timestamp_utc, open, high, low, close, volume, granularity, source
            FROM forex_prices
            WHERE date(substr(timestamp_utc, 1, 10)) BETWEEN ? AND ?
        """
        params: list[object] = [start_date, end_date]

        if selected_pairs:
            placeholders = ",".join("?" for _ in selected_pairs)
            sql += f" AND pair IN ({placeholders})"
            params.extend(selected_pairs)
            self.validate_pairs(selected_pairs)

        sql += " ORDER BY timestamp_utc, pair"
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def load_live_rows(
        self,
        query: dict[str, list[str]],
        selected_pairs: list[str] | None,
        granularity: str,
        offer_side: str,
    ) -> list[dict]:
        start_dt, end_dt = compute_datetime_range(query)
        pairs_to_fetch = selected_pairs or [item["pair"] for item in PROVIDER.get_pairs()]
        self.validate_pairs(pairs_to_fetch)

        bid_rows: list[dict] = []
        ask_rows: list[dict] = []
        for pair in pairs_to_fetch:
            if offer_side in {"BID", "BOTH"}:
                bid_rows.extend(
                    PROVIDER.fetch_rows(
                        DukascopyQuery(
                            pair=pair,
                            offer_side="BID",
                            granularity_key=granularity,
                            start_dt=start_dt,
                            end_dt=end_dt,
                        )
                    )
                )
            if offer_side in {"ASK", "BOTH"}:
                ask_rows.extend(
                    PROVIDER.fetch_rows(
                        DukascopyQuery(
                            pair=pair,
                            offer_side="ASK",
                            granularity_key=granularity,
                            start_dt=start_dt,
                            end_dt=end_dt,
                        )
                    )
                )
        return merge_side_rows(bid_rows, ask_rows, requested_side=offer_side)

    def normalize_seed_rows(self, rows: list[dict], offer_side: str) -> list[dict]:
        return [seed_row_to_strategy_row(row, offer_side) for row in rows]

    def handle_status(self) -> None:
        with get_connection() as conn:
            pair_count = conn.execute("SELECT COUNT(*) AS count FROM pair_catalog").fetchone()["count"]
            latest_job = conn.execute(
                """
                SELECT job_type, status, end_time, records_inserted, message
                FROM update_log
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        provider_status = PROVIDER.status()
        status_payload = {
            "status": "ok",
            "source": "Dukascopy",
            "supported_pairs": pair_count,
            "latest_job_type": latest_job["job_type"] if latest_job else None,
            "latest_job_status": latest_job["status"] if latest_job else None,
            "latest_successful_refresh": latest_job["end_time"] if latest_job else None,
            "records_inserted": latest_job["records_inserted"] if latest_job else 0,
            "message": latest_job["message"] if latest_job else None,
            "provider_mode": provider_status["mode"],
            "provider_base_url": provider_status["base_url"],
            "provider_message": provider_status["message"],
            "granularity_choices": PROVIDER.get_granularity_choices(),
            "seed_supported_granularities": [item["key"] for item in PROVIDER.get_granularity_choices()],
            "power_bi_recommended_granularities": [
                key for key in ("5m", "1h", "1d") if key in GRANULARITY_MAP
            ],
            "offer_side_choices": ["BOTH", "BID", "ASK"],
        }
        self.send_json(status_payload)

    def validate_pairs(self, pairs: list[str]) -> None:
        valid_pairs = {row["pair"] for row in PROVIDER.get_pairs()}
        invalid = [pair for pair in pairs if pair not in valid_pairs]
        if invalid:
            raise ValueError(f"Invalid pairs: {', '.join(invalid)}")

    def validate_offer_side(self, offer_side: str) -> None:
        if offer_side not in {"BID", "ASK", "BOTH"}:
            raise ValueError("offer_side must be BOTH, BID, or ASK")

    def send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_csv(self, rows: list[dict], filename: str) -> None:
        fieldnames = [
            "pair",
            "timestamp_utc",
            "bid_open",
            "bid_high",
            "bid_low",
            "bid_close",
            "ask_open",
            "ask_high",
            "ask_low",
            "ask_close",
            "bid_volume",
            "ask_volume",
            "spread",
            "granularity",
            "source",
        ]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        body = buffer.getvalue().encode("utf-8")

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def maybe_seed_on_startup() -> None:
    should_seed = os.environ.get("SEED_SAMPLE_DATA_ON_STARTUP", "").strip() == "1"
    if not should_seed:
        return
    with get_connection() as conn:
        existing_rows = conn.execute("SELECT COUNT(*) AS count FROM forex_prices").fetchone()["count"]
    if existing_rows == 0:
        seed_prices()


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    initialize_database()
    seed_pair_catalog()
    maybe_seed_on_startup()
    server = ThreadingHTTPServer((host, port), ForexRequestHandler)
    print(f"Serving USD Forex app at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    run_server(host=host, port=port)
