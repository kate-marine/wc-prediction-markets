"""Pull World Cup 2026 match-performance data from SofaScore.

Complements the FBref pull with genuinely time-resolved signal that FBref
doesn't have: a per-minute "momentum" index, half-by-half (and extra-time)
splits of ~45 team stats, a minute-stamped incident feed (goals/cards/
subs/VAR), and a per-shot log with xG, xGOT, body part, situation, and
pitch coordinates.

See src/sofascore/client.py for a note on why this uses an undocumented
API (no official alternative exists) and how volume is kept modest.

Output (all under data/raw/sofascore/):
  - schedule.parquet     104 matches: teams, score, round, kickoff time
  - statistics.parquet   long-format team stats, one row per (match, period, stat)
  - incidents.parquet    goals/cards/subs/VAR with exact minute
  - momentum.parquet     per-minute momentum index, one row per (match, minute)
  - shotmap.parquet      every shot: player, xg, xgot, body part, situation, coordinates, minute
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sofascore.client import SofascoreClient  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "sofascore"


def flatten_event(e: dict) -> dict:
    round_info = e.get("roundInfo") or {}
    return {
        "event_id": e["id"],
        "home_team": e["homeTeam"]["name"],
        "away_team": e["awayTeam"]["name"],
        "home_score": (e.get("homeScore") or {}).get("current"),
        "away_score": (e.get("awayScore") or {}).get("current"),
        "start_timestamp": e["startTimestamp"],
        "start_time": pd.to_datetime(e["startTimestamp"], unit="s", utc=True),
        "tournament_name": e["tournament"]["name"],
        "round": round_info.get("round"),
        "round_name": round_info.get("name"),
        "status": (e.get("status") or {}).get("description"),
    }


def flatten_statistics(stats: list[dict], event_id: int) -> list[dict]:
    rows = []
    for period in stats:
        for group in period["groups"]:
            for item in group["statisticsItems"]:
                rows.append(
                    {
                        "event_id": event_id,
                        "period": period["period"],
                        "group_name": group["groupName"],
                        "stat_name": item["name"],
                        "stat_key": item.get("key"),
                        "home_value": item.get("homeValue"),
                        "away_value": item.get("awayValue"),
                        "home_display": item.get("home"),
                        "away_display": item.get("away"),
                    }
                )
    return rows


def flatten_incident(inc: dict, event_id: int) -> dict:
    player = inc.get("player") or {}
    player_in = inc.get("playerIn") or {}
    player_out = inc.get("playerOut") or {}
    return {
        "event_id": event_id,
        "incident_type": inc.get("incidentType"),
        "incident_class": inc.get("incidentClass"),
        "time": inc.get("time"),
        "added_time": inc.get("addedTime"),
        "time_seconds": inc.get("timeSeconds"),
        "is_home": inc.get("isHome"),
        "home_score": inc.get("homeScore"),
        "away_score": inc.get("awayScore"),
        "player_name": inc.get("playerName") or player.get("name"),
        "player_in_name": player_in.get("name"),
        "player_out_name": player_out.get("name"),
        "reason": inc.get("reason"),
        "text": inc.get("text"),
    }


def flatten_momentum(points: list[dict], event_id: int) -> list[dict]:
    return [{"event_id": event_id, "minute": p["minute"], "value": p["value"]} for p in points]


def flatten_shot(s: dict, event_id: int) -> dict:
    pc = s.get("playerCoordinates") or {}
    gc = s.get("goalMouthCoordinates") or {}
    player = s.get("player") or {}
    return {
        "event_id": event_id,
        "player_name": player.get("name"),
        "player_id": player.get("id"),
        "is_home": s.get("isHome"),
        "shot_type": s.get("shotType"),
        "situation": s.get("situation"),
        "body_part": s.get("bodyPart"),
        "xg": s.get("xg"),
        "xgot": s.get("xgot"),
        "time": s.get("time"),
        "added_time": s.get("addedTime"),
        "time_seconds": s.get("timeSeconds"),
        "player_x": pc.get("x"),
        "player_y": pc.get("y"),
        "goal_mouth_location": s.get("goalMouthLocation"),
        "goal_x": gc.get("x"),
        "goal_y": gc.get("y"),
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = SofascoreClient()

    print("Resolving World Cup 2026 season id...")
    season_id = client.get_season_id(2026)

    print("Fetching match list...")
    events = client.get_all_events(season_id)
    print(f"  {len(events)} matches found")

    schedule_df = pd.DataFrame([flatten_event(e) for e in events])
    schedule_df.to_parquet(DATA_DIR / "schedule.parquet", index=False)

    stats_rows, incident_rows, momentum_rows, shot_rows = [], [], [], []
    for event_id in tqdm([e["id"] for e in events], desc="Fetching match detail"):
        stats = client.get_statistics(event_id)
        if stats:
            stats_rows.extend(flatten_statistics(stats, event_id))

        incidents = client.get_incidents(event_id)
        if incidents:
            incident_rows.extend(flatten_incident(inc, event_id) for inc in incidents)

        momentum = client.get_momentum_graph(event_id)
        if momentum:
            momentum_rows.extend(flatten_momentum(momentum, event_id))

        shots = client.get_shotmap(event_id)
        if shots:
            shot_rows.extend(flatten_shot(s, event_id) for s in shots)

    pd.DataFrame(stats_rows).to_parquet(DATA_DIR / "statistics.parquet", index=False)
    pd.DataFrame(incident_rows).to_parquet(DATA_DIR / "incidents.parquet", index=False)
    pd.DataFrame(momentum_rows).to_parquet(DATA_DIR / "momentum.parquet", index=False)
    pd.DataFrame(shot_rows).to_parquet(DATA_DIR / "shotmap.parquet", index=False)

    print(f"Saved {len(schedule_df)} matches")
    print(f"Saved {len(stats_rows)} statistics rows")
    print(f"Saved {len(incident_rows)} incident rows")
    print(f"Saved {len(momentum_rows)} momentum rows")
    print(f"Saved {len(shot_rows)} shot rows")


if __name__ == "__main__":
    main()
