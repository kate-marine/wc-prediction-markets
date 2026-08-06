"""Client for SofaScore's undocumented public JSON API.

SofaScore does not publish or license this API for third-party use (see
their FAQ), so this is used sparingly and at low, personal-research
volume, mirroring the endpoint set used by open-source scraper projects
(e.g. LanusStats, apdmatos/sofascore-api). All data pulled here is the
same read-only match data shown on sofascore.com.

Requires `tls_requests` rather than plain `requests`: SofaScore's edge
blocks the default Python TLS fingerprint, and this library impersonates
a browser's TLS handshake to get through.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import tls_requests

API = "https://api.sofascore.com/api/v1"

WORLD_CUP_TOURNAMENT_ID = 16


@dataclass
class SofascoreClient:
    request_delay_seconds: float = 0.5
    max_retries: int = 5

    def __post_init__(self) -> None:
        self._client = tls_requests.Client()

    def _get(self, path: str) -> dict[str, Any] | None:
        url = f"{API}{path}"
        backoff = 1.0
        for attempt in range(self.max_retries):
            resp = self._client.get(url)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries - 1:
                    resp.raise_for_status()
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            time.sleep(self.request_delay_seconds)
            return resp.json()
        raise RuntimeError(f"unreachable: exhausted retries for {url}")

    def get_season_id(self, year: int, tournament_id: int = WORLD_CUP_TOURNAMENT_ID) -> int:
        data = self._get(f"/unique-tournament/{tournament_id}/seasons")
        for season in data["seasons"]:
            if season["year"] == str(year):
                return season["id"]
        raise ValueError(f"no season found for year {year}")

    def get_all_events(
        self, season_id: int, tournament_id: int = WORLD_CUP_TOURNAMENT_ID
    ) -> list[dict[str, Any]]:
        """Paginates .../events/last/{page} until exhausted; returns every match."""
        events: dict[int, dict[str, Any]] = {}
        page = 0
        while True:
            data = self._get(f"/unique-tournament/{tournament_id}/season/{season_id}/events/last/{page}")
            if not data or not data.get("events"):
                break
            for e in data["events"]:
                events[e["id"]] = e
            if not data.get("hasNextPage"):
                break
            page += 1
        return list(events.values())

    def get_statistics(self, event_id: int) -> list[dict[str, Any]] | None:
        data = self._get(f"/event/{event_id}/statistics")
        return data["statistics"] if data else None

    def get_incidents(self, event_id: int) -> list[dict[str, Any]] | None:
        data = self._get(f"/event/{event_id}/incidents")
        return data["incidents"] if data else None

    def get_momentum_graph(self, event_id: int) -> list[dict[str, Any]] | None:
        data = self._get(f"/event/{event_id}/graph")
        return data["graphPoints"] if data else None

    def get_shotmap(self, event_id: int) -> list[dict[str, Any]] | None:
        data = self._get(f"/event/{event_id}/shotmap")
        return data["shotmap"] if data else None
