import json
from datetime import date
from .database import get_connection


def log_recommendations(plays: list[dict], is_secondary: bool = False) -> list[int]:
    conn = get_connection()
    c = conn.cursor()
    today = date.today().isoformat()
    ids = []

    for play in plays:
        s = play.get("splits", {})
        c.execute("""
            INSERT INTO recommendations
              (run_date, player, stat_type, direction, line, over_odds, book,
               hit_rate_l5, hit_rate_l10, weighted_hr, avg_l5, avg_l10,
               games_available, small_sample,
               rule_score, ai_adjustment, final_score,
               ai_flag, ai_rationale, trap_detected, key_risk,
               data_source, is_secondary)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            today,
            play.get("player"),
            play.get("stat_type"),
            play.get("direction", "over"),
            play.get("line"),
            play.get("over_odds"),
            play.get("book"),
            s.get("hit_rate_l5"),
            s.get("hit_rate_l10"),
            play.get("weighted_hr"),
            s.get("avg_l5"),
            s.get("avg_l10"),
            s.get("games_available"),
            1 if s.get("small_sample") else 0,
            play.get("rule_score"),
            play.get("ai_adjustment"),
            play.get("final_score"),
            play.get("ai_flag"),
            play.get("ai_rationale"),
            1 if play.get("trap_detected") else 0,
            play.get("key_risk"),
            play.get("data_source"),
            1 if is_secondary else 0,
        ))
        ids.append(c.lastrowid)

    conn.commit()
    conn.close()
    return ids


def log_parlays(parlays: list[dict], rec_ids: list[int]):
    conn = get_connection()
    c = conn.cursor()
    today = date.today().isoformat()

    for parlay in parlays:
        leg_ids = json.dumps([rec_ids[i] for i in parlay.get("leg_indices", []) if i < len(rec_ids)])
        c.execute("""
            INSERT INTO parlays
              (run_date, parlay_type, n_legs, leg_ids, leg_summary, est_combined_hr)
            VALUES (?,?,?,?,?,?)
        """, (
            today,
            parlay.get("parlay_type", "multi"),
            parlay.get("n_legs"),
            leg_ids,
            parlay.get("summary", ""),
            parlay.get("est_combined_hr"),
        ))

    conn.commit()
    conn.close()


def get_history(
    limit: int = 50,
    include_secondary: bool = False,
    player: str | None = None,
    stat: str | None = None,
    direction: str | None = None,
    outcome: str | None = None,
    run_date: str | None = None,
) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()

    conditions = []
    params = []

    if not include_secondary:
        conditions.append("is_secondary = 0")

    if player:
        conditions.append("LOWER(player) LIKE ?")
        params.append(f"%{player.lower()}%")

    if stat:
        conditions.append("LOWER(stat_type) = ?")
        params.append(stat.lower())

    if direction:
        conditions.append("direction = ?")
        params.append(direction.lower())

    if outcome == "pending":
        conditions.append("outcome IS NULL")
    elif outcome:
        conditions.append("outcome = ?")
        params.append(outcome.lower())

    if run_date:
        conditions.append("run_date = ?")
        params.append(run_date)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    c.execute(f"""
        SELECT * FROM recommendations
        {where}
        ORDER BY created_at DESC
        LIMIT ?
    """, params)

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_parlay_history(
    limit: int = 50,
    parlay_type: str | None = None,
    outcome: str | None = None,
    run_date: str | None = None,
    n_legs: int | None = None,
) -> list[dict]:
    conn = get_connection()
    c = conn.cursor()

    conditions = []
    params = []

    if parlay_type:
        conditions.append("parlay_type = ?")
        params.append(parlay_type.upper())

    if outcome == "pending":
        conditions.append("outcome IS NULL")
    elif outcome:
        conditions.append("outcome = ?")
        params.append(outcome.lower())

    if run_date:
        conditions.append("run_date = ?")
        params.append(run_date)

    if n_legs:
        conditions.append("n_legs = ?")
        params.append(n_legs)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    c.execute(f"""
        SELECT * FROM parlays
        {where}
        ORDER BY created_at DESC
        LIMIT ?
    """, params)

    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def place_parlay(parlay_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE parlays SET placed = 1 WHERE id = ?", (parlay_id,))
    if c.rowcount == 0:
        raise ValueError(f"No parlay found with ID {parlay_id}")
    conn.commit()
    conn.close()


def log_parlay_outcome(parlay_id: int, outcome: str):
    valid = {"win", "loss", "push", "void"}
    if outcome not in valid:
        raise ValueError(f"Outcome must be one of: {', '.join(valid)}")
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE parlays SET outcome = ?, placed = 1 WHERE id = ?", (outcome, parlay_id))
    if c.rowcount == 0:
        raise ValueError(f"No parlay found with ID {parlay_id}")
    conn.commit()
    conn.close()


def log_outcome(rec_id: int, outcome: str):
    valid = {"win", "loss", "push", "void"}
    if outcome not in valid:
        raise ValueError(f"Outcome must be one of: {', '.join(valid)}")
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE recommendations SET outcome = ?, placed = 1 WHERE id = ?", (outcome, rec_id))
    conn.commit()
    conn.close()
