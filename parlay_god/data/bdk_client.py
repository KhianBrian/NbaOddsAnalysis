import time
import requests
from rapidfuzz import process, fuzz


STAT_MAP = {
    "points": "pts",
    "rebounds": "reb",
    "assists": "ast",
    "threes": "fg3m",
    "steals": "stl",
}

COMBO_STAT_MAP = {
    "pra": ["pts", "reb", "ast"],
    "ar": ["ast", "reb"],
}

BASE_URL = "https://api.balldontlie.io/v1"
DELAY = 0.4  # seconds between calls to stay under rate limit


class BallDontLieClient:
    def __init__(self, api_key: str):
        self.headers = {"Authorization": api_key}
        self._player_cache: dict[str, int] = {}
        self._stats_cache: dict[int, list] = {}  # keyed by player_id

    def _get(self, path: str, params: dict) -> dict | None:
        try:
            resp = requests.get(
                f"{BASE_URL}{path}", headers=self.headers, params=params, timeout=10
            )
            if resp.status_code == 429:
                return None  # rate limited — skip silently
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def _find_player_id(self, name: str) -> int | None:
        if name in self._player_cache:
            return self._player_cache[name]

        time.sleep(DELAY)
        data_resp = self._get("/players", {"search": name, "per_page": 5})
        if data_resp is None:
            return None

        data = data_resp.get("data", [])
        if not data:
            return None

        candidates = [f"{p['first_name']} {p['last_name']}" for p in data]
        match, score, idx = process.extractOne(name, candidates, scorer=fuzz.token_sort_ratio)

        if score < 70:
            return None

        pid = data[idx]["id"]
        self._player_cache[name] = pid
        return pid

    def get_player_stats_for_play(
        self, player_name: str, stat_type: str, line: float
    ) -> dict | None:
        player_id = self._find_player_id(player_name)
        if player_id is None:
            return None

        if stat_type in COMBO_STAT_MAP:
            needed_cols = COMBO_STAT_MAP[stat_type]
        else:
            col = STAT_MAP.get(stat_type)
            if col is None:
                return None
            needed_cols = [col]

        # Fetch game log once per player, cache for all stat types
        if player_id not in self._stats_cache:
            time.sleep(DELAY)
            result = self._get(
                "/stats",
                {"player_ids[]": player_id, "per_page": 15, "seasons[]": [2025]},
            )
            if result is None:
                return None
            games = result.get("data", [])
            games_sorted = sorted(games, key=lambda g: g.get("date", ""), reverse=True)
            self._stats_cache[player_id] = games_sorted

        games_sorted = self._stats_cache[player_id]

        if len(games_sorted) < 5:
            return None

        values = [
            sum(g.get(col, 0) or 0 for col in needed_cols)
            for g in games_sorted[:10]
        ]

        return {
            "player_id": player_id,
            "games_l10": values[:10],
            "games_l5": values[:5],
            "source": "balldontlie",
        }
