#!/usr/bin/env python3
"""
ParlayGod — NBA Player Props & Parlay Analyser
Usage:  python parlay_god/main.py
        python parlay_god/main.py --history
        python parlay_god/main.py --log-result 42 --outcome win
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import click
import yaml
from dotenv import load_dotenv
from rich.progress import Progress, SpinnerColumn, TextColumn

from parlay_god.db.database import init_db
from parlay_god.db.tracker import (log_recommendations, log_parlays, get_history,
                                    get_parlay_history, log_parlay_outcome, place_parlay, log_outcome)
from parlay_god.data.odds_client import OddsClient
from parlay_god.data.nba_client import NBAClient
from parlay_god.data.bdk_client import BallDontLieClient
from parlay_god.models.player_stats import compute_splits
from parlay_god.models.scoring import score_play
from parlay_god.models.ai_layer import evaluate_plays
from parlay_god.models.parlay_builder import build_parlays
from parlay_god.cli.report import print_report, print_history, print_parlay_history, console

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base", "config.yaml"
)


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    load_dotenv(env_path)

    missing = [k for k in ("ODDS_API_KEY", "ANTHROPIC_API_KEY") if not os.getenv(k)]
    if missing:
        console.print(
            f"\n[red]Missing API keys:[/red] {', '.join(missing)}\n"
            "Open the [bold].env[/bold] file and add them. See [bold].env.template[/bold].\n"
        )
        sys.exit(1)


def get_stats_client(player_name, stat_type, line, nba_client, bdk_client):
    result = nba_client.get_player_stats_for_play(player_name, stat_type, line)
    if result:
        return result
    if bdk_client:
        return bdk_client.get_player_stats_for_play(player_name, stat_type, line)
    return None


def _enrich_props(props, stat_filter, min_games, weights, thresholds,
                  primary_threshold, secondary_threshold, nba_client, bdk_client):
    """
    Returns (primary_plays, secondary_plays).
    primary: passes main hit-rate and rule-score thresholds.
    secondary: passes lower thresholds — the "also look at" tier.
    """
    primary = []
    secondary = []

    for prop in props:
        if prop["stat_type"] not in stat_filter:
            continue

        direction = prop.get("direction", "over")

        raw_stats = get_stats_client(
            prop["player"], prop["stat_type"], prop["line"],
            nba_client, bdk_client
        )
        if not raw_stats:
            continue

        l10 = raw_stats.get("games_l10", [])
        l5 = raw_stats.get("games_l5", [])

        if len(l5) < min_games:
            continue

        splits = compute_splits(l10, l5, prop["line"], direction=direction)
        if not splits:
            continue

        scored = score_play(splits, weights, thresholds, direction=direction)

        base = {**prop, "splits": splits, **scored, "data_source": raw_stats.get("source")}

        if scored["passes_threshold"]:
            primary.append(base)
        elif (
            scored["weighted_hr"] >= secondary_threshold.get("min_hit_rate", 0.55)
            and scored["rule_score"] >= secondary_threshold.get("min_rule_score", 35)
        ):
            secondary.append(base)

    return primary, secondary


VALID_STATS = ["points", "rebounds", "assists", "threes", "steals", "pra", "ar"]


def _collect_manual_plays() -> list[dict]:
    """Interactive prompt to collect plays from the user."""
    console.print()
    console.print("[bold bright_blue]MANUAL MODE[/bold bright_blue] — Enter your plays from 747 or any book.")
    console.print("[dim]Type 'done' at the player name prompt when finished.[/dim]")
    console.print()

    plays = []
    i = 1

    while True:
        console.print(f"[bold]Play {i}[/bold]")

        player = console.input("  Player name (or 'done'): ").strip()
        if player.lower() == "done" or not player:
            break

        # Stat type
        while True:
            stat = console.input(f"  Stat [{'/'.join(VALID_STATS)}]: ").strip().lower()
            if stat in VALID_STATS:
                break
            console.print(f"  [red]Invalid stat. Choose from: {', '.join(VALID_STATS)}[/red]")

        # Direction
        while True:
            direction = console.input("  Direction [over/under]: ").strip().lower()
            if direction in ("over", "under", "o", "u"):
                direction = "over" if direction in ("over", "o") else "under"
                break
            console.print("  [red]Type 'over' or 'under'.[/red]")

        # Line
        while True:
            try:
                line = float(console.input("  Line: ").strip())
                break
            except ValueError:
                console.print("  [red]Enter a number (e.g. 22.5)[/red]")

        prefix = "o" if direction == "over" else "u"
        console.print(f"  [green]✓ Added:[/green] {player} {prefix}{line} {stat}")
        console.print()

        plays.append({
            "player": player,
            "stat_type": stat,
            "direction": direction,
            "line": line,
            "over_odds": None,
            "book": "manual",
            "home_team": "—",
            "away_team": "—",
            "market_key": stat,
            "is_alternate": False,
        })
        i += 1

    return plays


def _run_manual(plays, cfg, nba_client, bdk_client, use_ai, anthropic_key):
    """Score manually entered plays and print results."""
    weights = cfg.get("weights", {})
    thresholds = cfg.get("thresholds", {})
    ai_cfg = cfg.get("ai", {})
    min_games = cfg.get("stats", {}).get("min_games_required", 3)

    scored_plays = []

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as progress:
        task = progress.add_task("Fetching NBA stats...", total=None)

        for prop in plays:
            raw_stats = get_stats_client(prop["player"], prop["stat_type"], prop["line"], nba_client, bdk_client)

            if not raw_stats:
                console.print(f"[yellow]Could not find stats for {prop['player']} — skipping.[/yellow]")
                continue

            l10 = raw_stats.get("games_l10", [])
            l5 = raw_stats.get("games_l5", [])

            if len(l5) < min_games:
                console.print(f"[yellow]{prop['player']} has fewer than {min_games} games — skipping.[/yellow]")
                continue

            direction = prop.get("direction", "over")
            splits = compute_splits(l10, l5, prop["line"], direction=direction)
            if not splits:
                continue

            scored = score_play(splits, weights, thresholds, direction=direction)

            scored_plays.append({
                **prop,
                "splits": splits,
                **scored,
                "ai_flag": "yellow",
                "ai_adjustment": 0,
                "ai_rationale": "Stats only — run with --ai for analysis.",
                "trap_detected": False,
                "key_risk": "—",
                "final_score": scored["rule_score"],
                "data_source": raw_stats.get("source"),
            })

        if use_ai and scored_plays:
            progress.update(task, description="Running AI analysis...")
            try:
                scored_plays = evaluate_plays(
                    scored_plays,
                    api_key=anthropic_key,
                    model=model or ai_cfg.get("model", "anthropic/claude-haiku-4-5"),
                    batch_size=ai_cfg.get("max_plays_per_call", 15),
                    game7_context=game7_context,
                )
            except Exception as e:
                console.print(f"[yellow]AI layer skipped ({e}).[/yellow]")

    final = sorted(scored_plays, key=lambda p: p.get("final_score", 0), reverse=True)
    parlays = build_parlays(final) if len(final) >= 2 else []
    rec_ids = log_recommendations(final)
    if parlays:
        log_parlays(parlays, rec_ids)
    print_report(final, parlays)


@click.command()
@click.option("--history", is_flag=True, help="Show past recommendations")
@click.option("--log-result", type=str, metavar="ID[,ID...]", help="Log the outcome of one or more recommendation IDs (comma-separated)")
@click.option("--mode", default="all", type=click.Choice(["all", "props"]), help="Analysis mode")
@click.option("--manual", is_flag=True, help="Enter plays manually from any book (free — no Odds API used)")
@click.option("--ai", "use_ai", is_flag=True, help="Run AI analysis on manual plays (costs OpenRouter tokens)")
@click.option("--secondary", is_flag=True, help="Include secondary 'also worth a look' plays in history")
@click.option("--parlays", "show_parlays", is_flag=True, help="Show saved parlay history instead of individual plays")
@click.option("--parlay-type", default=None, type=click.Choice(["SGP","multi"]), help="Filter parlays by type")
@click.option("--legs", default=None, type=int, help="Filter parlays by number of legs")
@click.option("--log-parlay", type=str, metavar="ID[,ID...]", help="Log the outcome of one or more saved parlays (comma-separated)")
@click.option("--place-parlay", "place_parlay_id", type=int, metavar="ID", help="Mark a parlay as placed (bet before the game)")
@click.option("--player", default=None, help="Filter history by player name (partial match)")
@click.option("--stat", default=None, type=click.Choice(["points","rebounds","assists","threes","steals","pra","ar"]), help="Filter history by stat type")
@click.option("--direction", default=None, type=click.Choice(["over","under"]), help="Filter history by over or under")
@click.option("--outcome", default=None, type=click.Choice(["win","loss","push","void","pending"]), help="Filter history by outcome (pending = not yet recorded)")
@click.option("--date", "run_date", default=None, help="Filter history by date (YYYY-MM-DD)")
@click.option("--test-ai", "test_ai", is_flag=True, help="Send a test play through the AI layer to verify it's working")
@click.option("--model", default=None, help="Override the AI model for this run (e.g. deepseek/deepseek-chat)")
@click.option("--game7", "is_game7", is_flag=True, help="Load Game 7 series intelligence into the AI layer for deeper analysis")
def main(history, log_result, outcome, mode, manual, use_ai, secondary,
         player, stat, direction, run_date,
         show_parlays, parlay_type, legs, log_parlay, place_parlay_id, test_ai, model, is_game7):
    load_env()
    init_db()

    game7_context = None
    if is_game7:
        game7_path = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "game7_context.md")
        game7_path = os.path.normpath(game7_path)
        if os.path.exists(game7_path):
            with open(game7_path) as f:
                game7_context = f.read()
            console.print("[cyan]Game 7 mode active — series intelligence loaded into AI layer.[/cyan]")
        else:
            console.print("[yellow]--game7 flag set but knowledge_base/game7_context.md not found. Running without it.[/yellow]")

    if test_ai:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            console.print("[red]ANTHROPIC_API_KEY not found in .env[/red]")
            sys.exit(1)
        cfg = load_config()
        effective_model = model or cfg.get("ai", {}).get("model", "anthropic/claude-sonnet-4-5")
        console.print(f"[cyan]Testing AI layer...[/cyan]")
        console.print(f"[dim]Key type: {'OpenRouter' if api_key.startswith('sk-or-v1-') else 'Anthropic direct'}[/dim]")
        console.print(f"[dim]Model: {effective_model}[/dim]")
        dummy_play = [{
            "player": "LeBron James", "stat_type": "points", "line": 24.5,
            "book": "draftkings", "over_odds": -110, "rule_score": 62.0,
            "away_team": "LAL", "home_team": "GSW",
            "splits": {
                "hit_rate_l5": 0.80, "hits_l5": 4, "hit_rate_l10": 0.70, "hits_l10": 7,
                "avg_l5": 27.2, "avg_l10": 26.1, "last_3_avg": 28.0,
                "min_l10": 18, "max_l10": 38, "trend": 0.04, "line_value": 0.07,
                "std_dev": 5.2, "coefficient_of_variation": 0.20, "blowout_games": 1,
                "games_available": 10, "small_sample": False,
            }
        }]
        result = evaluate_plays(dummy_play, api_key=api_key, model=effective_model)
        play = result[0]
        if play.get("ai_rationale") == "Insufficient AI data.":
            console.print("[red]AI layer FAILED — check the error above for the reason.[/red]")
        else:
            console.print(f"\n[green]AI layer is working.[/green]")
            console.print(f"  Flag:       {play.get('ai_flag')}")
            console.print(f"  Adjustment: {play.get('ai_adjustment'):+d}")
            console.print(f"  Rationale:  {play.get('ai_rationale')}")
            console.print(f"  Key risk:   {play.get('key_risk')}")
            console.print(f"  Trap:       {play.get('trap_detected')}")
        return

    if history:
        rows = get_history(
            limit=100,
            include_secondary=secondary,
            player=player,
            stat=stat,
            direction=direction,
            outcome=outcome,
            run_date=run_date,
        )
        print_history(rows, include_secondary=secondary)
        return

    if log_result:
        if not outcome:
            console.print("[red]Provide --outcome (win, loss, push, void) with --log-result.[/red]")
            sys.exit(1)
        ids = [s.strip() for s in log_result.split(",")]
        for raw_id in ids:
            try:
                log_outcome(int(raw_id), outcome)
                console.print(f"[green]Outcome recorded:[/green] Play #{raw_id} → {outcome}")
            except Exception as e:
                console.print(f"[red]Error on #{raw_id}:[/red] {e}")
        return

    if place_parlay_id:
        try:
            place_parlay(place_parlay_id)
            console.print(f"[cyan]Parlay #{place_parlay_id} marked as PLACED ⏳[/cyan]")
            console.print("[dim]After the game, run: python parlay_god/main.py --log-parlay "
                          f"{place_parlay_id} --outcome win/loss[/dim]")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
        return

    if log_parlay:
        if not outcome:
            console.print("[red]Provide --outcome (win, loss, push, void) with --log-parlay.[/red]")
            sys.exit(1)
        ids = [s.strip() for s in log_parlay.split(",")]
        for raw_id in ids:
            try:
                log_parlay_outcome(int(raw_id), outcome)
                console.print(f"[green]Outcome recorded:[/green] Parlay #{raw_id} → {outcome}")
            except Exception as e:
                console.print(f"[red]Error on #{raw_id}:[/red] {e}")
        return

    if show_parlays:
        rows = get_parlay_history(
            limit=100,
            parlay_type=parlay_type,
            outcome=outcome,
            run_date=run_date,
            n_legs=legs,
        )
        print_parlay_history(rows)
        return

    cfg = load_config()

    if manual:
        nba_client = NBAClient(
            delay=cfg.get("nba", {}).get("api_delay_seconds", 0.6),
            season=cfg.get("nba", {}).get("season", "2025-26"),
        )
        bdk_key = os.getenv("BALLDONTLIE_API_KEY")
        bdk_client = BallDontLieClient(api_key=bdk_key) if bdk_key else None
        plays = _collect_manual_plays()
        if not plays:
            console.print("[yellow]No plays entered.[/yellow]")
            return
        _run_manual(plays, cfg, nba_client, bdk_client, use_ai, os.getenv("ANTHROPIC_API_KEY"))
        return

    stats_cfg = cfg.get("stats", {})
    weights = cfg.get("weights", {})
    thresholds = cfg.get("thresholds", {})
    secondary_threshold = cfg.get("secondary", {"min_hit_rate": 0.55, "min_rule_score": 35})
    nba_cfg = cfg.get("nba", {})
    ai_cfg = cfg.get("ai", {})
    parlay_cfg = cfg.get("parlay", {})
    stat_filter = cfg.get("stat_types", ["points", "rebounds", "assists", "threes"])

    odds_client = OddsClient(
        api_key=os.getenv("ODDS_API_KEY"),
        preferred_books=cfg.get("bookmakers", ["draftkings", "fanduel"]),
    )
    nba_client = NBAClient(
        delay=nba_cfg.get("api_delay_seconds", 1.5),
        season=nba_cfg.get("season", "2025-26"),
    )
    bdk_key = os.getenv("BALLDONTLIE_API_KEY")
    bdk_client = BallDontLieClient(api_key=bdk_key) if bdk_key else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:

        task = progress.add_task("Fetching today's prop lines...", total=None)
        try:
            raw_props = odds_client.get_todays_props()
        except RuntimeError as e:
            console.print(f"\n[red]Odds API error:[/red] {e}\n")
            sys.exit(1)

        if not raw_props:
            console.print(
                "\n[yellow]No NBA prop lines found for today. "
                "No games scheduled or Odds API returned nothing.[/yellow]\n"
            )
            sys.exit(0)

        progress.update(task, description=f"Scoring {len(raw_props)} props...")

        primary_plays, secondary_plays = _enrich_props(
            raw_props, stat_filter,
            stats_cfg.get("min_games_required", 5),
            weights, thresholds, thresholds, secondary_threshold,
            nba_client, bdk_client,
        )

        if not primary_plays and not secondary_plays:
            console.print(
                "\n[yellow]No plays cleared the threshold today.[/yellow]\n"
                f"[dim]Primary threshold: {thresholds.get('min_hit_rate', 0.65):.0%} hit rate.[/dim]\n"
            )
            sys.exit(0)

        # AI layer runs on primary plays only (save API credits)
        if primary_plays:
            progress.update(task, description=f"Running AI on {len(primary_plays)} plays...")
            try:
                primary_plays = evaluate_plays(
                    primary_plays,
                    api_key=os.getenv("ANTHROPIC_API_KEY"),
                    model=model or ai_cfg.get("model", "claude-haiku-4-5-20251001"),
                    batch_size=ai_cfg.get("max_plays_per_call", 15),
                    game7_context=game7_context,
                )
            except Exception as e:
                console.print(f"\n[yellow]AI layer skipped ({e}). Showing rule scores.[/yellow]\n")
                for p in primary_plays:
                    p.setdefault("ai_adjustment", 0)
                    p.setdefault("ai_flag", "yellow")
                    p.setdefault("ai_rationale", "AI unavailable.")
                    p.setdefault("trap_detected", False)
                    p.setdefault("key_risk", "—")
                    p["final_score"] = p.get("rule_score", 0)

        # Deduplicate — same player/stat/line/direction may appear from multiple books
        seen_plays = set()
        deduped_primary = []
        for p in primary_plays:
            if p.get("ai_flag") == "red":
                continue
            key = (p["player"], p["stat_type"], p["line"], p.get("direction", "over"))
            if key not in seen_plays:
                seen_plays.add(key)
                deduped_primary.append(p)

        final_plays = sorted(deduped_primary, key=lambda p: p.get("final_score", 0), reverse=True)

        # Secondary plays: deduplicate and sort by rule_score
        seen_secondary = set()
        deduped_secondary = []
        for p in secondary_plays:
            key = (p["player"], p["stat_type"], p["line"], p.get("direction", "over"))
            if key not in seen_secondary:
                seen_secondary.add(key)
                deduped_secondary.append(p)

        secondary_sorted = sorted(deduped_secondary, key=lambda p: p.get("rule_score", 0), reverse=True)

        parlays = []
        if mode != "props" and final_plays:
            progress.update(task, description="Building parlay combinations...")
            parlays = build_parlays(
                final_plays,
                min_legs=thresholds.get("min_parlay_legs", 2),
                max_legs=thresholds.get("max_parlay_legs", 6),
                target_combined_hr=parlay_cfg.get("target_combined_hit_rate", 0.35),
                prefer_same_game=parlay_cfg.get("prefer_same_game", True),
            )

        progress.update(task, description="Saving to history...")
        rec_ids = log_recommendations(final_plays)
        log_recommendations(secondary_sorted, is_secondary=True)
        if parlays:
            log_parlays(parlays, rec_ids)

    print_report(final_plays, parlays, secondary_plays=secondary_sorted)


if __name__ == "__main__":
    main()
