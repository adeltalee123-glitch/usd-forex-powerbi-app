from __future__ import annotations

import json
import math
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


USD_PAIR_CATALOG = [
    {"pair": "AUD/USD", "pair_name": "Australian Dollar vs US Dollar"},
    {"pair": "EUR/USD", "pair_name": "Euro vs US Dollar"},
    {"pair": "GBP/USD", "pair_name": "Pound Sterling vs US Dollar"},
    {"pair": "NZD/USD", "pair_name": "New Zealand Dollar vs US Dollar"},
    {"pair": "USD/CAD", "pair_name": "US Dollar vs Canadian Dollar"},
    {"pair": "USD/CHF", "pair_name": "US Dollar vs Swiss Franc"},
    {"pair": "USD/CNH", "pair_name": "US Dollar vs Chinese Yuan"},
    {"pair": "USD/CZK", "pair_name": "US Dollar vs Czech Koruna"},
    {"pair": "USD/DKK", "pair_name": "US Dollar vs Danish Krone"},
    {"pair": "USD/HKD", "pair_name": "US Dollar vs Hong Kong Dollar"},
    {"pair": "USD/HUF", "pair_name": "US Dollar vs Hungarian Forint"},
    {"pair": "USD/ILS", "pair_name": "US Dollar vs Israeli Shekel"},
    {"pair": "USD/JPY", "pair_name": "US Dollar vs Yen"},
    {"pair": "USD/MXN", "pair_name": "US Dollar vs Mexican Peso"},
    {"pair": "USD/NOK", "pair_name": "US Dollar vs Norwegian Krone"},
    {"pair": "USD/PLN", "pair_name": "US Dollar vs Zloty"},
    {"pair": "USD/RON", "pair_name": "US Dollar vs Romanian Leu"},
    {"pair": "USD/SEK", "pair_name": "US Dollar vs Swedish Krona"},
    {"pair": "USD/SGD", "pair_name": "US Dollar vs Singapore Dollar"},
    {"pair": "USD/THB", "pair_name": "US Dollar vs Thai Baht"},
    {"pair": "USD/TRY", "pair_name": "US Dollar vs Turkish Lira"},
    {"pair": "USD/ZAR", "pair_name": "US Dollar vs Rand"},
]

GRANULARITY_CHOICES = [
    {"key": "tick", "label": "Tick", "candle_type": "Tick", "candle_time": 1, "max_range_days": 1},
    {"key": "1s", "label": "1 Second", "candle_type": "Second", "candle_time": 1, "max_range_days": 7},
    {"key": "2s", "label": "2 Seconds", "candle_type": "Second", "candle_time": 2, "max_range_days": 7},
    {"key": "3s", "label": "3 Seconds", "candle_type": "Second", "candle_time": 3, "max_range_days": 7},
    {"key": "5s", "label": "5 Seconds", "candle_type": "Second", "candle_time": 5, "max_range_days": 7},
    {"key": "10s", "label": "10 Seconds", "candle_type": "Second", "candle_time": 10, "max_range_days": 7},
    {"key": "15s", "label": "15 Seconds", "candle_type": "Second", "candle_time": 15, "max_range_days": 7},
    {"key": "30s", "label": "30 Seconds", "candle_type": "Second", "candle_time": 30, "max_range_days": 7},
    {"key": "45s", "label": "45 Seconds", "candle_type": "Second", "candle_time": 45, "max_range_days": 7},
    {"key": "1m", "label": "1 Minute", "candle_type": "Minute", "candle_time": 1, "max_range_days": 366},
    {"key": "2m", "label": "2 Minutes", "candle_type": "Minute", "candle_time": 2, "max_range_days": 366},
    {"key": "3m", "label": "3 Minutes", "candle_type": "Minute", "candle_time": 3, "max_range_days": 366},
    {"key": "5m", "label": "5 Minutes", "candle_type": "Minute", "candle_time": 5, "max_range_days": 1826},
    {"key": "10m", "label": "10 Minutes", "candle_type": "Minute", "candle_time": 10, "max_range_days": 1826},
    {"key": "15m", "label": "15 Minutes", "candle_type": "Minute", "candle_time": 15, "max_range_days": 1826},
    {"key": "30m", "label": "30 Minutes", "candle_type": "Minute", "candle_time": 30, "max_range_days": 1826},
    {"key": "45m", "label": "45 Minutes", "candle_type": "Minute", "candle_time": 45, "max_range_days": 1826},
    {"key": "1h", "label": "1 Hour", "candle_type": "Hour", "candle_time": 1, "max_range_days": 3650},
    {"key": "2h", "label": "2 Hours", "candle_type": "Hour", "candle_time": 2, "max_range_days": 3650},
    {"key": "3h", "label": "3 Hours", "candle_type": "Hour", "candle_time": 3, "max_range_days": 3650},
    {"key": "4h", "label": "4 Hours", "candle_type": "Hour", "candle_time": 4, "max_range_days": 3650},
    {"key": "1d", "label": "1 Day", "candle_type": "Day", "candle_time": 1, "max_range_days": 3650},
    {"key": "2d", "label": "2 Days", "candle_type": "Day", "candle_time": 2, "max_range_days": 3650},
    {"key": "3d", "label": "3 Days", "candle_type": "Day", "candle_time": 3, "max_range_days": 3650},
    {"key": "1w", "label": "1 Week", "candle_type": "Week", "candle_time": 1, "max_range_days": 3650},
    {"key": "2w", "label": "2 Weeks", "candle_type": "Week", "candle_time": 2, "max_range_days": 3650},
    {"key": "3w", "label": "3 Weeks", "candle_type": "Week", "candle_time": 3, "max_range_days": 3650},
    {"key": "4w", "label": "4 Weeks", "candle_type": "Week", "candle_time": 4, "max_range_days": 3650},
    {"key": "1mo", "label": "1 Month", "candle_type": "Month", "candle_time": 1, "max_range_days": 3650},
    {"key": "3mo", "label": "3 Months", "candle_type": "Month", "candle_time": 3, "max_range_days": 3650},
    {"key": "6mo", "label": "6 Months", "candle_type": "Month", "candle_time": 6, "max_range_days": 3650},
    {"key": "12mo", "label": "12 Months", "candle_type": "Month", "candle_time": 12, "max_range_days": 3650},
]

GRANULARITY_MAP = {item["key"]: item for item in GRANULARITY_CHOICES}
DEFAULT_JETTA_BASE = "https://jetta.dukascopy.com"
DEFAULT_CA_BUNDLE_CANDIDATES = [
    os.environ.get("SSL_CERT_FILE", "").strip(),
    "/etc/ssl/cert.pem",
    "/private/etc/ssl/cert.pem",
]


@dataclass(frozen=True)
class DukascopyQuery:
    pair: str
    offer_side: str
    granularity_key: str
    start_dt: datetime
    end_dt: datetime

    @property
    def instrument_code(self) -> str:
        return self.pair.replace("/", "-")


class DukascopyProviderError(RuntimeError):
    pass


class DukascopyProvider:
    def __init__(self) -> None:
        self._base_url = os.environ.get("DUKASCOPY_JETTA_BASE", "").strip() or DEFAULT_JETTA_BASE
        self._ssl_context = build_ssl_context()

    def get_pairs(self) -> list[dict[str, str]]:
        return list(USD_PAIR_CATALOG)

    def get_granularity_choices(self) -> list[dict[str, Any]]:
        return [item for item in GRANULARITY_CHOICES if is_widget_granularity(item)]

    def status(self) -> dict[str, Any]:
        if os.environ.get("DUKASCOPY_JETTA_BASE", "").strip():
            return {
                "mode": "configured",
                "base_url": self._base_url,
                "message": f"Live Dukascopy mode enabled through DUKASCOPY_JETTA_BASE. SSL mode: {ssl_mode_label(self._ssl_context)}.",
            }
        return {
            "mode": "auto_discovered",
            "base_url": self._base_url,
            "message": (
                "Live Dukascopy mode is using the official widget config value from "
                "https://widgets.dukascopy.com/config.json. "
                f"SSL mode: {ssl_mode_label(self._ssl_context)}."
            ),
        }

    def fetch_rows(self, query: DukascopyQuery) -> list[dict[str, Any]]:
        if not self._base_url:
            raise DukascopyProviderError(
                "Live Dukascopy mode is not configured. Set DUKASCOPY_JETTA_BASE before starting the server."
            )

        granularity = GRANULARITY_MAP.get(query.granularity_key)
        if not granularity:
            raise DukascopyProviderError(f"Unsupported granularity: {query.granularity_key}")
        validate_range_for_granularity(query.start_dt, query.end_dt, granularity)

        candle_type = granularity["candle_type"]
        candle_time = granularity["candle_time"]

        if candle_type == "Tick":
            rows = self._fetch_ticks(query)
        elif candle_type == "Second":
            rows = self._fetch_seconds(query)
        elif candle_type == "Minute":
            rows = self._fetch_minutes(query)
        elif candle_type == "Hour":
            rows = self._fetch_hours(query)
        else:
            rows = self._fetch_days(query)

        if candle_type in {"Second", "Week", "Month"} or candle_time > 1:
            rows = aggregate_rows(rows, candle_type=candle_type, candle_time=candle_time)

        return rows

    def _request_json(self, path: str) -> Any:
        url = self._build_url(path)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://widgets.dukascopy.com/en/historical-data-export",
                "Origin": "https://widgets.dukascopy.com",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30, context=self._ssl_context) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise DukascopyProviderError(f"Dukascopy request failed: HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise DukascopyProviderError(f"Dukascopy request failed: {exc.reason} for {url}") from exc

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            preview = body[:160].replace("\n", " ")
            raise DukascopyProviderError(f"Dukascopy returned non-JSON data for {url}: {preview}") from exc

    def _build_url(self, path: str) -> str:
        base_url = (self._base_url or "").rstrip("/")
        clean_path = path.lstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/{clean_path}"
        return f"{base_url}/v1/{clean_path}"

    def _fetch_minutes(self, query: DukascopyQuery) -> list[dict[str, Any]]:
        payloads = []
        cursor = query.start_dt.date()
        today_utc = datetime.now(timezone.utc).date()
        while cursor <= query.end_dt.date():
            if cursor == today_utc:
                path = f"candles/minute/{query.instrument_code}/{query.offer_side}"
            else:
                path = f"candles/minute/{query.instrument_code}/{query.offer_side}/{cursor.year}/{cursor.month}/{cursor.day}"
            payloads.append(self._request_json(path))
            cursor += timedelta(days=1)
        rows: list[dict[str, Any]] = []
        for payload in payloads:
            rows.extend(
                decode_candle_payload(
                    payload=payload,
                    pair=query.pair,
                    offer_side=query.offer_side,
                    start_dt=query.start_dt,
                    end_dt=query.end_dt,
                    base_granularity="minute",
                )
            )
        return rows

    def _fetch_hours(self, query: DukascopyQuery) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor_year = query.start_dt.year
        cursor_month = query.start_dt.month
        now_utc = datetime.now(timezone.utc)
        while (cursor_year, cursor_month) <= (query.end_dt.year, query.end_dt.month):
            if (cursor_year, cursor_month) == (now_utc.year, now_utc.month):
                path = f"candles/hour/{query.instrument_code}/{query.offer_side}"
            else:
                path = f"candles/hour/{query.instrument_code}/{query.offer_side}/{cursor_year}/{cursor_month}"
            payload = self._request_json(path)
            rows.extend(
                decode_candle_payload(
                    payload=payload,
                    pair=query.pair,
                    offer_side=query.offer_side,
                    start_dt=query.start_dt,
                    end_dt=query.end_dt,
                    base_granularity="hour",
                )
            )
            if cursor_month == 12:
                cursor_year += 1
                cursor_month = 1
            else:
                cursor_month += 1
        return rows

    def _fetch_days(self, query: DukascopyQuery) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current_year = datetime.now(timezone.utc).year
        for year in range(query.start_dt.year, query.end_dt.year + 1):
            if year == current_year:
                path = f"candles/day/{query.instrument_code}/{query.offer_side}"
            else:
                path = f"candles/day/{query.instrument_code}/{query.offer_side}/{year}"
            payload = self._request_json(path)
            rows.extend(
                decode_candle_payload(
                    payload=payload,
                    pair=query.pair,
                    offer_side=query.offer_side,
                    start_dt=query.start_dt,
                    end_dt=query.end_dt,
                    base_granularity="day",
                )
            )
        return rows

    def _fetch_seconds(self, query: DukascopyQuery) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = query.start_dt.replace(minute=0, second=0, microsecond=0)
        now_utc = datetime.now(timezone.utc)
        while cursor <= query.end_dt:
            if (
                cursor.year == now_utc.year
                and cursor.month == now_utc.month
                and cursor.day == now_utc.day
                and cursor.hour == now_utc.hour
            ):
                path = f"ticks/{query.instrument_code}"
            else:
                path = f"ticks/{query.instrument_code}/{cursor.year}/{cursor.month}/{cursor.day}/{cursor.hour}"
            payload = self._request_json(path)
            rows.extend(
                decode_tick_payload(
                    payload=payload,
                    pair=query.pair,
                    offer_side=query.offer_side,
                    start_dt=query.start_dt,
                    end_dt=query.end_dt,
                    mode="second",
                )
            )
            cursor += timedelta(hours=1)
        return rows

    def _fetch_ticks(self, query: DukascopyQuery) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = query.start_dt.replace(minute=0, second=0, microsecond=0)
        now_utc = datetime.now(timezone.utc)
        while cursor <= query.end_dt:
            if (
                cursor.year == now_utc.year
                and cursor.month == now_utc.month
                and cursor.day == now_utc.day
                and cursor.hour == now_utc.hour
            ):
                path = f"ticks/{query.instrument_code}"
            else:
                path = f"ticks/{query.instrument_code}/{cursor.year}/{cursor.month}/{cursor.day}/{cursor.hour}"
            payload = self._request_json(path)
            rows.extend(
                decode_tick_payload(
                    payload=payload,
                    pair=query.pair,
                    offer_side=query.offer_side,
                    start_dt=query.start_dt,
                    end_dt=query.end_dt,
                    mode="tick",
                )
            )
            cursor += timedelta(hours=1)
        return rows


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_ssl_context() -> ssl.SSLContext:
    if os.environ.get("DUKASCOPY_SSL_NO_VERIFY", "").strip() == "1":
        return ssl._create_unverified_context()

    for candidate in DEFAULT_CA_BUNDLE_CANDIDATES:
        if candidate and Path(candidate).exists():
            return ssl.create_default_context(cafile=candidate)

    return ssl.create_default_context()


def ssl_mode_label(context: ssl.SSLContext) -> str:
    if context.check_hostname is False and context.verify_mode == ssl.CERT_NONE:
        return "unverified"
    return "verified"


def is_widget_granularity(item: dict[str, Any]) -> bool:
    candle_type = item.get("candle_type")
    candle_time = int(item.get("candle_time", 0))
    if candle_type == "Minute":
        return True
    if candle_type == "Hour":
        return True
    return candle_type == "Day" and candle_time == 1


def validate_range_for_granularity(start_dt: datetime, end_dt: datetime, granularity: dict[str, Any]) -> None:
    max_range_days = int(granularity.get("max_range_days", 3650))
    actual_days = (ensure_utc(end_dt) - ensure_utc(start_dt)).days + 1
    if actual_days > max_range_days:
        raise DukascopyProviderError(
            f"{granularity['label']} requests are limited to {max_range_days} days in live mode. "
            f"Please shorten the date range or switch to a coarser granularity."
        )


def decode_candle_payload(
    payload: dict[str, Any],
    pair: str,
    offer_side: str,
    start_dt: datetime,
    end_dt: datetime,
    base_granularity: str,
) -> list[dict[str, Any]]:
    times = payload.get("times") or []
    opens = payload.get("opens") or []
    highs = payload.get("highs") or []
    lows = payload.get("lows") or []
    closes = payload.get("closes") or []
    volumes = payload.get("volumes") or []
    if not times:
        return []

    if not (len(times) == len(opens) == len(highs) == len(lows) == len(closes) == len(volumes)):
        raise DukascopyProviderError("Inconsistent candle payload received from Dukascopy.")

    shift = payload.get("shift", 1)
    multiplier = payload.get("multiplier", 1)
    scale = price_scale(multiplier)
    timestamp_ms = payload.get("timestamp", 0)
    open_price = payload.get("open", 1)
    high_price = payload.get("high", 1)
    low_price = payload.get("low", 1)
    close_price = payload.get("close", 1)

    rows: list[dict[str, Any]] = []
    for index, delta in enumerate(times):
        timestamp_ms += shift * delta
        open_price = apply_delta(open_price, opens[index], multiplier, scale)
        high_price = apply_delta(high_price, highs[index], multiplier, scale)
        low_price = apply_delta(low_price, lows[index], multiplier, scale)
        close_price = apply_delta(close_price, closes[index], multiplier, scale)

        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        if timestamp < start_dt or timestamp > end_dt:
            continue

        rows.append(
            {
                "pair": pair,
                "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "open": round(open_price, 6),
                "high": round(high_price, 6),
                "low": round(low_price, 6),
                "close": round(close_price, 6),
                "volume": round(float(volumes[index]), 6),
                "granularity": base_granularity,
                "source": "Dukascopy",
                "offer_side": offer_side,
            }
        )
    return rows


def decode_tick_payload(
    payload: dict[str, Any],
    pair: str,
    offer_side: str,
    start_dt: datetime,
    end_dt: datetime,
    mode: str,
) -> list[dict[str, Any]]:
    times = payload.get("times") or []
    bids = payload.get("bids") or []
    asks = payload.get("asks") or []
    bid_volumes = payload.get("bidVolumes") or []
    ask_volumes = payload.get("askVolumes") or []
    if not times:
        return []

    if not (len(times) == len(bids) == len(asks) == len(bid_volumes) == len(ask_volumes)):
        raise DukascopyProviderError("Inconsistent tick payload received from Dukascopy.")

    multiplier = payload.get("multiplier", 1)
    scale = price_scale(multiplier)
    timestamp_ms = payload.get("timestamp", 0)
    bid_price = payload.get("bid", 1)
    ask_price = payload.get("ask", 1)

    rows: list[dict[str, Any]] = []
    for index, delta in enumerate(times):
        timestamp_ms += delta
        bid_price = apply_delta(bid_price, bids[index], multiplier, scale)
        ask_price = apply_delta(ask_price, asks[index], multiplier, scale)

        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        if timestamp < start_dt or timestamp > end_dt:
            continue

        chosen_price = bid_price if offer_side == "BID" else ask_price
        chosen_volume = bid_volumes[index] if offer_side == "BID" else ask_volumes[index]
        rows.append(
            {
                "pair": pair,
                "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "open": round(chosen_price, 6),
                "high": round(chosen_price, 6),
                "low": round(chosen_price, 6),
                "close": round(chosen_price, 6),
                "volume": round(float(chosen_volume) / 1_000_000, 6),
                "granularity": mode,
                "source": "Dukascopy",
                "offer_side": offer_side,
            }
        )
    return rows


def price_scale(multiplier: float) -> float:
    if multiplier == 0:
        return 1
    digits = math.floor(math.log10(abs(multiplier))) if multiplier else 0
    return multiplier if digits > 0 else math.pow(10, abs(digits))


def apply_delta(current_value: float, delta: float, multiplier: float, scale: float) -> float:
    return round((current_value + delta * multiplier) * scale) / scale


def aggregate_rows(rows: list[dict[str, Any]], candle_type: str, candle_time: int) -> list[dict[str, Any]]:
    if not rows:
        return rows
    if candle_time <= 1 and candle_type not in {"Second", "Week", "Month"}:
        return rows

    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in sorted(rows, key=lambda item: item["timestamp_utc"]):
        ts = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
        bucket = bucket_start(ts, candle_type, candle_time)
        grouped.setdefault(bucket, []).append(row)

    output: list[dict[str, Any]] = []
    for bucket in sorted(grouped):
        group = grouped[bucket]
        first = group[0]
        last = group[-1]
        output.append(
            {
                "pair": first["pair"],
                "timestamp_utc": datetime.fromtimestamp(bucket / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "open": first["open"],
                "high": max(item["high"] for item in group),
                "low": min(item["low"] for item in group),
                "close": last["close"],
                "volume": round(sum(item["volume"] for item in group), 6),
                "granularity": normalize_output_granularity(candle_type, candle_time),
                "source": first["source"],
                "offer_side": first["offer_side"],
            }
        )
    return output


def bucket_start(timestamp: datetime, candle_type: str, candle_time: int) -> int:
    epoch_ms = int(timestamp.timestamp() * 1000)
    if candle_type == "Month":
        month_index = timestamp.year * 12 + (timestamp.month - 1)
        aligned = month_index - (month_index % candle_time)
        year = aligned // 12
        month = aligned % 12 + 1
        return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
    if candle_type == "Week":
        monday = datetime.combine((timestamp - timedelta(days=timestamp.weekday())).date(), time.min, tzinfo=timezone.utc)
        epoch_monday = datetime(1970, 1, 5, tzinfo=timezone.utc)
        week_index = (monday - epoch_monday).days // 7
        aligned = week_index - (week_index % candle_time)
        return int((epoch_monday + timedelta(weeks=aligned)).timestamp() * 1000)
    if candle_type == "Day":
        return epoch_ms - (epoch_ms % (86_400_000 * candle_time))
    if candle_type == "Hour":
        return epoch_ms - (epoch_ms % (3_600_000 * candle_time))
    if candle_type == "Minute":
        return epoch_ms - (epoch_ms % (60_000 * candle_time))
    if candle_type == "Second":
        return epoch_ms - (epoch_ms % (1_000 * candle_time))
    return epoch_ms


def normalize_output_granularity(candle_type: str, candle_time: int) -> str:
    suffix = {
        "Tick": "tick",
        "Second": "s",
        "Minute": "m",
        "Hour": "h",
        "Day": "d",
        "Week": "w",
        "Month": "mo",
    }[candle_type]
    return "tick" if candle_type == "Tick" else f"{candle_time}{suffix}"
