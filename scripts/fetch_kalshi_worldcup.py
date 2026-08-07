"""Pull World Cup 2026 market data from Kalshi's public API.

Fetches two things:

1. KXWCGAME -- per-match "regulation time moneyline" markets (one binary
   market per team + a tie market, for each of the tournament's matches).
   For these we pull minute-resolution candlesticks tightly around the
   match window, since the project's core question is how prices move
   during/around individual games.

2. KXMENWORLDCUP -- the tournament-winner futures market (one binary
   market per team, live for the whole tournament). For these we pull
   hourly candlesticks across the full series, since the interesting
   signal here is odds drift over days/weeks, not minutes.

Output (all under data/raw/kalshi/):
  - kxwcgame_markets.parquet       one row per match market (metadata + result)
  - kxmenworldcup_markets.parquet  one row per team's title-odds market
  - candlesticks/kxwcgame_minute.parquet
  - candlesticks/kxmenworldcup_hourly.parquet
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from kalshi.client import KalshiClient  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "kalshi"
CANDLES_DIR = DATA_DIR / "candlesticks"


def to_ts(iso: str | None) -> int | None:
    if not isinstance(iso, str) or not iso:
        return None
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def _f(x: str | None) -> float | None:
    """The API returns dollar/fixed-point fields as strings (e.g. '0.4300')."""
    return float(x) if x is not None else None


def flatten_candle(c: dict, market_ticker: str) -> dict:
    price = c.get("price") or {}
    yes_bid = c.get("yes_bid") or {}
    yes_ask = c.get("yes_ask") or {}
    return {
        "market_ticker": market_ticker,
        "end_period_ts": c["end_period_ts"],
        "timestamp": pd.to_datetime(c["end_period_ts"], unit="s", utc=True),
        "price_open": _f(price.get("open_dollars")),
        "price_close": _f(price.get("close_dollars")),
        "price_high": _f(price.get("high_dollars")),
        "price_low": _f(price.get("low_dollars")),
        "price_mean": _f(price.get("mean_dollars")),
        "yes_bid_close": _f(yes_bid.get("close_dollars")),
        "yes_ask_close": _f(yes_ask.get("close_dollars")),
        "volume": _f(c.get("volume_fp")),
        "open_interest": _f(c.get("open_interest_fp")),
    }


def fetch_match_markets(client: KalshiClient) -> pd.DataFrame:
    print("Fetching KXWCGAME events...")
    events = list(client.get_events(series_ticker="KXWCGAME"))
    print(f"  {len(events)} match events found")

    rows = []
    for ev in tqdm(events, desc="Fetching match markets"):
        full_event = client.get_event(ev["event_ticker"], with_nested_markets=True)
        for m in full_event.get("markets", []):
            rows.append(
                {
                    "event_ticker": full_event["event_ticker"],
                    "event_title": full_event.get("title"),
                    "market_ticker": m["ticker"],
                    "yes_team_subtitle": m.get("yes_sub_title"),
                    "no_team_subtitle": m.get("no_sub_title"),
                    "status": m.get("status"),
                    "result": m.get("result"),
                    "open_time": m.get("open_time"),
                    "close_time": m.get("close_time"),
                    "occurrence_datetime": m.get("occurrence_datetime"),
                    "settlement_value_dollars": _f(m.get("settlement_value_dollars")),
                    "volume": _f(m.get("volume_fp")),
                    "open_interest": _f(m.get("open_interest_fp")),
                }
            )
    return pd.DataFrame(rows)


def fetch_match_candlesticks(client: KalshiClient, markets_df: pd.DataFrame) -> pd.DataFrame:
    """Fetches minute candlesticks for each match market.

    `occurrence_datetime` looks like a kickoff time but isn't reliable as
    one: it's null for some matches (which used to fall back to
    `open_time` -- when the market was *created*, often months before
    kickoff, producing a multi-week candle window) and for others it
    lands a few minutes *after* `close_time` (which used to make
    start >= end and skip the market with zero candles). `close_time`
    (settlement) is the one timestamp that's consistently accurate, so
    windows are anchored there instead: no match, even with extra time
    and penalties, runs longer than ~2.5 hours, so 4 hours of lookback
    comfortably covers kickoff plus pre-match context.
    """
    all_candles = []
    for _, row in tqdm(
        list(markets_df.iterrows()), desc="Fetching match candlesticks (1-min)"
    ):
        end = to_ts(row["close_time"])
        if end is None:
            end = int(datetime.now(timezone.utc).timestamp())
        open_time = to_ts(row["open_time"])
        start = end - 4 * 60 * 60
        if open_time is not None:
            start = max(start, open_time)
        if start >= end:
            continue
        candles = client.get_candlesticks(
            series_ticker="KXWCGAME",
            market_ticker=row["market_ticker"],
            start_ts=start,
            end_ts=end,
            period_interval=1,
        )
        all_candles.extend(flatten_candle(c, row["market_ticker"]) for c in candles)
    return pd.DataFrame(all_candles)


def fetch_worldcup_winner_markets(client: KalshiClient) -> pd.DataFrame:
    print("Fetching KXMENWORLDCUP event...")
    events = list(client.get_events(series_ticker="KXMENWORLDCUP"))
    rows = []
    for ev in events:
        full_event = client.get_event(ev["event_ticker"], with_nested_markets=True)
        for m in full_event.get("markets", []):
            rows.append(
                {
                    "event_ticker": full_event["event_ticker"],
                    "market_ticker": m["ticker"],
                    "team_subtitle": m.get("yes_sub_title"),
                    "status": m.get("status"),
                    "result": m.get("result"),
                    "open_time": m.get("open_time"),
                    "close_time": m.get("close_time"),
                    "settlement_value_dollars": _f(m.get("settlement_value_dollars")),
                    "volume": _f(m.get("volume_fp")),
                    "open_interest": _f(m.get("open_interest_fp")),
                }
            )
    print(f"  {len(rows)} team title-odds markets found")
    return pd.DataFrame(rows)


def fetch_worldcup_winner_candlesticks(
    client: KalshiClient, markets_df: pd.DataFrame
) -> pd.DataFrame:
    all_candles = []
    now_ts = int(datetime.now(timezone.utc).timestamp())
    for _, row in tqdm(
        list(markets_df.iterrows()), desc="Fetching title-odds candlesticks (1-hr)"
    ):
        start = to_ts(row["open_time"])
        end = to_ts(row["close_time"]) or now_ts
        if start is None or start >= end:
            continue
        candles = client.get_candlesticks(
            series_ticker="KXMENWORLDCUP",
            market_ticker=row["market_ticker"],
            start_ts=start,
            end_ts=end,
            period_interval=60,
        )
        all_candles.extend(flatten_candle(c, row["market_ticker"]) for c in candles)
    return pd.DataFrame(all_candles)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CANDLES_DIR.mkdir(parents=True, exist_ok=True)
    client = KalshiClient()

    match_markets = fetch_match_markets(client)
    match_markets.to_parquet(DATA_DIR / "kxwcgame_markets.parquet", index=False)
    match_markets.to_csv(DATA_DIR / "kxwcgame_markets.csv", index=False)
    print(f"Saved {len(match_markets)} match markets")

    match_candles = fetch_match_candlesticks(client, match_markets)
    match_candles.to_parquet(CANDLES_DIR / "kxwcgame_minute.parquet", index=False)
    print(f"Saved {len(match_candles)} minute candlesticks for match markets")

    winner_markets = fetch_worldcup_winner_markets(client)
    winner_markets.to_parquet(DATA_DIR / "kxmenworldcup_markets.parquet", index=False)
    winner_markets.to_csv(DATA_DIR / "kxmenworldcup_markets.csv", index=False)
    print(f"Saved {len(winner_markets)} title-odds markets")

    winner_candles = fetch_worldcup_winner_candlesticks(client, winner_markets)
    winner_candles.to_parquet(CANDLES_DIR / "kxmenworldcup_hourly.parquet", index=False)
    print(f"Saved {len(winner_candles)} hourly candlesticks for title-odds markets")


if __name__ == "__main__":
    main()
