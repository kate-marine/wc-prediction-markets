# Data

## Kalshi (`data/raw/kalshi/`)

Produced by `scripts/fetch_kalshi_worldcup.py`, which pulls Kalshi's public
market-data endpoints (no API key needed to read market data — see
docs.kalshi.com). Re-run the script any time to refresh/regenerate this
directory; it's gitignored since it's fully reproducible from the script.

**`kxwcgame_markets.parquet` / `.csv`** — one row per match outcome market
(3 per match: home win / away win / tie) from the `KXWCGAME` series (the
104 World Cup 2026 matches). Columns: `event_ticker`, `event_title`,
`market_ticker`, `yes_team_subtitle`, `no_team_subtitle`, `status`,
`result` (yes/no once settled), `open_time`, `close_time`,
`occurrence_datetime` (scheduled kickoff), `settlement_value_dollars`,
`volume`, `open_interest`.

**`candlesticks/kxwcgame_minute.parquet`** — minute-resolution price
history for every market above, spanning from 1 hour before kickoff to
market close (i.e. through full time + resolution). Columns:
`market_ticker`, `end_period_ts`, `timestamp`, `price_open/close/high/low/mean`
(traded price, in dollars = implied probability), `yes_bid_close`,
`yes_ask_close`, `volume`, `open_interest`.

**`kxmenworldcup_markets.parquet` / `.csv`** — one row per team in the
`KXMENWORLDCUP` tournament-winner futures market.

**`candlesticks/kxmenworldcup_hourly.parquet`** — hourly price history for
each team's title odds across the whole tournament. Useful for looking at
how a team's championship odds drift match-to-match, separate from the
regulation-time win/loss/tie price action captured in `kxwcgame_minute`.

### Notes for analysis

- Prices are in dollars (0.00–1.00) and are the market's implied
  probability of the "yes" outcome.
- `KXWCGAME` markets are 3-way (win/lose/tie) rather than a single
  moneyline, so home and away win probabilities don't sum to 1 with the
  tie priced separately.
- Kalshi's soccer category has many other series worth pulling later for
  the "underlying performance vs. result" question — e.g. `KXWCTOTAL`
  (goal totals), `KXWCSPREAD`, `KXWCROUND` (advancement), `KXWCGROUPWIN`.
  `KXWCGAME` was the starting point since it's the cleanest per-match
  price series.
- This data has no match-event timestamps (goals, cards, etc.) — that
  needs to come from a separate source (e.g. a football data API) and be
  joined on `event_ticker` / kickoff time to study price reactions to
  specific in-game events.
