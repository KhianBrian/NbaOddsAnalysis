import statistics


def compute_splits(
    games_l10: list[float],
    games_l5: list[float],
    line: float,
    direction: str = "over",
) -> dict:
    """
    Compute statistical splits for a player / stat / line / direction combo.

    direction: "over" — looking for the player to exceed the line
               "under" — looking for the player to fall short of the line
    """
    if len(games_l5) < 3:
        return {}

    l10 = games_l10[:10] if len(games_l10) >= 3 else games_l10
    l5 = games_l5[:5] if len(games_l5) >= 5 else games_l5

    # Hit rates depend on direction
    if direction == "under":
        hits_l10 = sum(1 for v in l10 if v < line)
        hits_l5 = sum(1 for v in l5 if v < line)
    else:
        hits_l10 = sum(1 for v in l10 if v > line)
        hits_l5 = sum(1 for v in l5 if v > line)

    hit_rate_l10 = hits_l10 / len(l10)
    hit_rate_l5 = hits_l5 / len(l5)

    avg_l10 = sum(l10) / len(l10)
    avg_l5 = sum(l5) / len(l5)

    max_l10 = max(l10)
    min_l10 = min(l10)

    # Trend: positive = player's recent output is rising
    trend = (avg_l5 - avg_l10) / avg_l10 if avg_l10 > 0 else 0

    # Line value: positive = book's line is set below player's average (value on over)
    # Scoring layer negates this for under bets
    line_value = (avg_l10 - line) / line if line > 0 else 0

    # Standard deviation and coefficient of variation
    std_dev = round(statistics.stdev(l10), 4) if len(l10) >= 2 else 0.0
    coefficient_of_variation = round(std_dev / avg_l10, 4) if avg_l10 > 0 else 0.0

    # Last 3 games
    games_l3 = l5[:3]
    last_3_avg = round(sum(games_l3) / len(games_l3), 2) if games_l3 else 0.0

    # Blowout games: games where player posted < 50% of their L10 average
    # For OVER bets: these are bad (benching/foul trouble).
    # For UNDER bets: these are good (player cratered well below the line).
    blowout_threshold = avg_l10 * 0.50
    blowout_games = sum(1 for v in l10 if v < blowout_threshold)

    # Outlier high games: games where player posted > 150% of L10 average
    # For UNDER bets: these are bad (explosive game = went way over).
    # For OVER bets: not penalised (having a big game is fine).
    outlier_high_threshold = avg_l10 * 1.50
    outlier_high_games = sum(1 for v in l10 if v > outlier_high_threshold)

    return {
        "small_sample": len(l10) < 5,   # AI layer will flag this as a caution
        "games_available": len(l10),
        "hit_rate_l5": round(hit_rate_l5, 4),
        "hit_rate_l10": round(hit_rate_l10, 4),
        "avg_l5": round(avg_l5, 2),
        "avg_l10": round(avg_l10, 2),
        "max_l10": round(max_l10, 2),
        "min_l10": round(min_l10, 2),
        "hits_l5": hits_l5,
        "hits_l10": hits_l10,
        "games_l5": l5,
        "games_l10": l10,
        "trend": round(trend, 4),
        "line_value": round(line_value, 4),
        "std_dev": std_dev,
        "coefficient_of_variation": coefficient_of_variation,
        "last_3_avg": last_3_avg,
        "games_l3": games_l3,
        "blowout_games": blowout_games,
        "outlier_high_games": outlier_high_games,
        "direction": direction,
    }
