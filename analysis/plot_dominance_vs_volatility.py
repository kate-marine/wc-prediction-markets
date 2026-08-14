from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "analysis" / "figures"

TEAM_NAME_ALIASES = {
    "Cape Verde": "Cabo Verde",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Congo DR": "DR Congo",
    "Ivory Coast": "Côte d'Ivoire",
    "IR Iran": "Iran",
    "Turkiye": "Türkiye",
    "Curacao": "Curaçao",
    "Korea Republic": "South Korea",
}


def load_kalshi_outcome_volatility() -> pd.DataFrame:
    markets = pd.read_parquet(ROOT / "data/raw/kalshi/kxwcgame_markets.parquet")
    candles = pd.read_parquet(ROOT / "data/raw/kalshi/candlesticks/kxwcgame_minute.parquet")

    outcome_markets = markets[markets["result"] == "yes"].copy()

    price_range = candles.groupby("market_ticker")["price_close"].agg(lambda s: s.max() - s.min())
    outcome_markets["price_range"] = outcome_markets["market_ticker"].map(price_range)
    outcome_markets = outcome_markets.dropna(subset=["price_range"])

    # split string
    parts = outcome_markets["event_title"].str.split(" vs ", n=1, expand=True)
    team1 = parts[0].str.strip().replace(TEAM_NAME_ALIASES)
    team2 = parts[1].str.split(":").str[0].str.strip().replace(TEAM_NAME_ALIASES)
    outcome_markets["team_set"] = [frozenset(t) for t in zip(team1, team2)]
    return outcome_markets[["event_ticker", "team_set", "yes_team_subtitle", "price_range"]]


def load_sofascore_xg_margin() -> pd.DataFrame:
    stats = pd.read_parquet(ROOT / "data/raw/sofascore/statistics.parquet")
    schedule = pd.read_parquet(ROOT / "data/raw/sofascore/schedule.parquet")

    xg = stats[(stats["period"] == "ALL") & (stats["stat_name"] == "Expected goals")]
    xg = xg.merge(schedule[["event_id", "home_team", "away_team"]], on="event_id")
    xg["team_set"] = [frozenset(t) for t in zip(xg["home_team"], xg["away_team"])]
    xg["xg_margin"] = (xg["home_value"] - xg["away_value"]).abs()
    return xg[["team_set", "xg_margin"]]


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    kalshi = load_kalshi_outcome_volatility()
    xg = load_sofascore_xg_margin()

    # match Kalshi matches to SofaScore xG data
    merged = kalshi.merge(xg, on="team_set", how="inner")
    unmatched = kalshi[~kalshi["team_set"].isin(xg["team_set"])]
    if len(unmatched):
        print("Unmatched (likely a team-name spelling mismatch between sources):")
        for teams in unmatched["team_set"]:
            print(" ", " vs ".join(teams))

    corr = merged["xg_margin"].corr(merged["price_range"])

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(merged["xg_margin"], merged["price_range"], alpha=0.6, edgecolor="white", s=50)
    ax.set_xlabel("|xG margin|")
    ax.set_ylabel("Price range of the market pricing the actual outcome")
    ax.set_title("Performance dominance vs. price volatility")
    ax.annotate(
        f"Pearson r = {corr:.2f}\nn = {len(merged)}",
        xy=(0.05, 0.95),
        xycoords="axes fraction",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": "gray"},
    )

    fig.tight_layout()
    out_path = FIG_DIR / "dominance_vs_price_volatility.png"
    fig.savefig(out_path, dpi=150)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
