"""Thin client for Kalshi's public (unauthenticated) market-data endpoints.

Covers the read-only surface needed for this project: series, events,
markets, and candlesticks. All of these are public per Kalshi's API docs
(docs.kalshi.com) -- no API key is required to read market data, only to
trade.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterator

import requests

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

# Candlestick endpoint caps the number of periods returned per request.
MAX_CANDLES_PER_REQUEST = 5000


@dataclass
class KalshiClient:
    base_url: str = BASE_URL
    request_delay_seconds: float = 0.15
    max_retries: int = 5

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"accept": "application/json"})

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        backoff = 1.0
        for attempt in range(self.max_retries):
            resp = self._session.get(url, params=params, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries - 1:
                    resp.raise_for_status()
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            time.sleep(self.request_delay_seconds)
            return resp.json()
        raise RuntimeError(f"unreachable: exhausted retries for {url}")

    def get_series_list(self, category: str | None = None) -> list[dict[str, Any]]:
        params = {"category": category} if category else {}
        return self._get("/series", params=params)["series"]

    def get_series(self, series_ticker: str) -> dict[str, Any]:
        return self._get(f"/series/{series_ticker}")["series"]

    def get_events(
        self,
        series_ticker: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> Iterator[dict[str, Any]]:
        """Yields every event, transparently following the cursor."""
        cursor = None
        while True:
            params: dict[str, Any] = {"limit": limit}
            if series_ticker:
                params["series_ticker"] = series_ticker
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            data = self._get("/events", params=params)
            yield from data.get("events", [])
            cursor = data.get("cursor")
            if not cursor:
                break

    def get_event(self, event_ticker: str, with_nested_markets: bool = True) -> dict[str, Any]:
        params = {"with_nested_markets": str(with_nested_markets).lower()}
        return self._get(f"/events/{event_ticker}", params=params)["event"]

    def get_candlesticks(
        self,
        series_ticker: str,
        market_ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int,
    ) -> list[dict[str, Any]]:
        """Fetches candlesticks over [start_ts, end_ts], chunking requests so
        each stays under the API's per-request candle cap.
        """
        chunk_seconds = period_interval * 60 * (MAX_CANDLES_PER_REQUEST - 1)
        candles: list[dict[str, Any]] = []
        chunk_start = start_ts
        while chunk_start < end_ts:
            chunk_end = min(chunk_start + chunk_seconds, end_ts)
            data = self._get(
                f"/series/{series_ticker}/markets/{market_ticker}/candlesticks",
                params={
                    "start_ts": chunk_start,
                    "end_ts": chunk_end,
                    "period_interval": period_interval,
                },
            )
            candles.extend(data.get("candlesticks", []))
            chunk_start = chunk_end
        return candles
