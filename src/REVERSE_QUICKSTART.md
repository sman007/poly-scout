# Strategy Reverser - Quick Start Guide

## 5-Minute Setup

### 1. Import the Module
```python
from reverse import (
    StrategyReverser,
    Trade, WalletProfile, WalletAnalysis,
    to_markdown, to_json, to_config
)
from datetime import datetime, timedelta
```

### 2. Prepare Your Data
```python
# Wallet info
wallet = WalletProfile(
    address="0x...",
    total_trades=1000,
    active_days=30,
    creation_date=datetime.now() - timedelta(days=30),
    total_pnl=50000.0,
    current_balance=75000.0
)

# Trades (from API or blockchain)
trades = [
    Trade(
        timestamp=datetime.now(),
        market_id="market_123",
        market_title="BTC UP next 15 min",
        outcome="YES",
        side="BUY",
        shares=1000,
        price=0.48,
        value=480.0,
        market_type="binary"
    ),
    # ... more trades
]

# Analysis summary
analysis = WalletAnalysis(
    wallet=wallet,
    primary_markets=["crypto"],
    avg_trade_size=500.0,
    avg_holding_period=timedelta(minutes=15),
    win_rate=0.95,
    peak_exposure=10000.0,
    trading_hours=list(range(24))
)
```

### 3. Reverse Engineer
```python
reverser = StrategyReverser()
blueprint = reverser.reverse_engineer(wallet, trades, analysis)
```

### 4. Get Results
```python
# Markdown report
print(to_markdown(blueprint))

# JSON data
json_str = to_json(blueprint)

# Bot config
config = to_config(blueprint)

# Pseudocode
pseudocode = reverser.generate_pseudocode(blueprint)
```

## Quick Reference

### Strategy Types Detected
| Type | Description | Win Rate |
|------|-------------|----------|
| `arbitrage_binary` | YES+NO hedging | 95-100% |
| `arbitrage_multi` | All outcomes | 100% |
| `market_maker` | Spread capture | 85-95% |
| `directional` | Prediction-based | 50-75% |
| `sniper` | Event-triggered | 60-80% |
| `hybrid` | Mixed approach | Varies |

### Rules Extracted
| Rule Type | Examples |
|-----------|----------|
| Entry | "sum(YES+NO) < 0.94", "Buy all 14 candidates" |
| Exit | "Hold to resolution", "Take profit at 20%" |
| Sizing | "Fixed $5k", "Compound profits" |
| Market | "Focus on crypto", "15min timeframes" |

### Confidence Levels
| Score | Meaning |
|-------|---------|
| 0.9+ | Very high - almost always followed |
| 0.7-0.9 | High - usually followed |
| 0.5-0.7 | Moderate - often followed |
| < 0.5 | Low - filtered out |

### Replicability Scores
| Score | Assessment |
|-------|------------|
| 0.8+ | Highly replicable |
| 0.6-0.8 | Moderately replicable |
| 0.4-0.6 | Difficult |
| < 0.4 | Very difficult |

## Common Use Cases

### 1. Analyze Single Wallet
```python
reverser = StrategyReverser()
blueprint = reverser.reverse_engineer(wallet, trades, analysis)
print(f"Strategy: {blueprint.strategy_type.value}")
print(f"Replicability: {blueprint.replicability_score:.1%}")
```

### 2. Compare Multiple Wallets
```python
blueprints = []
for address in wallet_addresses:
    wallet, trades, analysis = fetch_data(address)
    blueprint = reverser.reverse_engineer(wallet, trades, analysis)
    blueprints.append(blueprint)

# Find best
best = max(blueprints, key=lambda b: b.replicability_score)
```

### 3. Extract Specific Rules
```python
entry_rules = reverser.extract_entry_rules(trades)
exit_rules = reverser.extract_exit_rules(trades)
sizing_rules = reverser.extract_sizing_rules(trades)
market_filters = reverser.extract_market_selection(trades)
```

### 4. Custom Thresholds
```python
# Strict analysis
reverser = StrategyReverser(
    min_confidence=0.9,  # Only very high confidence
    min_evidence=100     # Require lots of data
)
```

## Example Output

### Binary Arbitrage
```
Type: arbitrage_binary
Replicability: 81.3%
Capital: $1.4M

Entry: sum(YES+NO) < 0.94 (90% confidence)
Exit: Hold to resolution (100% confidence)
Size: Fixed $4,700 (98% confidence)

Daily P&L: $23,704
Per-trade: $17.32 (0.37%)
Win rate: 98%
```

### Multi-Outcome Arbitrage
```
Type: arbitrage_multi
Replicability: 47.2%
Capital: $274K

Entry: Buy all candidates when sum < $1
Markets: Focus on 'president' elections
Size: ~$8,299 per trade

Daily P&L: $7,177
Per-trade: $2,871 (32.82%)
Win rate: 100%
Timeframe: > 1 month
```

## File Locations

- **Module**: `C:/Projects/poly-scout/src/reverse.py`
- **Examples**: `C:/Projects/poly-scout/src/reverse_example.py`
- **Docs**: `C:/Projects/poly-scout/src/README_REVERSE.md`
- **Summary**: `C:/Projects/poly-scout/src/REVERSE_MODULE_SUMMARY.md`

## Run Examples
```bash
cd C:/Projects/poly-scout/src
python reverse_example.py
```

## Integration Points

### With Polymarket API
```python
import requests

response = requests.get(
    f"https://data-api.polymarket.com/trades?user={address}"
)
trades_data = response.json()
# Convert to Trade objects...
```

### With Trading Bot
```python
config = to_config(blueprint)
bot = TradingBot(config)
bot.run()
```

### With Dashboard
```python
markdown = to_markdown(blueprint)
save_to_dashboard(markdown)
```

## Tips

1. **More data = better confidence**: 100+ trades recommended
2. **Check replicability first**: Focus on 0.6+ scores
3. **Validate capital requirements**: Ensure you have sufficient funds
4. **Consider timeframes**: Match your investment horizon
5. **Monitor win rates**: Higher = more consistent

## Troubleshooting

### Low Replicability (< 0.5)
- Insufficient trades (< 50)
- Complex/changing strategy
- Missing data

### No Rules Extracted
- Check min_confidence threshold (try 0.5)
- Check min_evidence threshold (try 5)
- Verify trade data format

### Unexpected Strategy Type
- Review market_positions grouping
- Check trade timestamps
- Validate outcome fields

## Next Steps

1. Run `reverse_example.py` to see it in action
2. Read `README_REVERSE.md` for detailed docs
3. Review `REVERSE_MODULE_SUMMARY.md` for technical details
4. Integrate with your poly-scout workflow

**Ready to reverse engineer strategies!** 🔍
