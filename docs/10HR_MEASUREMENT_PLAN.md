# 10-Hour Measurement Plan - Real Money Decision

**Start:** 2026-01-26 ~6:30pm ET
**Decision Time:** 2026-01-27 ~4:30am ET
**Bankroll:** $1K-$2K

## CRITICAL CONSTRAINT
Small bankroll = CAN'T SURVIVE DRAWDOWNS
Need: **High win rate (>70%)** + **Low variance** + **Short capital lock-up**

---

## STRATEGIES TO MEASURE

### 1. SPORTSBOOK MISPRICING (PM vs Vegas)
**Status:** ACTIVE in daemon (5 min intervals)
**Claimed Edge:** 3-5%
**Claimed Win Rate:** 55-60%

**Measurement Tasks:**
- [ ] Count opportunities detected in 10 hours
- [ ] Track actual game results for any today's games
- [ ] Run historical backtest if possible

**Risk Assessment:**
- 55% win rate = 0.25% chance of 10 losses in a row
- NOT SUITABLE for $1K bankroll without proven backtest

### 2. SCALP/RESOLUTION FARMING (65%+ markets)
**Status:** ACTIVE in daemon (5 min intervals)
**Claimed Edge:** 1-2%
**Claimed Win Rate:** 95%+ (if buying 95%+ favorites)

**Measurement Tasks:**
- [ ] Track all scalp opportunities detected
- [ ] Note entry prices and resolution times
- [ ] Calculate hypothetical returns

**Risk Assessment:**
- If win rate is truly 95%, this is BEST for small bankroll
- Need to verify with real data

### 3. MULTI-OUTCOME ARBITRAGE (YES+NO < $1)
**Status:** Have find_arbitrage_now.py
**Claimed Edge:** 100% guaranteed
**Claimed Win Rate:** 100%

**Measurement Tasks:**
- [ ] Scan for opportunities every 15 min
- [ ] Check Reference Wallet's current positions
- [ ] Note any opportunities found (likely ZERO - highly competitive)

**Risk Assessment:**
- Zero risk if found, but opportunities are RARE

### 4. NEW MARKET SNIPING
**Status:** ACTIVE in daemon (60 sec intervals)
**Claimed Edge:** Variable (extreme prices on new markets)
**Claimed Win Rate:** Unknown

**Measurement Tasks:**
- [ ] Count new markets detected
- [ ] Note any mispricing alerts
- [ ] Track what happens to flagged markets

**Risk Assessment:**
- Unknown - needs validation

### 5. LIVE GAME SCALPING (Peter 77777 style)
**Status:** THEORETICAL (unverified source)
**Claimed Edge:** 1-2%
**Claimed Win Rate:** 95%+

**Measurement Tasks:**
- [ ] Monitor NFL Championship games TODAY
- [ ] Track when prices hit 95%+ threshold
- [ ] Note if there are actual entry opportunities
- [ ] Watch for comebacks (risk events)

**Games Today:**
- AFC: Patriots vs Broncos (~3pm ET)
- NFC: Seahawks vs Rams (~6:30pm ET)

**Risk Assessment:**
- Strategy is UNVERIFIED but testable TODAY

---

## DATA COLLECTION EVERY 2 HOURS

| Time (ET) | Sportsbook Opps | Scalp Opps | Arb Opps | New Market Alerts | Live Game Status |
|-----------|----------------|------------|----------|-------------------|------------------|
| 6:30pm | | | | | |
| 8:30pm | | | | | |
| 10:30pm | | | | | |
| 12:30am | | | | | |
| 2:30am | | | | | |
| 4:30am | DECISION | | | | |

---

## GO/NO-GO CRITERIA

| Strategy | GO IF | NO-GO IF |
|----------|-------|----------|
| Sportsbook | Backtest shows >55% win, >0 ROI | Win rate <53% |
| Scalp | Win rate >90% on 90%+ markets | Win rate <80% |
| Arbitrage | Any opportunity found | Zero opportunities in 10 hrs |
| New Market | Edge detected >5% | All false positives |
| Live Game | Entry opportunity at 95%+ exists | No opportunities or comeback risk |

---

## COMMANDS FOR MEASUREMENT

**Check daemon log:**
```bash
ssh -i ~/.ssh/vultr_polymarket root@95.179.138.245 "tail -200 /tmp/scout.log | grep -E '(OPPORTUNITY|VALID|edge|SPORTSBOOK|SCALP)'"
```

**Run arbitrage scan:**
```bash
ssh -i ~/.ssh/vultr_polymarket root@95.179.138.245 "cd /root/poly-scout && python3 find_arbitrage_now.py"
```

**Check NFL prices:**
```bash
ssh -i ~/.ssh/vultr_polymarket root@95.179.138.245 "cd /root/poly-scout && python3 -m src.live_game_monitor --find"
```

---

## DECISION FRAMEWORK

After 10 hours, rank strategies by:
1. **Verified win rate** (must be >70% for small bankroll)
2. **Opportunity frequency** (need >1/day minimum)
3. **Capital lock-up** (prefer <24 hours)
4. **Edge size** (bigger = more room for error)

**If NO strategy meets criteria:** DO NOT TRADE. Continue validation.

---

*Created: 2026-01-26*
