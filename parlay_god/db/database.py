import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "parlaygod.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date        TEXT NOT NULL,
            player          TEXT NOT NULL,
            team            TEXT,
            opponent        TEXT,
            stat_type       TEXT NOT NULL,
            direction       TEXT DEFAULT 'over',
            line            REAL NOT NULL,
            over_odds       INTEGER,
            book            TEXT,
            hit_rate_l5     REAL,
            hit_rate_l10    REAL,
            weighted_hr     REAL,
            avg_l5          REAL,
            avg_l10         REAL,
            games_available INTEGER,
            small_sample    INTEGER DEFAULT 0,
            rule_score      REAL,
            ai_adjustment   INTEGER,
            final_score     REAL,
            ai_flag         TEXT,
            ai_rationale    TEXT,
            trap_detected   INTEGER DEFAULT 0,
            key_risk        TEXT,
            data_source     TEXT,
            is_secondary    INTEGER DEFAULT 0,
            placed          INTEGER DEFAULT 0,
            outcome         TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS parlays (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date        TEXT NOT NULL,
            parlay_type     TEXT NOT NULL,
            n_legs          INTEGER,
            leg_ids         TEXT NOT NULL,
            leg_summary     TEXT NOT NULL,
            est_combined_hr REAL,
            placed          INTEGER DEFAULT 0,
            outcome         TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # Migrate existing tables — add any missing columns without data loss
    _migrate(c, "recommendations", {
        "direction":       "TEXT DEFAULT 'over'",
        "games_available": "INTEGER",
        "small_sample":    "INTEGER DEFAULT 0",
        "trap_detected":   "INTEGER DEFAULT 0",
        "key_risk":        "TEXT",
        "data_source":     "TEXT",
        "is_secondary":    "INTEGER DEFAULT 0",
    })
    _migrate(c, "parlays", {
        "n_legs": "INTEGER",
    })

    conn.commit()
    conn.close()


def _migrate(cursor, table: str, new_columns: dict):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for col, definition in new_columns.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
