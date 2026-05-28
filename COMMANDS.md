# ParlayGod — Command Reference

> **If you only bet parlays:** ignore `--history` and `--log-result` entirely.
> Your flow is: run the program → `--parlays` to review → `--log-parlay [ID]` to record results.
> `--history` is only for tracking individual straight bets.

---

## Starting Up

Every time you open a new terminal, run this first:
```bash
cd /Users/khiansismundo/NbaOddsProgram
source venv/bin/activate
```

You'll see `(venv)` appear at the start of your terminal line. You're ready.

---

## One-Time Setup

Only needed the first time:
```bash
bash setup.sh
```

---

## Running the Program

### Full run (odds pulled automatically from DraftKings, FanDuel, BetMGM)
```bash
python parlay_god/main.py
```

### Props only — skip the parlay builder
```bash
python parlay_god/main.py --mode props
```

---

## Manual Mode — Enter Your Own Lines (e.g. from 747)

### Stats only — free, no AI cost
```bash
python parlay_god/main.py --manual
```

### Stats + Claude AI analysis — costs OpenRouter tokens
```bash
python parlay_god/main.py --manual --ai
```

When you run manual mode, it will ask you one play at a time:
```
Play 1
  Player name (or 'done'): Jalen Williams
  Stat [points/rebounds/assists/threes/steals/pra/ar]: points
  Direction [over/under]: under
  Line: 22.5
  ✓ Added: Jalen Williams u22.5 points

Play 2
  Player name (or 'done'): done
```
Type `done` when you've entered all your plays.

---

## Swapping the AI Model

Open `knowledge_base/config.yaml` and change the `model` line:

```yaml
ai:
  model: "anthropic/claude-sonnet-4-5"   # smarter, costs more
  # model: "anthropic/claude-haiku-4-5"  # fast and cheap
```

No code changes needed — just save the file and run normally.

---

## Viewing Saved History

### All primary plays
```bash
python parlay_god/main.py --history
```

### Primary + secondary "also worth a look" plays
```bash
python parlay_god/main.py --history --secondary
```

### Filter by player name (partial name works)
```bash
python parlay_god/main.py --history --player "Jalen"
python parlay_god/main.py --history --player "Jalen Williams"
```

### Filter by stat type
```bash
python parlay_god/main.py --history --stat points
python parlay_god/main.py --history --stat rebounds
python parlay_god/main.py --history --stat assists
python parlay_god/main.py --history --stat threes
python parlay_god/main.py --history --stat steals
python parlay_god/main.py --history --stat pra
python parlay_god/main.py --history --stat ar
```

### Filter by direction
```bash
python parlay_god/main.py --history --direction over
python parlay_god/main.py --history --direction under
```

### Filter by outcome
```bash
python parlay_god/main.py --history --outcome win
python parlay_god/main.py --history --outcome loss
python parlay_god/main.py --history --outcome push
python parlay_god/main.py --history --outcome void
python parlay_god/main.py --history --outcome pending   # not yet recorded
```

### Filter by date
```bash
python parlay_god/main.py --history --date 2026-05-28
```

### Combine filters
```bash
# All winning unders
python parlay_god/main.py --history --direction under --outcome win

# A specific player's pending plays
python parlay_god/main.py --history --player "Jalen" --outcome pending

# Points plays from a specific date including secondary
python parlay_god/main.py --history --stat points --date 2026-05-28 --secondary

# Every win across all stat types and both tiers
python parlay_god/main.py --history --outcome win --secondary
```

---

## Viewing Saved Parlays

### All saved parlays
```bash
python parlay_god/main.py --parlays
```

### Filter by type
```bash
python parlay_god/main.py --parlays --parlay-type SGP
python parlay_god/main.py --parlays --parlay-type multi
```

### Filter by number of legs
```bash
python parlay_god/main.py --parlays --legs 2
python parlay_god/main.py --parlays --legs 3
```

### Filter by outcome or date
```bash
python parlay_god/main.py --parlays --outcome win
python parlay_god/main.py --parlays --outcome pending
python parlay_god/main.py --parlays --date 2026-05-28
```

### Combine filters
```bash
python parlay_god/main.py --parlays --parlay-type SGP --outcome win
python parlay_god/main.py --parlays --legs 2 --outcome pending --date 2026-05-28
```

---

## Recording Results

### Individual plays — find the ID from `--history`
```bash
python parlay_god/main.py --log-result 5 --outcome win
python parlay_god/main.py --log-result 5 --outcome loss
python parlay_god/main.py --log-result 5 --outcome push
python parlay_god/main.py --log-result 5 --outcome void
```

### Parlays — find the ID from `--parlays`
```bash
python parlay_god/main.py --log-parlay 3 --outcome win
python parlay_god/main.py --log-parlay 3 --outcome loss
python parlay_god/main.py --log-parlay 3 --outcome push
python parlay_god/main.py --log-parlay 3 --outcome void
```

---

## Tuning the Algorithm

All thresholds live in `knowledge_base/config.yaml`. Open it and adjust:

| Setting | What it controls |
|---|---|
| `min_hit_rate` | Minimum hit rate to qualify as a primary play (default 0.65 = 65%) |
| `secondary.min_hit_rate` | Minimum for secondary "also look at" plays (default 0.55) |
| `max_parlay_legs` | Maximum legs in a parlay (default 6) |
| `target_combined_hit_rate` | Minimum estimated hit rate for a parlay to be shown (default 0.35) |
| `min_games_required` | Minimum playoff games needed to score a player (default 3) |
| `api_delay_seconds` | Pause between NBA API calls — raise if you get rate limited |

---

## Quick Reference

| What you want | Command |
|---|---|
| Run full analysis | `python parlay_god/main.py` |
| Props only | `python parlay_god/main.py --mode props` |
| Manual plays, free | `python parlay_god/main.py --manual` |
| Manual plays + AI | `python parlay_god/main.py --manual --ai` |
| View all history | `python parlay_god/main.py --history` |
| View + secondary | `python parlay_god/main.py --history --secondary` |
| Filter by player | `python parlay_god/main.py --history --player "Name"` |
| Filter by stat | `python parlay_god/main.py --history --stat points` |
| Filter by direction | `python parlay_god/main.py --history --direction under` |
| Filter by outcome | `python parlay_god/main.py --history --outcome win` |
| Filter by date | `python parlay_god/main.py --history --date 2026-05-28` |
| View parlay history | `python parlay_god/main.py --parlays` |
| Filter parlays by type | `python parlay_god/main.py --parlays --parlay-type SGP` |
| Filter parlays by legs | `python parlay_god/main.py --parlays --legs 2` |
| Record a play result | `python parlay_god/main.py --log-result 5 --outcome win` |
| Record a parlay result | `python parlay_god/main.py --log-parlay 3 --outcome win` |
