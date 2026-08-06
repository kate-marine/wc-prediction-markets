# wc-prediction-markets

Goal: I want to look at analyze prediction markets like kalshi during the 2026 World Cup. My main question is whether market prices respond more strongly to final results or
to a team’s underlying performance, measured through things like shot quality, possession,
cards, momentum, and overall dominance. I am also interested in whether public attention
or social media factors, such as famous players, underdog wins, or trending fan bases help
explain market movements beyond what would be expected from performance alone. More
broadly, I want to look at whether large market reactions are justified by new information
or whether they seem to be overreacting in the short term. 

## Data sources

### Kalshi (done — see `data/README.md`)

`scripts/fetch_kalshi_worldcup.py` pulls World Cup 2026 market data from
Kalshi's public API (no key required for market data):

- Per-match win/lose/tie prices at minute resolution around each of the
  104 matches (`KXWCGAME` series)
- Tournament-winner futures odds at hourly resolution for the whole
  tournament (`KXMENWORLDCUP` series)

Setup:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_kalshi_worldcup.py
```

Output lands in `data/raw/kalshi/` (gitignored — regenerate via the
script rather than committing it).

### Match performance: FBref + SofaScore (done — see `data/README.md`)

Two complementary sources, both scoped to the same 104 matches:

- `scripts/fetch_fbref_worldcup.py` — Opta-sourced, official-quality data
  via the `soccerdata` library (drives real Chrome via Selenium to get
  past FBref's Cloudflare check). Shooting/keeper/misc team stats per
  match, goal/card/sub event timeline, lineups, and full player-level
  match box scores (passing, carries, defense).
- `scripts/fetch_sofascore_worldcup.py` — hits SofaScore's public JSON
  API directly (`src/sofascore/client.py`). Adds what FBref doesn't
  have: a per-minute "momentum" index, ~45 team stats split by half
  (not just full-match totals), minute-stamped incidents, and a
  per-shot log with xG/xGOT and pitch coordinates. Note: SofaScore's
  FAQ states they don't license third-party API access, so this is used
  read-only at modest, personal-research volume — see the module
  docstring for details.

Run after the Kalshi setup above:

```
.venv/bin/python scripts/fetch_fbref_worldcup.py      # ~15-20 min, first run
.venv/bin/python scripts/fetch_sofascore_worldcup.py   # ~5 min
```

Both cache aggressively, so re-runs are fast. Output lands in
`data/raw/fbref/` and `data/raw/sofascore/` (gitignored).

None of the three sources share a match ID — `data/README.md` has the
join recipe (team names + kickoff date).

### Still needed

- Social/attention data (search trends, social mentions) — not yet
  sourced.