# Live Game Scalp Strategy (Peter 77777 Style)

## Core Insight

Peter 77777's 95%+ win rate comes from buying **during live games** when outcomes become near-certain, NOT from pre-game betting.

## How It Works

1. **Pre-game**: Market at ~55-70% (balanced odds)
2. **During game**: One team gets commanding lead
3. **Price spike**: Favorite jumps to 95-99%
4. **Entry window**: Buy at 95-99c during this spike
5. **Resolution**: Collect $1.00 when game ends

## Example: NFL Championship

```
Pre-game: Patriots 78.5%
4th Quarter, Patriots up 28-7:
  → Patriots price spikes to 97-99%
  → Buy YES @ 98c
  → Game ends, collect $1.00
  → Profit: 2% in ~30 minutes
```

## Key Differences from Regular Scalping

| Aspect | Regular Scalp | Live Game Scalp |
|--------|---------------|-----------------|
| Timing | Pre-game | During game |
| Price window | Static 65%+ | Dynamic spike to 95%+ |
| Win rate | ~70% | ~95%+ |
| Hold time | Hours/days | Minutes |
| Frequency | Anytime | Only during live games |

## Why This Works

1. **Information asymmetry**: Scoreboard shows clear outcome
2. **Market lag**: PM prices update slower than reality
3. **Low risk**: 95%+ favorites rarely collapse (but CAN happen)
4. **Quick exit**: Resolution within minutes/hours

## Risks

- **Comeback**: Team down 28-7 CAN still win (rare but happens)
- **Slippage**: Price may move before order fills
- **Liquidity**: May not get full size at desired price

## Implementation Requirements

1. **Real-time price monitoring** during live games
2. **Fast execution** (seconds matter)
3. **Pre-funded account** ready to trade
4. **Game schedule awareness** (when to monitor)

## Best Events for This Strategy

1. **NFL** - Conference championships, Super Bowl
2. **NBA** - Playoffs, especially late games
3. **Tennis** - Grand Slam finals
4. **LoL Esports** - Peter 77777's original niche (no longer on PM)

## Today's Opportunity: NFL Championship (Jan 26, 2026)

**AFC**: Patriots (78.5%) vs Broncos (21.5%)
- Game time: ~3pm ET
- Resolution: ~7pm ET
- Watch for: Patriots lead by 14+ in 4th quarter → 95%+ price

**NFC**: Seahawks (55%) vs Rams (45%)
- Game time: ~6:30pm ET
- Resolution: ~10pm ET
- Watch for: Either team up 14+ in 4th quarter → 95%+ price

## Real-Time Monitor

Run `live_game_monitor.py` during games:
```bash
python -m src.live_game_monitor --markets "Patriots AFC,Seahawks NFC" --threshold 0.95
```

This will alert when prices cross 95% threshold.

---

*Based on Peter 77777 (`0x161e...6ef0`) - LoL Esports scalper with 95%+ win rate*
*Documented: 2026-01-26*
