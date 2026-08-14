# Data

## Kalshi 

Used `scripts/fetch_kalshi_worldcup.py` to pull Kalshi's public
market-data endpoints (no API key needed see docs.kalshi.com). Re-run the script any time to refresh/regenerate this directory (gitignored since it's fully reproducible from the script).

`kxwcgame_markets.parquet` — one row per match outcome market
(3 per match: home win / away win / tie) from the KXWCGAME series (the
104 World Cup 2026 matches). Columns: `event_ticker`, `event_title`,
`market_ticker`, `yes_team_subtitle`, `no_team_subtitle`, `status`,
`result` (yes/no once settled), `open_time`, `close_time`,
`occurrence_datetime`, `settlement_value_dollars`, `volume`,
`open_interest`. Note: `occurrence_datetime` is not actually accurate kickoff
time so usring SofaScore's `start_time` instead (see below), and joined on team names.

`candlesticks/kxwcgame_minute.parquet` — minute by minute price
history for every market above, spanning the 4 hours before each
market's close time.
Columns: `market_ticker`, `end_period_ts`, `timestamp`,
`price_open/close/high/low/mean`, `yes_bid_close`, `yes_ask_close`, `volume`,
`open_interest`.

`kxmenworldcup_markets.parquet` — one row per team in the
tournament-winner futures market.

`candlesticks/kxmenworldcup_hourly.parquet` — has hourly price history for
each team's title odds across the whole tournament. Can see
how a team's championship odds change from match to match.

### Notes 

- Prices are in dollars (0.00–1.00) and are the market's implied
  probability of the "yes" outcome.
- `KXWCGAME` markets are 3-way (win/lose/tie) rather than a single
  moneyline, so home and away win probabilities don't sum to 1 with the
  tie priced separately.

## FBref (`data/raw/fbref/`)

Used `scripts/fetch_fbref_worldcup.py` which drives a Chrome browser (Selenium) to get past FBref's Cloudflare bot check (~7s/request per FBref's
crawl policy). 

- **`schedule.parquet`** — 104 matches: teams, score, date/time, venue,
  attendance, referee, link to the match report, `game_id` (FBref's
  8-char match hash, used to join the tables below).
- **`team_match_shooting.parquet`** — 208 rows (104 matches x 2 teams,
  with explicit `team`/`opponent` columns): shots, shots on target,
  goals, G/Sh, G/SoT, penalties. (No xG in this particular table --
  FBref's team-season match log doesn't carry it; use SofaScore's
  `statistics.parquet` for xG instead.)
- **`team_match_keeper.parquet`** — 208 rows, goalkeeper log: goals
  against, saves, save%, PSxG, launch/pass stats, crosses stopped.
- **`team_match_misc.parquet`** — 208 rows: yellow/red cards, fouls
  committed/drawn, offsides, crosses, tackles won, interceptions, ball
  recoveries, aerial duels won/lost.

  (These three come from FBref's team-season match logs, which include
  every match a team played back to 2023 — qualifiers, friendlies, etc.
  — and don't label which team a row belongs to. The fetch script
  filters down to just the 104 WC 2026 matches and derives `team` by
  joining `date` + `opponent` against the schedule.)
- **`events.parquet`** — goal/card/substitution timeline with the
  players and minute involved (full-match granularity, not per-minute).
- **`lineup.parquet`** — starting XI, formation, and substitutes used.
- **`player_match_summary.parquet`** — per-player per-match box score:
  passing (attempted/completed/progressive), carries, tackles,
  interceptions, blocks, touches by pitch zone, take-ons, cards.
- **`player_match_keepers.parquet`** — per-player goalkeeper detail
  (shot-stopping, distribution, sweeping) for matches they played.

## SofaScore (`data/raw/sofascore/`)

Produced by `scripts/fetch_sofascore_worldcup.py`, which hits SofaScore's
undocumented public JSON API directly (`src/sofascore/client.py`).
**Caveat:** SofaScore's own FAQ states they don't license third-party API
access — this is used read-only, at modest personal-research volume,
mirroring what several open-source scraper projects already do. Treat as
lower-provenance than FBref; cross-check anything load-bearing.

This is the source for genuinely *time-resolved* signal that FBref
doesn't have:

- **`schedule.parquet`** — 104 matches: teams, score, kickoff time
  (`start_time`), round/stage, `event_id` (used to join the tables below).
- **`statistics.parquet`** — long format, one row per
  (match, period, stat). `period` is `ALL`, `1ST`, `2ND`, and `ET1`/`ET2`
  where applicable — i.e. most of these ~45 stats (possession, xG, shots
  by zone, passes, duels, tackles, distance covered, sprints, etc.) are
  available split by half, not just as a full-match total.
- **`incidents.parquet`** — goals, cards, substitutions, and period
  markers with exact minute (`time`, `added_time`) and the player(s)
  involved.
- **`momentum.parquet`** — SofaScore's per-minute "momentum" index (one
  row per match per minute) — their proprietary attacking-pressure
  score. Useful as a continuous, minute-by-minute performance signal to
  line up against the Kalshi minute candlesticks directly.
- **`shotmap.parquet`** — every shot in the tournament: player, minute,
  `xg`, `xgot` (xG on target), body part, situation (open play/corner/
  free kick/etc.), and pitch coordinates.

## Joining the three sources

None of Kalshi, FBref, and SofaScore share a common match ID. Join on
**team names + kickoff date** (all three include both):

- Kalshi: `event_ticker` encodes date + 3-letter team codes (e.g.
  `KXWCGAME-26JUL19ESPARG`); `occurrence_datetime` is the scheduled
  kickoff.
- FBref: `home_team`/`away_team` (full names) + `date` in `schedule.parquet`.
- SofaScore: `home_team`/`away_team` (full names) + `start_time` in
  `schedule.parquet`.

Team names differ slightly across sources (e.g. FBref's "Bosnia–Herz"
vs. SofaScore's likely full name) — building a small crosswalk table is
the first step before merging.
