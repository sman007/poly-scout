# 0xf2e346ab Weather Trading Strategy Analysis

**Partial Wallet Address:** `0xf2e346ab*` (full address not located)
**Analysis Date:** 2026-01-24
**Status:** Unable to complete analysis - full wallet address not found

---

## Investigation Summary

### Search Attempts Conducted

| Method | Endpoint | Result |
|--------|----------|--------|
| Direct API query | `https://data-api.polymarket.com/activity?user=0xf2e346ab` | 400 Bad Request |
| User profile | `https://data-api.polymarket.com/users/0xf2e346ab` | 404 Not Found |
| Leaderboard search | `https://data-api.polymarket.com/leaderboard?limit=1000` | 404 Not Found (endpoint unavailable) |
| Common address patterns | Tried padding with 0x00, 0xFF, 0x11 | No active trading found |
| Weather market trades | Searched active London temperature markets | No matching address prefix |

### Known Information

Based on the provided context:

1. **Trading Focus:** London daily high temperature ranges
2. **Strategy Type:** Exploits mispricing between temperature brackets
3. **Address Prefix:** `0xf2e346ab`

---

## Weather Trading Context

### Market Structure

London weather markets on Polymarket typically operate as:

- **Exact brackets:** "Will London high be exactly XC?" (e.g., 8C, 9C, 10C)
- **Range brackets:** "Will London high be X or higher?" / "X or lower?"
- **Settlement:** Based on official weather data

### Known Successful Strategies

Based on research and Hans323 analysis:

#### 1. Liquidity Provision Strategy (Hans323)
- **Approach:** SELL "No" positions on exact brackets at >90%
- **Volume:** $365,969 across 265 trades
- **Profit:** Primary income from selling overpriced positions
- **Win rate:** Benefits from exact brackets rarely hitting

#### 2. Bot Arbitrage Strategy
- **Approach:** Buy undervalued ranges (20-30 cents), hedge with neighboring ranges
- **Performance:** $24,000 profit from $204 start, 73% win rate
- **Method:** Exploits structural inefficiencies between adjacent brackets

#### 3. Temporal Lag Strategy (Hans323 variant)
- **Approach:** React to weather forecast updates before market adjusts
- **Profit:** $1.1M+ by exploiting few-minute lag between updates and odds

---

## Expected Strategy: Bracket Arbitrage

### Hypothesis: Mispricing Between Buckets

If this trader "exploits mispricing between buckets," they likely:

1. **Identify misaligned probabilities** across adjacent temperature ranges
2. **Simultaneous positions** across multiple brackets
3. **Guaranteed profit structure** where one winning bracket covers losses on others

### Example Scenario

London forecast: High of 10C with ±2C uncertainty

**Market prices:**
- 8C or lower: 15%
- Exactly 9C: 12%
- Exactly 10C: 20%
- Exactly 11C: 18%
- 12C or higher: 35%

**Total probability: 100%** ✓

**Mispricing example:**
If adjacent brackets sum to >100% or create overlapping value, arbitrage exists.

**Strategy execution:**
1. Buy undervalued bracket (e.g., Exactly 10C at 20% when true probability is 25%)
2. Hedge with neighboring brackets
3. Structure ensures profit regardless of outcome

---

## Why Full Address Couldn't Be Found

### Possible Reasons

1. **Inactive trader:** May not have traded recently (>7 days)
2. **Not on leaderboard:** Profit below top 500-1000
3. **Newer account:** Not yet ranked
4. **Private/unlisted:** Profile not public
5. **API limitations:** Partial address searches not supported
6. **Closed markets:** May only trade settled London markets

### Data Limitations

- **Polymarket leaderboard API:** Returns 404 (endpoint unavailable or changed)
- **User search:** Requires full 42-character Ethereum address
- **Market trade history:** Limited to recent trades on active markets
- **No partial address search:** API doesn't support prefix matching

---

## How to Complete This Analysis

### Manual Steps Required

1. **Get full wallet address:**
   - Check Polymarket profile page if username known
   - Search blockchain explorer (Etherscan/Polygonscan) for transactions starting with 0xf2e346ab
   - Check Polymarket Discord/Twitter for mentions
   - Look for recent London temperature market trades

2. **Once full address obtained:**
   ```bash
   curl "https://data-api.polymarket.com/activity?user=0xf2e346ab[FULL_ADDRESS]&limit=500"
   ```

3. **Filter for weather trades:**
   ```python
   weather_trades = [t for t in trades if 'london' in t['market_title'].lower()
                     and ('temperature' in t['market_title'].lower()
                          or 'high' in t['market_title'].lower())]
   ```

4. **Analyze bracket patterns:**
   - Buy vs Sell ratio
   - Entry price distribution
   - Bracket types (exact, or_higher, or_lower)
   - Position sizes
   - Combined probability checks
   - Evidence of simultaneous positions

---

## Key Questions to Answer (Pending Data)

### Strategy Mechanics
- [ ] How exactly do they exploit "mispricing between buckets"?
- [ ] Do they take simultaneous positions across brackets?
- [ ] Are they buying or selling?
- [ ] What's the typical combined probability of their positions?

### Edge Source
- [ ] Forecast-based (like Hans323)?
- [ ] Pure arbitrage (bracket math doesn't add up)?
- [ ] Liquidity provision (market making)?
- [ ] Temporal lag exploitation?

### Position Structure
- [ ] Entry price ranges
- [ ] Position sizes
- [ ] Holding periods
- [ ] Win rate
- [ ] Profit per trade

### Replicability
- [ ] Capital required
- [ ] Trade frequency
- [ ] Latency requirements
- [ ] Forecast data sources needed
- [ ] Saturation level

---

## Comparison to Known Strategies

### Hans323 (Known)
| Metric | Value |
|--------|-------|
| Strategy | Sell No on exact brackets >90% |
| Direction | SELL only (0 buys) |
| Edge | Exact brackets rarely hit |
| Capital | $10,000+ |
| Win rate | ~86% |

### 0xf2e346ab (Unknown - Needs Data)
| Metric | Value |
|--------|-------|
| Strategy | Bracket mispricing arbitrage (hypothesis) |
| Direction | Unknown |
| Edge | Structural inefficiency between adjacent brackets? |
| Capital | Unknown |
| Win rate | Unknown |

---

## Next Steps

1. **Obtain full wallet address** (42 characters)
2. **Fetch complete trade history:**
   - `/activity` endpoint with limit=500-1000
   - `/positions` endpoint for current holdings
3. **Filter for London temperature markets**
4. **Analyze trade patterns:**
   - Group trades by market
   - Check for simultaneous bracket positions
   - Calculate combined entry prices
   - Identify edge mechanism
5. **Assess replicability:**
   - Capital requirements
   - Data sources needed
   - Competition level
   - Profit potential
6. **Update this document** with findings

---

## Resources

**API Endpoints:**
- Activity: `https://data-api.polymarket.com/activity?user=[ADDRESS]&limit=500`
- Positions: `https://data-api.polymarket.com/positions?user=[ADDRESS]`
- Markets: `https://gamma-api.polymarket.com/markets`

**Related Analysis:**
- [Hans323 Weather Strategy](./HANS323_WEATHER_STRATEGY.md) - Complete analysis of liquidity provision strategy

**Web Research:**
- Weather markets still show inefficiencies (as of Jan 2024)
- Multiple profitable strategies identified
- Bracket arbitrage theoretically viable

---

## Conclusion

**Unable to complete analysis without full wallet address.**

The partial address `0xf2e346ab` is insufficient for API queries. Once the full 42-character Ethereum address is provided, this analysis can be completed following the methodology used for Hans323's weather trading strategy.

**Expected timeline with full address:** 15-30 minutes to fetch data and complete reverse engineering.

---

## Search Methodology Attempted

**Tools Used:**
1. Direct API queries with partial address
2. Common address padding patterns (0x00, 0xFF, 0x11 suffixes)
3. Leaderboard scanning (API unavailable)
4. Active London weather market trade history
5. Web search for public mentions

**Why These Failed:**
- Polymarket API requires exact full addresses
- No partial address/prefix search capability
- Leaderboard API endpoint returns 404
- Wallet may not be actively trading during search window
- No current London temperature markets with recent trades

**What Would Work:**
- Full 42-character address (e.g., `0xf2e346ab[34 more hex characters]`)
- Username on Polymarket platform
- Direct link to Polymarket profile page
- Recent transaction hash involving this address
