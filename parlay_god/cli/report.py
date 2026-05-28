from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from datetime import date

console = Console()

FLAG_COLORS = {"green": "bright_green", "yellow": "yellow", "red": "red"}
FLAG_ICONS = {"green": "●", "yellow": "◐", "red": "○"}
DIR_LABELS = {"over": ("▲", "cyan"), "under": ("▼", "magenta")}


def _odds_str(odds: int | None) -> str:
    if odds is None:
        return "N/A"
    return f"+{odds}" if odds > 0 else str(odds)


def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.0%}"


def _dir_cell(direction: str) -> Text:
    icon, color = DIR_LABELS.get(direction, ("▲", "cyan"))
    return Text(f"{icon} {'O' if direction == 'over' else 'U'}", style=color)


def print_report(plays: list[dict], parlays: list[dict], secondary_plays: list[dict] | None = None):
    today = date.today().strftime("%B %d, %Y")

    console.print()
    console.print(
        Panel(
            f"[bold white]PARLAYGOD[/bold white]  [dim]NBA Player Props & Parlays[/dim]\n[dim]{today}[/dim]",
            border_style="bright_blue",
            expand=False,
        )
    )
    console.print()

    if not plays and not secondary_plays:
        console.print("[yellow]No plays found today.[/yellow]")
        return

    # ------------------------------------------------------------------ #
    # PRIMARY PLAYS
    # ------------------------------------------------------------------ #
    if plays:
        console.print("[bold]TOP PLAYS[/bold]", style="bright_blue")
        console.print()

        table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim", expand=False)
        table.add_column("", width=2)
        table.add_column("Dir", width=4)
        table.add_column("Player", min_width=18)
        table.add_column("Stat", width=10)
        table.add_column("Line", width=6, justify="right")
        table.add_column("Odds", width=6, justify="right")
        table.add_column("L5", width=5, justify="center")
        table.add_column("L10", width=5, justify="center")
        table.add_column("Avg", width=5, justify="right")
        table.add_column("Score", width=6, justify="right")
        table.add_column("Trap", width=5, justify="center")
        table.add_column("Book", width=10)
        table.add_column("Analysis", min_width=34)

        for play in plays:
            flag = play.get("ai_flag", "yellow")
            color = FLAG_COLORS.get(flag, "white")
            icon = FLAG_ICONS.get(flag, "◐")
            direction = play.get("direction", "over")
            s = play.get("splits", {})
            trap = play.get("trap_detected", False)

            analysis = Text()
            analysis.append(play.get("ai_rationale", ""), style="dim")
            key_risk = play.get("key_risk", "")
            if key_risk and key_risk != "—":
                analysis.append(f"\n⚠ {key_risk}", style="dim red" if trap else "dim yellow")

            table.add_row(
                Text(icon, style=color),
                _dir_cell(direction),
                play.get("player", "—"),
                play.get("stat_type", "—").upper(),
                str(play.get("line", "—")),
                _odds_str(play.get("over_odds")),
                _pct(s.get("hit_rate_l5")),
                _pct(s.get("hit_rate_l10")),
                f"{s.get('avg_l10', 0):.1f}",
                f"{play.get('final_score', 0):.1f}",
                Text("TRAP", style="bold red") if trap else Text("—", style="dim"),
                play.get("book", "—").upper()[:10],
                analysis,
            )

        console.print(table)
        console.print("[dim]● green  ◐ yellow  ○ red  |  ▲ Over  ▼ Under[/dim]")
        console.print()

    # ------------------------------------------------------------------ #
    # PARLAYS
    # ------------------------------------------------------------------ #
    if parlays:
        console.print("[bold]TOP PARLAY COMBINATIONS[/bold]", style="bright_blue")
        console.print()

        sgp = [p for p in parlays if p["parlay_type"] == "SGP"]
        multi = [p for p in parlays if p["parlay_type"] == "multi"]

        def _print_parlays(group: list[dict], label: str):
            if not group:
                return
            console.print(f"  [bold]{label}[/bold]")
            for i, parlay in enumerate(group[:8], 1):
                bonus_tag = " [dim cyan][SGP CORR +5%][/dim cyan]" if parlay.get("sgp_high_total_bonus") else ""
                console.print(
                    f"  [dim]{i}.[/dim] {parlay['summary']}"
                    f"  [dim]est. HR: {parlay.get('est_combined_hr', 0):.0%}  "
                    f"legs: {parlay['n_legs']}  avg score: {parlay.get('avg_final_score', 0):.1f}[/dim]{bonus_tag}"
                )
            console.print()

        _print_parlays(sgp, "Same-Game Parlays (SGP)")
        _print_parlays(multi, "Multi-Game Parlays")

    # ------------------------------------------------------------------ #
    # SECONDARY — "ALSO WORTH A LOOK"
    # ------------------------------------------------------------------ #
    if secondary_plays:
        console.print("[bold]ALSO WORTH A LOOK[/bold]  [dim](below primary threshold — use your judgment)[/dim]", style="yellow")
        console.print()

        sec_table = Table(box=box.SIMPLE_HEAD, header_style="bold dim", expand=False)
        sec_table.add_column("Dir", width=4)
        sec_table.add_column("Player", min_width=18)
        sec_table.add_column("Stat", width=10)
        sec_table.add_column("Line", width=6, justify="right")
        sec_table.add_column("Odds", width=6, justify="right")
        sec_table.add_column("L5", width=5, justify="center")
        sec_table.add_column("L10", width=5, justify="center")
        sec_table.add_column("Avg", width=5, justify="right")
        sec_table.add_column("Rule Score", width=10, justify="right")

        for play in secondary_plays[:15]:
            direction = play.get("direction", "over")
            s = play.get("splits", {})

            sec_table.add_row(
                _dir_cell(direction),
                play.get("player", "—"),
                play.get("stat_type", "—").upper(),
                str(play.get("line", "—")),
                _odds_str(play.get("over_odds")),
                _pct(s.get("hit_rate_l5")),
                _pct(s.get("hit_rate_l10")),
                f"{s.get('avg_l10', 0):.1f}",
                f"{play.get('rule_score', 0):.1f}",
            )

        console.print(sec_table)
        console.print("[dim]These did not clear the 65% hit rate threshold. Check injury reports and game context before considering.[/dim]")
        console.print()

    console.print("[dim]Always verify injury reports before placing. Good luck.[/dim]")
    console.print()


def print_parlay_history(rows: list[dict]):
    if not rows:
        console.print("[yellow]No parlay history found.[/yellow]")
        return

    console.print()
    console.print("[bold]PARLAY HISTORY[/bold]", style="bright_blue")
    console.print()

    table = Table(box=box.SIMPLE_HEAD, header_style="bold dim", expand=False)
    table.add_column("ID", width=4)
    table.add_column("Date", width=12)
    table.add_column("Type", width=6)
    table.add_column("Legs", width=5, justify="center")
    table.add_column("Est. HR", width=8, justify="right")
    table.add_column("Status", width=10)
    table.add_column("Combination", min_width=40)

    for row in rows:
        outcome = row.get("outcome")
        placed = row.get("placed", 0)
        ptype = row.get("parlay_type", "—")
        type_color = "cyan" if ptype == "SGP" else "white"
        hr = row.get("est_combined_hr")
        hr_str = f"{hr:.0%}" if hr is not None else "—"

        if outcome == "win":
            status = Text("WIN", style="bold green")
        elif outcome == "loss":
            status = Text("LOSS", style="bold red")
        elif outcome == "push":
            status = Text("PUSH", style="bold yellow")
        elif outcome == "void":
            status = Text("VOID", style="dim")
        elif placed:
            status = Text("PLACED ⏳", style="bold cyan")
        else:
            status = Text("not placed", style="dim")

        table.add_row(
            str(row["id"]),
            row.get("run_date", "—"),
            Text(ptype, style=type_color),
            str(row.get("n_legs", "—")),
            hr_str,
            status,
            Text(row.get("leg_summary", "—"), style="dim"),
        )

    console.print(table)
    console.print()


def print_history(rows: list[dict], include_secondary: bool = False):
    if not rows:
        console.print("[yellow]No recommendation history found.[/yellow]")
        return

    console.print()
    label = "RECOMMENDATION HISTORY"
    if include_secondary:
        label += "  [dim](including secondary plays)[/dim]"
    console.print(f"[bold]{label}[/bold]", style="bright_blue")
    console.print()

    table = Table(box=box.SIMPLE_HEAD, header_style="bold dim")
    table.add_column("ID", width=4)
    table.add_column("Date", width=12)
    table.add_column("Dir", width=4)
    table.add_column("Player", min_width=16)
    table.add_column("Stat", width=8)
    table.add_column("Line", width=6, justify="right")
    table.add_column("Score", width=6, justify="right")
    table.add_column("Flag", width=5)
    table.add_column("Tier", width=5)
    table.add_column("Outcome", width=8)

    for row in rows:
        outcome = row.get("outcome") or "—"
        outcome_color = {"win": "green", "loss": "red", "push": "yellow", "void": "dim"}.get(outcome, "white")
        flag = row.get("ai_flag", "yellow")
        is_sec = row.get("is_secondary", 0)
        tier = Text("2nd", style="dim yellow") if is_sec else Text("1st", style="dim cyan")

        table.add_row(
            str(row["id"]),
            row.get("run_date", "—"),
            _dir_cell(row.get("direction", "over")),
            row.get("player", "—"),
            row.get("stat_type", "—").upper(),
            str(row.get("line", "—")),
            f"{row.get('final_score', row.get('rule_score', 0)):.1f}",
            Text(FLAG_ICONS.get(flag, "◐"), style=FLAG_COLORS.get(flag, "white")),
            tier,
            Text(outcome, style=outcome_color),
        )

    console.print(table)
    console.print("[dim]Tier: 1st = primary plays  2nd = secondary 'also look at' plays[/dim]")
    console.print()
