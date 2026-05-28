import time
import pandas as pd
from rapidfuzz import process, fuzz
from nba_api.stats.endpoints import playergamelog, scoreboardv2
from nba_api.stats.static import players as nba_players_static


STAT_COLUMN_MAP = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "threes": "FG3M",
    "steals": "STL",
}

COMBO_STAT_MAP = {
    "pra": ["PTS", "REB", "AST"],
    "ar": ["AST", "REB"],
}


class NBAClient:
    def __init__(self, delay: float = 0.6, season: str = "2025-26"):
        self.delay = delay
        self.season = season
        self._player_id_cache: dict[str, int] = {}
        self._game_log_cache: dict[int, pd.DataFrame] = {}  # keyed by player_id
        self._all_players: list[dict] | None = None

    def _load_all_players(self):
        if self._all_players is None:
            self._all_players = nba_players_static.get_players()

    def find_player_id(self, name: str) -> int | None:
        if name in self._player_id_cache:
            return self._player_id_cache[name]

        self._load_all_players()
        all_names = [p["full_name"] for p in self._all_players]
        match, score, _ = process.extractOne(name, all_names, scorer=fuzz.token_sort_ratio)

        if score < 70:
            return None

        for p in self._all_players:
            if p["full_name"] == match:
                self._player_id_cache[name] = p["id"]
                return p["id"]

        return None

    def get_todays_games(self) -> list[dict]:
        try:
            board = scoreboardv2.ScoreboardV2()
            time.sleep(self.delay)
            games_df = board.game_header.get_data_frame()
            return [
                {
                    "game_id": row["GAME_ID"],
                    "home_team": row["HOME_TEAM_ID"],
                    "away_team": row["VISITOR_TEAM_ID"],
                    "status": row.get("GAME_STATUS_TEXT", ""),
                }
                for _, row in games_df.iterrows()
            ]
        except Exception as e:
            raise RuntimeError(f"Could not fetch today's games from NBA API: {e}")

    def get_player_game_log(self, player_id: int, last_n: int = 10) -> pd.DataFrame:
        if player_id in self._game_log_cache:
            return self._game_log_cache[player_id].head(last_n)

        # Playoffs only — regular season stats are not comparable
        for season_type in ("Playoffs", "Regular Season"):
            try:
                log = playergamelog.PlayerGameLog(
                    player_id=player_id,
                    season=self.season,
                    season_type_all_star=season_type,
                )
                time.sleep(self.delay)
                df = log.player_game_log.get_data_frame()
                if not df.empty:
                    self._game_log_cache[player_id] = df
                    return df.head(last_n)
            except Exception:
                continue

        raise RuntimeError(f"NBA API returned no game log for player {player_id}")

    def get_player_stats_for_play(
        self, player_name: str, stat_type: str, line: float
    ) -> dict | None:
        player_id = self.find_player_id(player_name)
        if player_id is None:
            return None

        try:
            df = self.get_player_game_log(player_id, last_n=10)
        except RuntimeError:
            return None

        if df.empty:
            return None

        # Combo stats: sum multiple columns per game
        if stat_type in COMBO_STAT_MAP:
            cols = COMBO_STAT_MAP[stat_type]
            if not all(c in df.columns for c in cols):
                return None
            values = df[cols].sum(axis=1).tolist()
        else:
            col = STAT_COLUMN_MAP.get(stat_type)
            if col is None or col not in df.columns:
                return None
            values = df[col].tolist()

        l10 = values[:10]
        l5 = values[:5]

        if len(l5) < 5:
            return None

        return {
            "player_id": player_id,
            "games_l10": l10,
            "games_l5": l5,
            "source": "nba_api",
        }
