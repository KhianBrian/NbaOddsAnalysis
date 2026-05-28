# ParlayGod — Bet Type Definitions

## Player Props

A wager on whether an individual player exceeds or falls short of a stat line.

| Stat | Market Key (Odds API) | Notes |
|---|---|---|
| Points | player_points | Most liquid market |
| Rebounds | player_rebounds | Total (offensive + defensive) |
| Assists | player_assists | Does not include turnovers |
| 3-Pointers Made | player_threes | Made, not attempted |

System evaluates: **over** only (finding under value requires a separate negative model).

## Alternate Lines

The same stat as a standard prop but at a non-standard line. Books offer these at different odds.

- Example: standard line is 25.5 points at −115. Alternate lines might be 22.5 at −190 or 28.5 at +140.
- System pulls alternate markets (player_points_alternate etc.) and compares them against the player's distribution to find mispriced alternates.

## Same-Game Parlays (SGP)

Multiple legs from the same game combined into one bet.

**Correlated legs (good)**: Two players on the same team both going over assists — if the game pace is high, both benefit.

**Anti-correlated legs (bad)**: Player A goes over points AND the total goes under — high individual scoring in a low-scoring game is contradictory.

The parlay builder flags anti-correlated legs and will not combine them.

## Multi-Game Parlays

Standard parlay combining legs from different games. Independence assumption holds (legs are uncorrelated across games). Max 4 legs enforced as a guardrail.
