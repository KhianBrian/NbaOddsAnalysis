# ParlayGod — Guardrails

These rules are hardcoded into the system. They exist to protect the edge.

## Hard Stops — System Will NOT Recommend

- **Insufficient data**: Player has fewer than 5 recent games of data. Not enough signal.
- **Single-book pricing**: Only one bookmaker is offering the line. No competition = no edge to find.
- **AI red flag**: Claude rates a play as red flag, regardless of how high the rule score is.
- **Parlay > 4 legs**: Variance compounds too aggressively. Cap is 4 legs maximum.
- **Anti-correlated SGP legs**: E.g. player goes over assists AND team loses badly. Structural contradiction.

## Soft Warnings — System Will Flag But Still Surface

- **Trending down**: Player's L5 average is meaningfully below L10 average. Play may still have value if line already accounts for the dip.
- **Questionable/DTD status**: System cannot automatically pull real-time injury news. Always verify manually before placing.
- **Back-to-back game**: Player performance can dip. System notes this when detectable.
- **Yellow AI flag**: Claude sees something worth noting — read the rationale before acting.

## What the System Does NOT Know (You Must Check)

- Real-time injury reports (check NBA injury report on game day)
- Late lineup scratches
- Minutes restrictions coming off injury
- Trade deadline moves that haven't propagated to the stats database

## Responsible Use

This system provides statistical analysis and probability estimates. No model predicts the future with certainty. Never bet more than you are prepared to lose. The system is a tool for edge identification, not a guarantee.
