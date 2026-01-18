# Signal Detection Module

The `signals.py` module detects anomalous wallet behavior that indicates a trader has found an exploitable edge in prediction markets.

## Overview

The module identifies patterns that distinguish skilled traders from lucky gamblers:
- **Statistical anomalies** (e.g., 90%+ win rate over 100+ trades)
- **Sudden profit spikes** (e.g., 7-day profit >> 30-day average)
- **Consistent profitability** (e.g., positive profit every day for a week)
- **Behavioral patterns** (e.g., specialization, frequency changes)

## Core Classes

### `Signal`

Represents a detected anomaly with:
- `signal_type`: Type of anomaly (e.g., PROFIT_SPIKE, WIN_RATE_ANOMALY)
- `strength`: Signal strength from 0.0 to 1.0
- `description`: Human-readable explanation
- `evidence`: Supporting data and metrics
- `timestamp`: When detected

### `SignalDetector`

Main detection engine with methods for:

#### `detect_all_signals(wallet, trades) -> list[Signal]`
Runs all detection methods and returns sorted signals.

#### Individual Signal Detectors

1. **`profit_spike_signal(trades, threshold_multiplier=3.0)`**
   - Detects when 7-day profit exceeds 3x the 30-day average
   - Indicates recent discovery of an edge

2. **`win_rate_anomaly_signal(win_rate, trade_count)`**
   - Uses binomial test to detect statistically improbable win rates
   - 90%+ win rate over 100+ trades is extremely unlikely without an edge

3. **`new_wallet_success_signal(first_seen, profit)`**
   - New wallet (<60 days) with >$10k profit
   - Suggests starting with knowledge rather than learning

4. **`concentration_signal(market_distribution)`**
   - Detects specialization (>80% trades in one category)
   - Indicates domain expertise or category-specific edge

5. **`velocity_signal(trades)`**
   - Trading frequency increased 5x+ recently
   - Suggests aggressive exploitation of new opportunity

6. **`consistent_edge_signal(trades)`**
   - Positive profit every day for 7+ consecutive days
   - Rare in gambling, expected when exploiting an edge

#### Composite Scoring

**`calculate_alpha_score(signals) -> float`**

Combines signals with reliability weights:
- WIN_RATE_ANOMALY: 0.25 (strongest evidence)
- CONSISTENT_EDGE: 0.20
- PROFIT_SPIKE: 0.20
- RAPID_GROWTH: 0.15
- FREQUENCY_SPIKE: 0.10
- MARKET_SPECIALIST: 0.10

Returns overall likelihood (0.0-1.0) that wallet has found an edge.

## Usage Example

```python
from signals import SignalDetector, WalletProfile, Trade

# Initialize detector
detector = SignalDetector()

# Analyze wallet
signals = detector.detect_all_signals(wallet, trades)

# Get composite score
alpha_score = detector.calculate_alpha_score(signals)

if alpha_score >= 0.7:
    print("Strong evidence of edge - HIGH PRIORITY")
elif alpha_score >= 0.5:
    print("Moderate evidence - worth monitoring")
```

## Signal Types

| Type | Description | Threshold |
|------|-------------|-----------|
| `PROFIT_SPIKE` | 7-day profit spike | 3x 30-day average |
| `WIN_RATE_ANOMALY` | Improbable win rate | 90%+ over 100+ trades |
| `RAPID_GROWTH` | New wallet success | <60 days, >$10k profit |
| `MARKET_SPECIALIST` | Category concentration | >80% in one category |
| `FREQUENCY_SPIKE` | Trading velocity increase | 5x baseline |
| `CONSISTENT_EDGE` | Daily profit streak | 7+ consecutive days |

## Statistical Methods

- **Binomial Test**: Tests if win rate significantly exceeds 50% (fair odds)
- **P-value Threshold**: 0.01 (1% significance level)
- **Fallback**: Normal approximation when scipy unavailable

## Dependencies

- `scipy` (optional but recommended for exact binomial test)
- Standard library: `dataclasses`, `datetime`, `collections`, `math`

## Configuration

All thresholds can be customized:

```python
detector = SignalDetector()

# Custom profit spike threshold (4x instead of 3x)
signal = detector.profit_spike_signal(trades, threshold_multiplier=4.0)

# Custom win rate threshold (95% instead of 90%)
signal = detector.win_rate_anomaly_signal(
    win_rate,
    trade_count,
    threshold=0.95
)
```

## Integration Notes

The module includes placeholder `Trade` and `WalletProfile` dataclasses. Replace these with your actual data models:

```python
# Remove placeholder classes from signals.py
# Import your models instead:
from your_models import Trade, WalletProfile
```

## Performance Considerations

- All methods are O(n) or better where n = number of trades
- `detect_all_signals()` makes a single pass through trades
- No expensive API calls or I/O operations
- Safe for real-time analysis of active wallets

## Future Enhancements

Potential additions:
- Time-series analysis of profit trajectory
- Correlation with market events
- Social graph analysis (copy trading detection)
- Machine learning classification
- Cross-market arbitrage detection
