# Weather Bucket Arbitrage Strategy

**Based on:** 0xf2e346ab London Temperature Bot ($204 → $24K, 73% win rate, 1300+ trades)

---

## Core Concept

**You're NOT predicting weather. You're exploiting pricing inefficiencies.**

Temperature markets have multiple brackets (e.g., 0-5°C, 5-10°C, 10-15°C...).
Each bracket is priced independently by market makers.
Often the prices don't add up correctly → arbitrage opportunity.

---

## How It Works

### Step 1: Find Multi-Bracket Weather Events

Look for events with structure like:
```
"What will be the high temperature in London on Jan 28?"
├── Below 0°C    → Market A
├── 0°C to 5°C   → Market B
├── 5°C to 10°C  → Market C
├── 10°C to 15°C → Market D
├── Above 15°C   → Market E
```

### Step 2: Sum All Bracket Prices

```
Bracket      YES Price    Implied Prob
Below 0°C    $0.02        2%
0-5°C        $0.15        15%
5-10°C       $0.45        45%
10-15°C      $0.30        30%
Above 15°C   $0.05        5%
─────────────────────────────────
TOTAL        $0.97        97%   ← ARBITRAGE! Should be 100%
```

### Step 3: Execute Arbitrage

**If sum < $1.00:** Buy YES on ALL brackets
- Cost: $0.97
- Payout: $1.00 (one bracket ALWAYS wins)
- Profit: $0.03 (3.1% guaranteed)

**If sum > $1.00:** Buy NO on ALL brackets
- This is rarer but also works

### Step 4: Alternative - Adjacent Bracket Mispricing

Even when sum ≈ $1.00, individual brackets can be mispriced:

```
Bracket      Market Price   True Prob (from forecasts)
5-10°C       $0.15          22%  ← UNDERVALUED by 7%
10-15°C      $0.55          48%  ← OVERVALUED by 7%
```

Strategy:
- Buy YES on undervalued bracket (5-10°C)
- Buy NO on overvalued bracket (10-15°C) as hedge
- Net profit when either hits

---

## Entry Criteria

| Criteria | Threshold |
|----------|-----------|
| Sum of all brackets | < $0.98 OR > $1.02 |
| Individual bracket edge | > 5% vs neighbors |
| Liquidity per bracket | > $500 |
| Time to resolution | < 48 hours |
| Cities | London, Seoul, Wellington, NYC |

---

## Position Sizing

For a **pure arbitrage** (sum ≠ $1.00):
```
Bet Size = Min(Available Liquidity, $100) per bracket
Total Cost = Sum of all bracket bets
Guaranteed Profit = $1.00 - Total Cost
```

For an **edge play** (single bracket undervalued):
```
Bet Size = Kelly Fraction × Bankroll
Kelly = (edge / odds) - ((1 - edge) / (1 - odds))
Max 5% of bankroll per trade
```

---

## Risk Management

| Risk | Mitigation |
|------|------------|
| Slippage | Check order book depth before entry |
| Resolution disputes | Only trade established cities |
| Liquidity vanishes | Set max position per bracket |
| Sum recalculates | Re-check prices before each leg |

---

## Expected Performance

Based on 0xf2e346ab's results:

| Metric | Value |
|--------|-------|
| Win Rate | 73% |
| Avg Trade Size | $18.50 |
| Avg Profit/Trade | ~$1.40 |
| Trades per Day | ~4-5 |
| Monthly Return | ~15-20% |

---

## Implementation

### Scanner Logic

```python
def find_bucket_arbitrage(events):
    for event in weather_events:
        brackets = get_brackets(event)

        # Check sum arbitrage
        total_yes = sum(b.yes_price for b in brackets)
        if total_yes < 0.98:
            edge = 1.0 - total_yes
            return ArbitrageOpportunity(
                type="SUM_UNDER",
                brackets=brackets,
                edge=edge
            )

        # Check adjacent mispricing
        for i, bracket in enumerate(brackets[:-1]):
            next_bracket = brackets[i+1]
            if bracket.yes_price < 0.20 and next_bracket.yes_price > 0.40:
                # Potential undervaluation
                return ArbitrageOpportunity(
                    type="ADJACENT_EDGE",
                    buy_bracket=bracket,
                    hedge_bracket=next_bracket
                )
```

### Paper Trade Logging

```python
{
    "strategy": "weather_bucket",
    "event": "London High Temp Jan 28",
    "type": "SUM_UNDER",
    "brackets": ["0-5C", "5-10C", "10-15C", "15-20C"],
    "prices": [0.15, 0.45, 0.30, 0.08],
    "total_cost": 0.98,
    "expected_profit": 0.02,
    "timestamp": "2026-01-26T22:00:00Z"
}
```

---

## Why This Works for Small Bankroll

1. **No weather prediction needed** - pure math
2. **Low capital requirement** - starts at $200
3. **High frequency** - multiple opportunities daily
4. **Consistent returns** - 73% win rate proven
5. **No speed advantage needed** - prices stable for hours

---

## Sources

- [How Polymarket makes millions from weather predictions](https://investx.fr/en/crypto-news/polymarket-london-weather-betting/)
- 0xf2e346ab wallet analysis
- [Wethr.net](https://wethr.net/) for market data

*Created: 2026-01-26*
