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

### Still needed

- Match performance data (xG, possession, shots, cards, momentum) —
  not yet sourced.
- Social/attention data (search trends, social mentions) — not yet
  sourced.