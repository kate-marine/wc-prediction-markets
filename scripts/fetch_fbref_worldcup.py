"""Pull World Cup 2026 match-performance data from FBref (Opta-sourced).

Uses the `soccerdata` library, which drives a real Chrome browser via
Selenium to get past FBref's Cloudflare bot check, and self-throttles to
~7s/request to respect FBref's crawl policy. Pages are cached to disk
(~/soccerdata/data/FBref), so re-running this script is cheap.

Note on efficiency: read_events / read_lineup / read_player_match_stats
all scrape the *same* per-match report page (/en/matches/{game_id}), just
parsing different tables out of it. Calling read_events first populates
the page cache; the other calls then reuse that cached HTML instead of
re-fetching, so pulling all of them costs about the same as pulling one.

Output (all under data/raw/fbref/):
  - schedule.parquet                 104 matches: teams, score, venue, referee, report link
  - team_match_shooting.parquet      208 rows (104 matches x 2 teams): shots, SoT, xG, npxG, distance, PK
  - team_match_keeper.parquet        208 rows: goals against, saves, PSxG, passes
  - team_match_misc.parquet          208 rows: cards, fouls, tackles won, aerials, recoveries

Team-season match logs from FBref cover every match a team played back to
2023 (qualifiers etc.), not just this tournament, and don't reliably
label which team a row belongs to (soccerdata leaves that column null).
restrict_to_tournament_and_fix_team() filters to the 104 WC 2026 matches
and derives the correct team identity by joining on (date, opponent)
against the schedule.
  - events.parquet                   goal/card/substitution timeline with the players involved
  - lineup.parquet                   starting XI, formations, substitutes per match
  - player_match_summary.parquet     per-player per-match: passing, carries, defense, shooting
  - player_match_keepers.parquet     per-player per-match goalkeeper detail
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import soccerdata as sd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "fbref"


def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """Flattens MultiIndex columns and fixes mixed-type object columns.

    FBref match logs mix int and str representations of the same numeric
    value across different scraped pages (e.g. GF is `0` on one team's
    page and `'0'` on another's), which pyarrow rejects outright.
    """
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            "_".join(str(p) for p in col if p) or f"col{i}"
            for i, col in enumerate(df.columns)
        ]
    for col in df.columns[df.dtypes == "object"]:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() == df[col].notna().sum():
            df[col] = numeric
        else:
            df[col] = df[col].astype(str).where(df[col].notna(), None)
    return df


def restrict_to_tournament_and_fix_team(df: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    """Filters team-season match logs down to the 104 WC 2026 matches and
    fixes the `team` column, which soccerdata leaves null (it's set from
    an unrelated function argument upstream). Team-season logs otherwise
    include every match the team played back to 2023 (qualifiers etc.),
    identifiable only by (date, opponent) -- not tournament-scoped.
    """
    df = df.reset_index(drop=False).drop(columns=["team"])
    df["date"] = pd.to_datetime(df["date"]).dt.date

    sched = schedule.reset_index()[["home_team", "away_team", "date"]].copy()
    sched["date"] = pd.to_datetime(sched["date"]).dt.date
    home_pairs = sched.rename(columns={"home_team": "team", "away_team": "opponent"})
    away_pairs = sched.rename(columns={"away_team": "team", "home_team": "opponent"})
    valid_pairs = pd.concat([home_pairs, away_pairs], ignore_index=True)[
        ["date", "team", "opponent"]
    ]

    return df.merge(valid_pairs, on=["date", "opponent"], how="inner")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fbref = sd.FBref(leagues="INT-World Cup", seasons=2026)

    print("Fetching schedule...")
    schedule = fbref.read_schedule()
    schedule.to_parquet(DATA_DIR / "schedule.parquet")
    print(f"  {len(schedule)} matches")

    for stat_type in ["shooting", "keeper", "misc"]:
        print(f"Fetching team match stats: {stat_type}...")
        df = sanitize(fbref.read_team_match_stats(stat_type=stat_type, force_cache=True))
        df = restrict_to_tournament_and_fix_team(df, schedule)
        df.to_parquet(DATA_DIR / f"team_match_{stat_type}.parquet")
        print(f"  {len(df)} rows")

    match_ids = schedule.reset_index()["game_id"].dropna().unique().tolist()
    print(f"Fetching per-match detail for {len(match_ids)} matches...")

    print("  events (goals/cards/subs timeline)...")
    events = sanitize(fbref.read_events(match_id=match_ids))
    events.to_parquet(DATA_DIR / "events.parquet")
    print(f"    {len(events)} rows")

    print("  lineups...")
    lineup = sanitize(fbref.read_lineup(match_id=match_ids))
    lineup.to_parquet(DATA_DIR / "lineup.parquet")
    print(f"    {len(lineup)} rows")

    print("  player match stats: summary...")
    player_summary = sanitize(
        fbref.read_player_match_stats(stat_type="summary", match_id=match_ids)
    )
    player_summary.to_parquet(DATA_DIR / "player_match_summary.parquet")
    print(f"    {len(player_summary)} rows")

    print("  player match stats: keepers...")
    player_keepers = sanitize(
        fbref.read_player_match_stats(stat_type="keepers", match_id=match_ids)
    )
    player_keepers.to_parquet(DATA_DIR / "player_match_keepers.parquet")
    print(f"    {len(player_keepers)} rows")

    print("Done.")


if __name__ == "__main__":
    main()
