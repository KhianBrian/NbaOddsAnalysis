def score_play(
    splits: dict,
    weights: dict,
    thresholds: dict,
    direction: str = "over",
) -> dict:
    """
    Layer 1 rule engine. Scores a single play on 6 factors.
    Direction-aware: factors flip signs for under bets where appropriate.

    Factor 1 — Hit Rate Score     (max  60 pts)   — direction-aware hit rate
    Factor 2 — Trend Score        (−10 to +10 pts) — negated for under
    Factor 3 — Line Value Score   (−15 to +15 pts) — negated for under
    Factor 4 — Consistency Score  ( −8 to  +8 pts) — same for both directions
    Factor 5 — Volume Trend       ( −5 to  +5 pts) — negated for under
    Factor 6 — Outlier Risk       (−10 to  +6 pts) — direction-aware
    """
    if not splits:
        return {"rule_score": 0, "passes_threshold": False, "weighted_hr": 0}

    recent_w = weights.get("recent_hit_rate", 0.60)
    primary_w = weights.get("primary_hit_rate", 0.40)
    min_hr = thresholds.get("min_hit_rate", 0.65)
    min_score = thresholds.get("min_rule_score", 45)

    weighted_hr = (splits["hit_rate_l5"] * recent_w) + (splits["hit_rate_l10"] * primary_w)

    # ------------------------------------------------------------------ #
    # Factor 1: Hit Rate Score (max 60 pts) — direction-aware via compute_splits
    # ------------------------------------------------------------------ #
    factor_hr = weighted_hr * 60

    # ------------------------------------------------------------------ #
    # Factor 2: Trend Score (−10 to +10 pts)
    # Over:  rising trend (avg_l5 > avg_l10) = positive signal
    # Under: falling trend (avg_l5 < avg_l10) = positive signal → negate
    # ------------------------------------------------------------------ #
    trend = splits.get("trend", 0)
    trend_signal = trend if direction == "over" else -trend
    factor_trend = max(-10.0, min(10.0, trend_signal * 20))

    # ------------------------------------------------------------------ #
    # Factor 3: Line Value Score (−15 to +15 pts)
    # line_value = (avg_l10 - line) / line
    # Over:  positive when avg > line (book set it too low)
    # Under: positive when avg < line (book set it too high) → negate
    # ------------------------------------------------------------------ #
    line_value = splits.get("line_value", 0)
    line_value_signal = line_value if direction == "over" else -line_value
    factor_value = max(-15.0, min(15.0, line_value_signal * 30))

    # ------------------------------------------------------------------ #
    # Factor 4: Consistency Score (−8 to +8 pts) — same for both directions
    # Low CV = predictable output = reliable bet regardless of direction
    # ------------------------------------------------------------------ #
    cv = splits.get("coefficient_of_variation", 0)
    if cv < 0.20:
        factor_consistency = 8.0
    elif cv < 0.35:
        factor_consistency = 3.0
    elif cv <= 0.50:
        factor_consistency = 0.0
    else:
        factor_consistency = -8.0

    # ------------------------------------------------------------------ #
    # Factor 5: Volume Trend (−5 to +5 pts)
    # Over:  rising L3 vs prior-2 in L5 = positive
    # Under: falling L3 vs prior-2 in L5 = positive → negate
    # Requires at least 4 games; skipped for very small playoff samples
    # ------------------------------------------------------------------ #
    games_l5 = splits.get("games_l5", [])
    factor_volume = 0.0
    if len(games_l5) >= 4:
        avg_recent_3 = sum(games_l5[:3]) / 3
        avg_prior_2 = sum(games_l5[3:]) / len(games_l5[3:])
        if avg_prior_2 > 0:
            vol_change = (avg_recent_3 - avg_prior_2) / avg_prior_2
            if direction == "under":
                vol_change = -vol_change
            if vol_change > 0.05:
                factor_volume = 5.0
            elif vol_change < -0.05:
                factor_volume = -5.0

    # ------------------------------------------------------------------ #
    # Factor 6: Outlier Risk (direction-aware)
    #
    # Over:  blowout_games (< 50% of avg) = bad → penalty up to −10
    # Under: blowout_games = good signal (player cratered) → bonus up to +6
    #        outlier_high_games (> 150% of avg) = bad for under → penalty
    # ------------------------------------------------------------------ #
    blowout_games = splits.get("blowout_games", 0)
    outlier_high_games = splits.get("outlier_high_games", 0)

    if direction == "over":
        if blowout_games >= 4:
            factor_outlier = -10.0
        elif blowout_games == 3:
            factor_outlier = -6.0
        elif blowout_games == 2:
            factor_outlier = -3.0
        else:
            factor_outlier = 0.0
    else:
        # Blowout games are a green signal for under (player went way under)
        blowout_bonus = min(blowout_games * 1.5, 6.0)
        # Outlier highs are a red signal for under (player can explode)
        high_penalty = min(outlier_high_games * 3.0, 9.0)
        factor_outlier = round(blowout_bonus - high_penalty, 2)
        factor_outlier = max(-10.0, min(6.0, factor_outlier))

    # ------------------------------------------------------------------ #
    # Composite rule score
    # ------------------------------------------------------------------ #
    rule_score = round(
        factor_hr + factor_trend + factor_value
        + factor_consistency + factor_volume + factor_outlier,
        2,
    )

    passes = weighted_hr >= min_hr and rule_score >= min_score

    return {
        "weighted_hr": round(weighted_hr, 4),
        "rule_score": rule_score,
        "factor_hit_rate": round(factor_hr, 2),
        "factor_trend": round(factor_trend, 2),
        "factor_value": round(factor_value, 2),
        "factor_consistency": round(factor_consistency, 2),
        "factor_volume": round(factor_volume, 2),
        "factor_outlier": round(factor_outlier, 2),
        "passes_threshold": passes,
    }
