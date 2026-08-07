# Analysis

Preliminary, exploratory plots over the data in `data/raw/` — pandas +
matplotlib, no framework. Each script is standalone and writes a PNG to
`analysis/figures/` (gitignored, same reasoning as `data/raw/`).

- **`plot_final_case_study.py`** — single-match deep dive on the final
  (Spain vs Argentina): Kalshi's implied win/lose/tie probabilities
  against SofaScore's per-minute momentum, with the goal marked. Shows
  the market pricing in a draw well before full time, tracking the
  run of play, then repricing sharply at the extra-time goal.

- **`plot_dominance_vs_volatility.py`** — tournament-wide scatter of
  |xG margin| (SofaScore, how lopsided a match was) against the price
  range of the Kalshi market that priced the actual outcome (how much
  that market moved before settling). All 104 matches, r = -0.38: bigger
  performance blowouts tend toward calmer, more confidently-priced
  markets; closer matches show much more varied volatility, including
  some of the largest swings.

Run either with `.venv/bin/python analysis/<script>.py`.

Both scripts join Kalshi to SofaScore by team names (see the crosswalk
note in `data/README.md`); `plot_dominance_vs_volatility.py` has a small
`TEAM_NAME_ALIASES` map for the ~8 teams the two sources spell
differently (Cape Verde/Cabo Verde, Ivory Coast/Côte d'Ivoire, etc.).
