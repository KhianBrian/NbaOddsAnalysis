import requests
from datetime import datetime, timezone, timedelta


BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "basketball_nba"

PROP_MARKETS = [
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_steals",
    "player_points_rebounds_assists",
    "player_rebounds_assists",
    "player_points_alternate",
    "player_rebounds_alternate",
    "player_assists_alternate",
]

MARKET_TO_STAT = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "threes",
    "player_steals": "steals",
    "player_points_rebounds_assists": "pra",
    "player_rebounds_assists": "ar",
    "player_points_alternate": "points",
    "player_rebounds_alternate": "rebounds",
    "player_assists_alternate": "assists",
}


class OddsClient:
    def __init__(self, api_key: str, preferred_books: list[str] | None = None):
        self.api_key = api_key
        self.preferred_books = preferred_books or [
            "draftkings", "fanduel", "betmgm", "caesars"
        ]

    def _get(self, path: str, params: dict) -> dict | list:
        params["apiKey"] = self.api_key
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=15)
        if resp.status_code == 401:
            raise RuntimeError("Invalid Odds API key. Check your ODDS_API_KEY in .env")
        if resp.status_code == 422:
            raise RuntimeError("Odds API rejected the request. Check your market/region params.")
        resp.raise_for_status()
        return resp.json()

    def get_todays_events(self) -> list[dict]:
        # Match games starting within the next 36 hours to handle UTC/local timezone drift
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=36)
        events = self._get(f"/sports/{SPORT}/events", {"dateFormat": "iso"})
        result = []
        for e in events:
            ct = e.get("commence_time", "")
            if not ct:
                continue
            try:
                game_time = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                if now <= game_time <= cutoff:
                    result.append(e)
            except ValueError:
                continue
        return result

    def _best_odds_for_outcome(
        self, bookmakers: list[dict], market_key: str, direction: str, player: str
    ) -> tuple[float | None, int | None, str | None]:
        best_line = None
        best_odds = None
        best_book = None

        for book in bookmakers:
            if book["key"] not in self.preferred_books:
                continue
            for market in book.get("markets", []):
                if market["key"] != market_key:
                    continue
                for outcome in market.get("outcomes", []):
                    if (
                        outcome.get("description", "").lower() == player.lower()
                        and outcome.get("name", "").lower() == direction.lower()
                    ):
                        if best_odds is None or outcome["price"] > best_odds:
                            best_odds = outcome["price"]
                            best_line = outcome.get("point")
                            best_book = book["key"]

        return best_line, best_odds, best_book

    def get_props_for_event(self, event_id: str) -> list[dict]:
        try:
            data = self._get(
                f"/sports/{SPORT}/events/{event_id}/odds",
                {
                    "regions": "us",
                    "markets": ",".join(PROP_MARKETS),
                    "oddsFormat": "american",
                },
            )
        except Exception:
            return []

        home_team = data.get("home_team", "")
        away_team = data.get("away_team", "")
        bookmakers = data.get("bookmakers", [])

        seen = set()
        props = []

        for book in bookmakers:
            for market in book.get("markets", []):
                market_key = market["key"]
                stat_type = MARKET_TO_STAT.get(market_key)
                if not stat_type:
                    continue

                for outcome in market.get("outcomes", []):
                    direction = outcome.get("name", "").lower()
                    if direction not in ("over", "under"):
                        continue

                    player = outcome.get("description", "")
                    line = outcome.get("point")
                    if not player or line is None:
                        continue

                    key = (player, stat_type, line, direction)
                    if key in seen:
                        continue
                    seen.add(key)

                    best_line, best_odds, best_book = self._best_odds_for_outcome(
                        bookmakers, market_key, direction.capitalize(), player
                    )

                    props.append({
                        "player": player,
                        "home_team": home_team,
                        "away_team": away_team,
                        "stat_type": stat_type,
                        "line": best_line if best_line is not None else line,
                        "over_odds": best_odds,
                        "book": best_book or book["key"],
                        "market_key": market_key,
                        "direction": direction,
                        "is_alternate": "alternate" in market_key,
                    })

        return props

    def get_todays_props(self) -> list[dict]:
        events = self.get_todays_events()
        if not events:
            return []

        all_props = []
        for event in events:
            props = self.get_props_for_event(event["id"])
            all_props.extend(props)

        # Deduplicate across events — same player/stat/line/direction can appear
        # in multiple future-game entries (e.g. OKC appearing in two potential Finals matchups)
        seen = set()
        deduped = []
        for prop in all_props:
            key = (prop["player"], prop["stat_type"], prop["line"], prop.get("direction", "over"))
            if key not in seen:
                seen.add(key)
                deduped.append(prop)

        return deduped
