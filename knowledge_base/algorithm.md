# ParlayGod — Algorithm Reference

## Overview

Every play passes through two layers before appearing in the report.

---

## Layer 1 — Rule Engine (scoring.py)

Produces a deterministic score from a six-factor model. The theoretical maximum is approximately 98 points. The minimum threshold to advance to the AI layer is a rule score of 45 (plus the separate hit rate floor of 65%).

### Factor 1: Weighted Hit Rate (max 60 points)

```
hit_rate_l5  = games where player exceeded the line / 5
hit_rate_l10 = games where player exceeded the line / 10
weighted_hr  = (hit_rate_l5 × 0.60) + (hit_rate_l10 × 0.40)
factor_score = weighted_hr × 60
```

The L5 window carries more weight (0.60) because recent form is more predictive than the full 10-game baseline. A player hitting 4/5 recent games counts more than 7/10 overall.

Example: Player hits 4/5 recent and 7/10 overall.
weighted_hr = (0.80 × 0.60) + (0.70 × 0.40) = 0.76
factor_score = 0.76 × 60 = 45.6

### Factor 2: Trend Score (−10 to +10 points)

```
avg_l5     = average stat in last 5 games
avg_l10    = average stat in last 10 games
trend      = (avg_l5 - avg_l10) / avg_l10
trend_pts  = clamp(trend × 20, −10, +10)
```

Positive means the player is outperforming their baseline recently. Negative means they are regressing. A 10% improvement in L5 vs L10 maps to +2 points; a 50% improvement (hot streak) maps to the +10 ceiling.

### Factor 3: Line Value Score (−15 to +15 points)

```
line_value = (avg_l10 - line) / line
value_pts  = clamp(line_value × 30, −15, +15)
```

Positive = the book's line is set below the player's L10 average — structural value on the over. Negative = the line exceeds the player's average — the book is daring you to bet against the grain.

### Factor 4: Consistency Score (−8 to +8 points)

```
std_dev                 = standard deviation of last 10 game values
coefficient_of_variation = std_dev / avg_l10
```

| CV range       | Points awarded | Interpretation                          |
|----------------|----------------|-----------------------------------------|
| CV < 0.20      | +8             | Machine-like consistency — low risk     |
| CV 0.20–0.35   | +3             | Reliable with minor game-to-game swings |
| CV 0.35–0.50   | 0              | Moderate volatility — neutral signal    |
| CV > 0.50      | −8             | Wild swings — prop value is unreliable  |

Rationale: a player averaging 22 points but ranging from 8 to 40 is a fundamentally different prop than a player averaging 22 and ranging from 17 to 27. The consistency score captures this distinction that hit rate alone misses.

### Factor 5: Volume Trend (−5 to +5 points)

```
games_l3      = the 3 most recent games (from the L5 window)
games_prior_2 = the 2 games before that in the L5 window
avg_recent_3  = mean of games_l3
avg_prior_2   = mean of games_prior_2
vol_change    = (avg_recent_3 - avg_prior_2) / avg_prior_2
```

If vol_change > 5%  → +5 (rising production — recent usage or role expansion)
If vol_change < −5% → −5 (falling production — usage dip, load management signal)
Otherwise           → 0  (flat — no directional volume signal)

Rationale: this catches situations where a player's recent role has shifted — a player getting +8 minutes per game over the last three due to a teammate's injury will show up here before the hit rate catches up.

### Factor 6: Blowout Risk Adjustment (−10 to 0 points)

```
blowout_threshold = avg_l10 × 0.50
blowout_games     = count of L10 games where value < blowout_threshold
```

| Blowout games | Points deducted | Notes                                              |
|---------------|----------------|----------------------------------------------------|
| 0 or 1        | 0              | No meaningful pattern                              |
| 2             | −3             | Mild concern — two outlier games                   |
| 3             | −6             | Significant pattern — investigate before betting   |
| 4+            | −10            | Systematic issue — foul trouble or blowout benching|

Rationale: a player who posts 3 points in three of their last ten games is a prop betting hazard even if their average is 22. The hit rate calculation does not penalise this heavily enough. This factor does.

### Rule Score

```
rule_score = factor_hr + factor_trend + factor_value + factor_consistency + factor_volume + factor_blowout
```

Plays with weighted hit rate < 0.65 are dropped regardless of rule score. They do not advance to Layer 2.

---

## Layer 2 — AI Reasoning (ai_layer.py)

Plays that pass Layer 1 are batched and sent to Claude. The AI reads the enriched numeric data — including the new consistency and blowout fields — and adds contextual intelligence that pure statistics cannot capture.

### System Prompt Rationale

The AI is instructed to behave as a 15-year veteran analyst, not a data summariser. The key behaviours enforced in the prompt:

- Be contrarian when warranted — do not rubber-stamp high hit rates
- Apply specific NBA domain knowledge (defender matchups, back-to-back fatigue, pace effects, home/away splits, revenge game patterns)
- Detect trap lines — books deliberately set lines at psychological anchor points (20.5, 25.5, 30.5) to attract recreational bettors regardless of edge
- Apply game-script reasoning — a 20-point favourite's star player may not play the fourth quarter

### Five Questions Claude Asks Per Play

1. **Is the line a TRAP?** — Does the line sit at a public-money anchor (e.g., 25.5) that looks approachable even though the player only averages 24.1?
2. **Is there a GAME SCRIPT concern?** — Heavy favourite, expected blowout, low game total, or team with nothing to play for?
3. **Is there a MATCHUP EDGE?** — Is the opponent weak at defending this stat? Or is there an elite lock-down defender likely assigned?
4. **Is the CONSISTENCY reliable?** — Is the player genuinely steady, or is the hit rate inflated by a 3-game hot streak that is likely to cool?
5. **Is there a FATIGUE or REST factor?** — Back-to-back game? Long road trip? Players on high minutes loads show measurable drops on the second night of a back-to-back.

### What Claude Returns Per Play

- `confidence_adjustment`: integer from −20 to +20 added to the rule score
- `flag`: green (strong), yellow (caution), red (avoid)
- `rationale`: one specific sentence, max 25 words
- `trap_detected`: boolean — true if the line is identified as a public-money trap
- `key_risk`: the single biggest risk to the play in 5 words or less

### Final Score

```
final_score = rule_score + confidence_adjustment
```

Plays are ranked by final_score descending. Red-flagged plays are excluded from parlay building.

---

## Parlay Builder (parlay_builder.py)

After individual plays are scored and ranked:

1. Top plays are selected (configurable, default top 10 by final_score)
2. 2–4 leg combinations are generated
3. Anti-correlated legs are filtered out (structural contradictions)
4. SGP combinations (same game) are flagged separately
5. **SGP correlation bonus applied**: when all legs come from the same high-total game (avg_final_score > 70 per team), the estimated combined hit rate receives a +5% additive bonus to reflect positive correlation — fast pace benefits all counting stats simultaneously
6. Only parlays above the target combined hit rate are surfaced (default 40%)
7. Top 20 parlays are returned, sorted by SGP preference, estimated combined hit rate, and average final score

### SGP Correlation Bonus Logic

In a standard multi-game parlay, each leg is independent and the combined hit rate is simply the product of individual hit rates. Same-game parlays break this independence assumption in two directions:

**Negative correlation (already filtered)**: a player going over assists while the game total goes under — contradiction.

**Positive correlation (now rewarded)**: in a high-scoring, high-pace game (combined total 220+), every possession-dependent stat benefits — points, rebounds, assists, and threes all see natural upward pressure. When two or more legs from the same high-total game are combined, the true combined probability is slightly higher than the mathematical product of individual hit rates. The 5% bonus is a conservative estimate of this structural edge.
