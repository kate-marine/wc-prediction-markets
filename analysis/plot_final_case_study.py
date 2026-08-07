"""Case study: Kalshi price paths vs SofaScore momentum for one match.

Picks the chronologically last KXWCGAME match (the final) and plots:
  - top: Kalshi's implied win probability for each outcome (home/away/tie)
  - bottom: SofaScore's per-minute momentum index

Goals are marked on both panels so it's easy to see whether the market
moves in step with the run of play (momentum) or mostly jumps at goals.

Run: .venv/bin/python analysis/plot_final_case_study.py
Output: analysis/figures/final_case_study.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "analysis" / "figures"


def load_kalshi_final():
    markets = pd.read_parquet(ROOT / "data/raw/kalshi/kxwcgame_markets.parquet")
    candles = pd.read_parquet(ROOT / "data/raw/kalshi/candlesticks/kxwcgame_minute.parquet")

    # `occurrence_datetime` is not a reliable kickoff time (null or even
    # *after* close_time for some matches -- see fetch_kalshi_worldcup.py).
    # close_time (settlement) is reliable, and the final is whichever
    # match settles last.
    final_ticker = markets.loc[markets["close_time"].idxmax(), "event_ticker"]
    final_markets = markets[markets["event_ticker"] == final_ticker]

    final_candles = candles[candles["market_ticker"].isin(final_markets["market_ticker"])].copy()
    final_candles = final_candles.merge(
        final_markets[["market_ticker", "yes_team_subtitle"]], on="market_ticker"
    )

    home_team, away_team = final_markets["event_title"].iloc[0].split(":")[0].split(" vs ")
    return final_candles, home_team, away_team


def load_sofascore_match(home_team: str, away_team: str):
    schedule = pd.read_parquet(ROOT / "data/raw/sofascore/schedule.parquet")
    teams = {home_team, away_team}
    match = schedule[schedule.apply(lambda r: {r["home_team"], r["away_team"]} == teams, axis=1)]
    if match.empty:
        raise ValueError(f"No SofaScore match found for {home_team} vs {away_team}")
    match = match.iloc[0]
    event_id = match["event_id"]

    momentum = pd.read_parquet(ROOT / "data/raw/sofascore/momentum.parquet")
    momentum = momentum[momentum["event_id"] == event_id]

    incidents = pd.read_parquet(ROOT / "data/raw/sofascore/incidents.parquet")
    goals = incidents[(incidents["event_id"] == event_id) & (incidents["incident_type"] == "goal")]
    return momentum, goals, match


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    candles, home_team, away_team = load_kalshi_final()
    momentum, goals, sofa_match = load_sofascore_match(home_team, away_team)

    # SofaScore's kickoff time (start_time) is authoritative; Kalshi's
    # own `occurrence_datetime` field isn't (see load_kalshi_final).
    kickoff = sofa_match["start_time"]
    match_date = kickoff.date()
    candles["minutes_since_kickoff"] = (candles["timestamp"] - kickoff).dt.total_seconds() / 60

    fig, (ax_price, ax_momentum) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True, height_ratios=[2, 1]
    )

    for label, grp in candles.groupby("yes_team_subtitle"):
        ax_price.plot(grp["minutes_since_kickoff"], grp["price_close"], label=label, linewidth=1.5)
    ax_price.set_ylabel("Kalshi implied probability")
    ax_price.set_title(f"{home_team} vs {away_team} ({match_date}): price vs momentum")
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.set_ylim(-0.02, 1.02)

    ax_momentum.plot(momentum["minute"], momentum["value"], color="tab:gray", linewidth=1)
    ax_momentum.axhline(0, color="black", linewidth=0.5)
    ax_momentum.set_ylabel("SofaScore momentum\n(+ home / − away)")
    ax_momentum.set_xlabel("Minutes since kickoff")

    for _, goal in goals.iterrows():
        scorer = home_team if goal["is_home"] else away_team
        for ax in (ax_price, ax_momentum):
            ax.axvline(goal["time"], color="tab:red", linestyle="--", linewidth=1, alpha=0.7)
        ax_price.annotate(
            f"Goal: {scorer}\n({goal['player_name']})",
            xy=(goal["time"], 1.0),
            xytext=(goal["time"], 1.05),
            fontsize=7,
            ha="center",
            annotation_clip=False,
        )

    fig.tight_layout()
    out_path = FIG_DIR / "final_case_study.png"
    fig.savefig(out_path, dpi=150)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
