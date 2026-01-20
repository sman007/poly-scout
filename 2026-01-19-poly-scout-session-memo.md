# Poly-Scout Session Memo - 2026-01-19

## Summary
Updated poly-scout to better detect 15-minute crypto traders (BINANCE_SIGNAL strategy).

## Key Finding
Investigated two wallets classified as "UNKNOWN" with very high ROIs:

| Wallet | ROI/mo | Actual Strategy |
|--------|--------|-----------------|
| 0x507e52ef68... | 39,144% | SPORTS (misclassified) |
| 0x2057241a70... | 209,824% | BINANCE_SIGNAL (misclassified) |

### Wallet 0x2057241a70... ("th169")
- Trading: **Bitcoin Up or Down 15-min markets**
- Strategy: Directional betting on BTC price direction
- Entry price: $0.05 (buying "Down")
- This IS the fast 15-min crypto strategy we want to find

## Bug Fixed
**Problem:** Classifier required `combined_avg > $1` to detect BINANCE_SIGNAL.
- This only matched arb patterns (buying both YES and NO)
- Missed directional traders who bet one side cheaply

**Fix:** Now any wallet with >50% trades on 15-min crypto markets is classified as BINANCE_SIGNAL.
```python
# Before: required arb pattern
if combined_avg > 1.0 and crypto_15m_pct > 0.5:
    likely_strategy = STRATEGY_BINANCE_SIGNAL

# After: detects both arb AND directional
if crypto_15m_pct > 0.5:
    likely_strategy = STRATEGY_BINANCE_SIGNAL
    if combined_avg > 1.0:
        edge_explanation = "Binance signal arb - buying both sides > $1"
    else:
        edge_explanation = "Binance signal directional - betting on price direction"
```

## Deployment
- Deployed to Vultr (pm-vultr / 95.179.138.245)
- Daemon running, scanning every 15 min
- Telegram alerts enabled

## Files Changed
- `src/daemon.py` - Fixed strategy classification logic

## Next Steps
- Monitor for BINANCE_SIGNAL detections in upcoming scans
- These are the high-priority fast-profit strategies (96 compounds/day)
