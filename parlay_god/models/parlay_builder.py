from itertools import combinations


SGP_HIGH_TOTAL_THRESHOLD = 70.0
SGP_CORRELATION_BONUS = 0.05


def _is_anti_correlated(leg_a: dict, leg_b: dict) -> bool:
    """
    Block same-player, same-stat, opposite-direction combos — they directly
    contradict each other (e.g. Player A over 25.5 pts + Player A under 25.5 pts).
    All other combinations are allowed; Claude handles softer conflicts.
    """
    if leg_a.get("home_team") != leg_b.get("home_team"):
        return False

    same_player = leg_a["player"] == leg_b["player"]
    same_stat = leg_a["stat_type"] == leg_b["stat_type"]
    opposite_dir = leg_a.get("direction", "over") != leg_b.get("direction", "over")

    return same_player and same_stat and opposite_dir


def _is_high_total_sgp(legs: list[dict]) -> bool:
    if len(legs) < 2:
        return False
    home_teams = set(l.get("home_team") for l in legs)
    if len(home_teams) != 1:
        return False
    scores = [l.get("final_score", 0) for l in legs]
    return all(s > SGP_HIGH_TOTAL_THRESHOLD for s in scores) and all(s > 0 for s in scores)


def _est_combined_hr(legs: list[dict], is_sgp: bool = False, high_total: bool = False) -> float:
    combined = 1.0
    for leg in legs:
        combined *= leg.get("weighted_hr", 0.5)
    if is_sgp and high_total:
        combined = min(combined + SGP_CORRELATION_BONUS, 0.99)
    return round(combined, 4)


def _leg_label(leg: dict) -> str:
    direction = leg.get("direction", "over")
    prefix = "o" if direction == "over" else "u"
    return f"{leg['player']} {prefix}{leg['line']} {leg['stat_type']}"


def build_parlays(
    plays: list[dict],
    min_legs: int = 2,
    max_legs: int = 6,
    top_n: int = 12,
    target_combined_hr: float = 0.35,
    prefer_same_game: bool = True,
) -> list[dict]:
    """Build parlay combinations (2–6 legs) from the top-ranked plays."""
    eligible = [p for p in plays if p.get("ai_flag") != "red"]
    top = sorted(eligible, key=lambda p: p.get("final_score", 0), reverse=True)[:top_n]

    parlays = []

    for n_legs in range(min_legs, max_legs + 1):
        for combo in combinations(range(len(top)), n_legs):
            legs = [top[i] for i in combo]

            anti = any(
                _is_anti_correlated(legs[a], legs[b])
                for a in range(len(legs))
                for b in range(a + 1, len(legs))
            )
            if anti:
                continue

            games = set((l.get("home_team"), l.get("away_team")) for l in legs)
            is_sgp = len(games) == 1
            high_total = _is_high_total_sgp(legs) if is_sgp else False

            est_hr = _est_combined_hr(legs, is_sgp=is_sgp, high_total=high_total)
            if est_hr < target_combined_hr:
                continue

            parlays.append({
                "legs": legs,
                "leg_indices": list(combo),
                "n_legs": n_legs,
                "est_combined_hr": est_hr,
                "parlay_type": "SGP" if is_sgp else "multi",
                "sgp_high_total_bonus": high_total,
                "summary": " + ".join(_leg_label(l) for l in legs),
                "avg_final_score": round(
                    sum(l.get("final_score", 0) for l in legs) / n_legs, 2
                ),
            })

    parlays.sort(
        key=lambda p: (
            (1 if prefer_same_game and p["parlay_type"] == "SGP" else 0),
            p["est_combined_hr"],
            p["avg_final_score"],
        ),
        reverse=True,
    )

    return parlays[:25]
