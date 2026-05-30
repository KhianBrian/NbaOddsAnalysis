import json
import anthropic
from openai import OpenAI
import sys


SYSTEM_PROMPT = """You are an elite NBA betting analyst with 15 years of experience. You have deep knowledge of:
- How individual player usage rates shift when teammates are injured or rested
- Back-to-back fatigue patterns (players with high minutes load show stat drops 60% of the time on second night)
- How pace of play affects counting stats (points, rebounds, assists all scale with possessions)
- Defender assignment tendencies — elite wing defenders like Kawhi Leonard, Mikal Bridges, or OG Anunoby on a scorer typically suppress points by 15-25%
- Home court advantage: players average +1.2 points, +0.4 rebounds at home on average
- Revenge game motivation: players facing former teams statistically outperform their average by 8-12%
- Fourth-quarter strategy: teams with large leads reduce star player minutes, killing prop value
- The "trap line" phenomenon: books set lines at psychological anchors (20.5, 25.5) that attract public money regardless of edge
- SGP correlation: in high-total games (230+), all player counting stats benefit; in defensive battles (under 210), compress your projections

Your job is to provide sharp, concise adjustments to player prop plays based on statistical data provided. Be a contrarian when the data supports it. Never give a green flag just because the hit rate is high — question WHY it's high and whether it continues."""


def _is_openrouter_key(api_key: str) -> bool:
    return api_key.startswith("sk-or-v1-")


def _build_play_summary(play: dict) -> str:
    s = play.get("splits", {})
    cv = s.get("coefficient_of_variation", 0)
    std = s.get("std_dev", 0)
    l3_avg = s.get("last_3_avg", 0)
    blowout = s.get("blowout_games", 0)

    return (
        f"Player: {play['player']} | Stat: {play['stat_type']} | Line: {play['line']} | "
        f"Book: {play.get('book', 'N/A')} | Odds: {play.get('over_odds', 'N/A')}\n"
        f"  Hit rate L5: {s.get('hit_rate_l5', 0):.0%} ({s.get('hits_l5', 0)}/5) | "
        f"Hit rate L10: {s.get('hit_rate_l10', 0):.0%} ({s.get('hits_l10', 0)}/10)\n"
        f"  Avg L5: {s.get('avg_l5', 0):.1f} | Avg L10: {s.get('avg_l10', 0):.1f} | "
        f"Avg L3: {l3_avg:.1f} | Range L10: {s.get('min_l10', 0):.0f}–{s.get('max_l10', 0):.0f}\n"
        f"  Trend: {'↑' if s.get('trend', 0) > 0 else '↓'} {abs(s.get('trend', 0)):.1%} | "
        f"Line vs avg: {s.get('line_value', 0):+.1%} | Rule score: {play.get('rule_score', 0):.1f}\n"
        f"  Std dev (L10): {std:.2f} | Coeff of variation: {cv:.2f} | "
        f"Blowout games (L10): {blowout}/10\n"
        f"  Consistency: {'LOW VARIANCE ✓' if cv < 0.25 else 'HIGH VARIANCE ⚠' if cv > 0.45 else 'MODERATE'} | "
        f"Blowout risk: {'HIGH ⚠' if blowout >= 2 else 'LOW'}\n"
        f"  Game: {play.get('away_team', '?')} @ {play.get('home_team', '?')}"
        + (f"\n  ⚠ SMALL SAMPLE: only {s.get('games_available', '?')} playoff games available"
           if s.get("small_sample") else "")
    )


def _call_openrouter(prompt: str, api_key: str, model: str) -> str:
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def evaluate_plays(plays: list[dict], api_key: str, model: str, batch_size: int = 15, game7_context: str = None) -> list[dict]:
    """Send scored plays to Claude for contextual reasoning. Returns plays with AI fields added."""
    if not plays:
        return plays

    use_openrouter = _is_openrouter_key(api_key)
    effective_model = model

    game7_block = ""
    if game7_context:
        game7_block = (
            "\nGAME 7 INTELLIGENCE — READ THIS BEFORE EVALUATING ANY PLAY:\n"
            "This is a Game 7. Apply everything below as live series context. It overrides any generic reasoning.\n\n"
            + game7_context +
            "\n\nGAME 7 ANALYSIS RULES:\n"
            "- Weight this intelligence heavily — it is specific, verified, and current.\n"
            "- Penalise role player props harder than normal (minutes compress in close Game 7s).\n"
            "- Boost reliability props for elite stars who have Game 7 pedigree.\n"
            "- Flag any prop involving a confirmed injured or absent player as RED immediately.\n"
            "- Be especially sceptical of three-point props for role players — pace compresses in Game 7.\n"
            "- Rebounds for elite big men are the most reliable prop type in this game.\n"
        )

    for batch_start in range(0, len(plays), batch_size):
        batch = plays[batch_start: batch_start + batch_size]

        plays_text = "\n\n".join(
            f"[Play {i + 1}]\n{_build_play_summary(p)}"
            for i, p in enumerate(batch)
        )

        prompt = (
            "Evaluate these NBA player prop plays. Apply your NBA expertise to each one.\n"
            + game7_block + "\n"
            "For each play, think about:\n"
            "1. Is the line a TRAP? (set to attract bets despite poor value)\n"
            "2. Is there a GAME SCRIPT concern? (blowout risk, low total, heavy favorite)\n"
            "3. Is there a MATCHUP EDGE? (weak defender, high-pace opponent, or elite lock-down defender)\n"
            "4. Is the CONSISTENCY reliable or is this a volatile player riding a hot streak?\n"
            "5. Is there a FATIGUE or REST factor worth noting?\n\n"
            'Return ONLY this JSON, no markdown, no explanation outside the JSON:\n'
            '{\n  "plays": [\n    {\n'
            '      "confidence_adjustment": <integer -20 to +20>,\n'
            '      "flag": <"green"|"yellow"|"red">,\n'
            '      "rationale": "<one sentence, max 25 words, be SPECIFIC — name the actual reason>",\n'
            '      "trap_detected": <true|false>,\n'
            '      "key_risk": "<the single biggest risk to this play in 5 words or less>"\n'
            '    }\n  ]\n}\n\n'
            "Plays:\n" + plays_text
        )

        try:
            if use_openrouter:
                raw = _call_openrouter(prompt, api_key, effective_model)
            else:
                raw = _call_anthropic(prompt, api_key, effective_model)

            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.rsplit("```", 1)[0].strip()
            parsed = json.loads(clean)
            ai_plays = parsed.get("plays", [])
        except json.JSONDecodeError as e:
            print(f"\n[AI ERROR] Response was not valid JSON: {e}", file=sys.stderr)
            print(f"[AI RAW RESPONSE] {raw[:500] if 'raw' in dir() else 'no response received'}", file=sys.stderr)
            ai_plays = []
        except Exception as e:
            print(f"\n[AI ERROR] {type(e).__name__}: {e}", file=sys.stderr)
            ai_plays = []

        for i, play in enumerate(batch):
            ai = ai_plays[i] if i < len(ai_plays) else {}
            adj = ai.get("confidence_adjustment", 0)
            flag = ai.get("flag", "yellow")
            rationale = ai.get("rationale", "Insufficient AI data.")
            trap_detected = ai.get("trap_detected", False)
            key_risk = ai.get("key_risk", "Unknown")

            play["ai_adjustment"] = adj
            play["ai_flag"] = flag
            play["ai_rationale"] = rationale
            play["trap_detected"] = trap_detected
            play["key_risk"] = key_risk
            play["final_score"] = round(play.get("rule_score", 0) + adj, 2)

    return plays
