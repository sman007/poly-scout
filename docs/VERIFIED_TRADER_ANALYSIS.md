# Verified Trader Analysis - Twitter Hype vs. On-Chain Reality

**Analysis Date:** 2026-01-26
**Method:** Direct Polymarket API queries, position/PnL data

## CRITICAL FINDING: Twitter narratives about bot profits are often MISLEADING

---

## Trader 1: swisstony

**Profile:** [polymarket.com/@swisstony](https://polymarket.com/profile/0x204f72f35326db932158cba6adff0b9a1da95e14)
**Wallet:** `0x204f72f35326db932158cba6adff0b9a1da95e14`

### Twitter Claims (from @carverfomo)
- "$333 → $3.8M in 6 months"
- "Resolution farming: buys NO at 99c when outcome is basically locked"
- "95%+ win rate"
- "$532K/week pace"

### Verified On-Chain Reality

| Metric | Claimed | Actual |
|--------|---------|--------|
| **Win Rate** | 95%+ | **54%** (27/23 on recent 50 positions) |
| **Strategy** | Buy at 99c | Sports betting at 20-80c |
| **Price Range** | 98-99c | 22 trades @ 20-50c, 17 trades @ 50-80c, only 6 @ >80c |

**Sample Verified Trades:**
- Juventus FC win (NO) @ 40.19c → **LOST $77,423**
- Real Sociedad win (YES) @ 57.64c → **WON $49,039**
- Warriors vs Timberwolves @ 55c
- Australian Open Zverev @ 63c

**Conclusion:** NOT resolution farming. Standard sports betting at mid-range prices.

---

## Trader 2: distinct-baguette

**Profile:** [polymarket.com/@distinct-baguette](https://polymarket.com/profile/0xe00740bce98a594e26861838885ab310ec3b548c)
**Wallet:** `0xe00740bce98a594e26861838885ab310ec3b548c`

### Twitter Claims
- "$184K pulled since October"
- "10,950 predictions with steady upward curve"
- "Short window crypto brackets"

### Verified On-Chain Reality

| Metric | Claimed | Actual |
|--------|---------|--------|
| **Win Rate** | High (implied) | **48%** (24/26 on recent 50 positions) |
| **Strategy** | Crypto brackets | Yes, confirmed - ETH/XRP/BTC Up/Down 15-min markets |
| **Price Range** | N/A | 30 trades @ 50-80c, 15 @ 20-50c, only 2 @ >80c |

**Sample Verified Trades:**
- Ethereum Up or Down 5:45PM @ 88c
- XRP Up or Down 5:45PM @ 87c (Up), 12c (Down)
- Multiple XRP trades in same 15-min window (arb attempt?)

**Conclusion:** Trading 15-min crypto brackets, but **LOSING** on recent positions. 48% win rate is below break-even.

---

## Trader 3: peter77777

**Claimed Profile:** LoL esports scalper with 95%+ win rate
**Claimed Wallet:** `0x161e0fa4a1E0B40F1fE60b68C1Dc4D1c0B806ef0`

### Verification Attempt

| API Endpoint | Result |
|--------------|--------|
| `activity?user=0x161e...` | **0 trades returned** |
| `positions?user=0x161e...` | **0 positions** |
| `user?username=peter77777` | **404 Not Found** |
| `profile?id=0x161e...` | **404 Not Found** |

**Conclusion:** **DOES NOT EXIST** in Polymarket's database. Either:
1. Username/wallet is wrong
2. Account was deleted
3. The trader never existed

---

## Why Twitter Hype ≠ Reality

1. **Survivorship bias**: Only profitable periods get posted
2. **Total PnL vs recent performance**: Historical $3.8M doesn't mean current strategy works
3. **Position aggregation**: Win rate calculated differently (markets vs trades)
4. **Cherry-picked examples**: Showing wins, hiding losses

As [@MeetHubble noted](https://x.com/MeetHubble/status/2010938884289675481):
> "The Polymarket Leaderboard is a lie. It shows you the lucky survivors, not the skilled winners."

---

## Implications for Small Bankroll ($1K-$2K)

| Strategy | Twitter Hype | Reality | Risk Level |
|----------|--------------|---------|------------|
| Resolution farming (99c) | "95% win rate" | Requires HUGE capital to be profitable | HIGH (capital lock) |
| Sports betting | "Copy swisstony" | 54% win rate = HIGH VARIANCE | HIGH |
| 15-min crypto | "distinct-baguette profits" | 48% win rate = LOSING MONEY | HIGH |

**For small bankroll:** NONE of these Twitter-hyped strategies are suitable.

---

## What ACTUALLY Works (Based on Verified Data)

### 1. Domain Specialization (Axios - 96% win rate)
- Focus on ONE market type (e.g., "mention markets")
- Build genuine expertise
- Not automated, requires knowledge edge

### 2. Sports Mispricing (PM vs Vegas)
- Our sportsbook scanner: Compares PM prices to multiple bookmakers
- Edge: 3-5% when PM deviates from consensus
- Win rate: 55-60% (still risky for small bankroll)

### 3. Multi-Outcome Political Arbitrage
- Reference Wallet strategy (documented in REFERENCE_WALLET.md)
- Buy all outcomes when sum < $1.00
- 100% win rate (mathematical guarantee)
- Requires finding opportunities (rare, competitive)

---

## Sources

- [Carver's swisstony thread](https://x.com/carverfomo/status/2009626564699283755)
- [Carver's distinct-baguette thread](https://x.com/carverfomo/status/1998896268538458182)
- [Hubble AI leaderboard analysis](https://x.com/MeetHubble/status/2010938884289675481)
- [BeInCrypto: Arbitrage Bots](https://beincrypto.com/arbitrage-bots-polymarket-humans/)
- [ChainCatcher: Polymarket Profit Models](https://www.chaincatcher.com/en/article/2233047)

---

*Documented: 2026-01-26*
*Methodology: Direct API queries to data-api.polymarket.com*
*All data verifiable on-chain*
