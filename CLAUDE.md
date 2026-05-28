# NbaOddsProgram — ParlayGod

A locally-run NBA player prop and parlay analysis system that ingests player stats, applies a hybrid rule-based + AI scoring model, and surfaces daily CLI recommendations for same-game parlays (SGP), player props, and alternate lines.

---

## Project Structure

```
NbaOddsProgram/
├── knowledge_base/        # System brain — rules, guardrails, configs, algorithm definitions
│   ├── config.yaml        # API keys, thresholds, book preferences, stat windows
│   ├── guardrails.md      # What the system WILL and WON'T recommend (edge floors, limits)
│   ├── algorithm.md       # How the scoring model works, what each layer does
│   └── bet_types.md       # Definitions: props, SGP legs, alt lines, how each is evaluated
│
└── parlay_god/            # The codebase
    ├── main.py            # Entry point — `python main.py` runs the full pipeline
    ├── data/
    │   ├── nba_client.py  # NBA Stats API client (primary)
    │   ├── bdk_client.py  # BallDontLie API fallback (auto-switches on rate limit)
    │   └── odds_client.py # The Odds API client (aggregator — DK, FD, BetMGM, etc.)
    ├── models/
    │   ├── player_stats.py  # Stat ingestion: last 5, last 10, season, matchup splits
    │   ├── scoring.py       # Rule-based hit-rate engine (threshold layer)
    │   ├── ai_layer.py      # Claude API — contextual reasoning on top of scored plays
    │   └── parlay_builder.py # Combines legs into SGP or multi-game parlays
    ├── db/
    │   ├── database.py    # SQLite setup and queries
    │   └── tracker.py     # Log recommendations, record outcomes, calculate P&L
    └── cli/
        └── report.py      # Formats and prints the final CLI output
```

---

## What the System Does

1. **Fetch upcoming games** for the current date (or a specified date).
2. **Pull player stats** for all players with lines available:
   - Last 5 and last 10 game averages and hit rates vs. the posted line
   - Season averages and trends
   - Matchup data: how the player performs against the specific opposing defender/team
3. **Score each play** through two layers:
   - **Rule layer**: hit rate ≥ threshold (configurable per stat type), trend direction, home/away splits
   - **AI layer**: Claude API call that reads the scored data and reasons about context (fatigue, minutes restrictions, matchup quality, narrative factors) — outputs a confidence adjustment and brief rationale
4. **Build parlay combinations** from the top-ranked individual legs (SGP and multi-game).
5. **Surface recommendations** as a ranked CLI report with odds, hit rates, AI rationale, and a confidence score.
6. **Log every recommendation** to SQLite so results can be tracked over time.

---

## Tech Stack

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Stats source (primary) | NBA Stats API (`nba_api` library) |
| Stats source (fallback) | BallDontLie API (auto-failover on rate limit) |
| Odds source | The Odds API (aggregator) |
| AI layer | Claude API (claude-sonnet-4-6 or claude-haiku-4-5 for speed) |
| Storage | SQLite (local, zero setup) |
| Output | CLI — terminal report |
| Scheduling | On-demand only (`python main.py`) |

---

## Running the System

```bash
# Full daily analysis for today's games
python parlay_god/main.py

# Specific date
python parlay_god/main.py --date 2026-05-30

# Props only (no SGP building)
python parlay_god/main.py --mode props

# View past recommendation history
python parlay_god/main.py --history

# Log the result of a past recommendation
python parlay_god/main.py --log-result <recommendation_id> --outcome win
```

---

## Algorithm Overview

### Layer 1 — Rule Engine (scoring.py)
- **Hit rate score**: % of last 10 games player exceeded the posted line (weighted: L5 counts 60%, L10 counts 40%)
- **Trend score**: direction of performance over the last 5 games (improving = bonus, declining = penalty)
- **Matchup score**: player's historical stat output against the specific opponent's defensive rank at position
- **Line value score**: compare posted line to player's L10 average — lines set too low relative to performance get a boost
- Minimum edge floor: only plays with hit rate ≥ 65% advance to the AI layer (configurable in `knowledge_base/config.yaml`)

### Layer 2 — AI Reasoning (ai_layer.py)
- Sends scored play data to Claude API with structured context
- Claude evaluates: injury/minutes news, narrative context, correlated legs (for SGP), line shopping across books
- Returns: confidence adjustment (−20 to +20), one-sentence rationale, green/yellow/red flag
- Final confidence score = rule score + AI adjustment

### Parlay Builder (parlay_builder.py)
- Combines top-ranked plays into 2–4 leg parlays
- SGP logic: checks for correlated legs (e.g. player on high-scoring team also goes over assists)
- Filters out anti-correlated legs (e.g. player goes over points AND team loses)

---

## Guardrails (knowledge_base/guardrails.md)

The system will NOT recommend:
- Any play with fewer than 5 games of recent data
- Players listed as questionable/out (injury check required before run)
- Lines where the book has no competition (single-book pricing = no edge)
- Parlays with more than 4 legs (variance too high for consistent edge)

The system WILL flag:
- Any play Claude rates as a red flag, even if the rule score is high
- SGP legs that are anti-correlated

---

## API Keys (store in `.env`, never in code)

```
NBA_API_KEY=          # Not required for nba_api but set base delay
ODDS_API_KEY=         # The Odds API key
ANTHROPIC_API_KEY=    # Claude API key
BALLDONTLIE_API_KEY=  # BallDontLie API key (free tier)
```

---

## Development Notes

- The user is not a developer — all CLI commands must work with zero Python knowledge beyond `python main.py`
- Error messages must be plain English, not stack traces
- Auto-failover from NBA Stats API to BallDontLie is silent (logged, not surfaced to user)
- SQLite database is created automatically on first run — no setup required
- All thresholds and weights are editable in `knowledge_base/config.yaml` without touching code
