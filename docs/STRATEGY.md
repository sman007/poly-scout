# Strategy Documentation

## The Meta-Strategy Concept

### Core Insight

Instead of predicting markets yourself, find traders who already cracked profitable patterns and learn from them.

**Traditional approach:**
```
You -> Analyze market -> Make prediction -> Place bet -> Hope for profit
```

**Meta-strategy approach:**
```
You -> Find profitable wallet -> Reverse-engineer strategy -> Replicate or adapt -> Profit
```

### Why This Works

**Market-proven alpha:**
- Real P&L, not backtest results
- Survived live market conditions
- Natural selection filters bad strategies

**Adaptation to current meta:**
- Detects what works RIGHT NOW
- No lag from historical analysis
- Captures regime shifts automatically

**Diversification:**
- Multiple traders = multiple strategies
- Different edge sources (arbitrage, info, speed)
- Portfolio of approaches reduces risk

**Lower false positives:**
- Profit is hard to fake
- Sustained success filters luck
- Statistical significance improves with sample size

### The Catch

**Strategies decay:**
- Discovered edges get crowded
- Market adapts to arbitrage
- Information spreads over time

**Survivorship bias:**
- You only see winners
- Failed strategies are invisible
- Past performance != future results

**Replication gaps:**
- Private information (insider knowledge)
- Speed advantages (infrastructure)
- Capital constraints (need size for some strategies)
- Skill differences (execution quality)

**Solution:** Continuously scan for NEW alpha, not just follow old winners.

## Signal Types Explained

poly-scout detects six primary signal types that indicate a wallet has found an edge:

### 1. PROFIT_SPIKE

**What it is:** Sudden jump in cumulative profit compared to recent average.

**Detection logic:**
```python
recent_avg_profit_per_day = last_7_days_profit / 7
spike_day_profit = single_day_profit
if spike_day_profit > (recent_avg_profit_per_day * 3.0):
    # PROFIT_SPIKE detected
```

**Example:**
- Wallet averages $200/day for a week
- Makes $1,500 in one day
- Spike multiplier: 7.5x (well above 3.0x threshold)

**What it means:**
- Trader discovered new edge
- Exploit opportunity (e.g., arbitrage gap)
- Event with unique information advantage
- Strategy scaling up

**Strength factors:**
- Multiplier magnitude (higher = stronger)
- Consistency afterward (sustained = stronger)
- Sample size (more history = stronger)

**When to investigate:**
- Strong spike (5x+) with no obvious market event
- Spike followed by consistent higher baseline
- Multiple spikes clustered together

**When to ignore:**
- Single spike returning to baseline (luck)
- Correlated with obvious news event (one-time)
- New wallet (first few trades always volatile)

### 2. WIN_RATE_ANOMALY

**What it is:** Win rate statistically improbable by chance.

**Detection logic:**
```python
# Binomial test: what's probability of W wins in N trades at 50% skill?
p_value = binomial_test(wins, total_trades, 0.5)
if p_value < 0.01 and win_rate > 0.90:
    # WIN_RATE_ANOMALY detected
```

**Example:**
- Wallet: 94 wins out of 100 trades (94% win rate)
- P-value: ~0.00001 (extremely unlikely by chance)
- Conclusion: Trader has genuine edge

**What it means:**
- Real skill, not luck
- Consistent advantage in market selection
- Possible arbitrage or information edge
- Risk management (cuts losses fast)

**Strength factors:**
- Sample size (100+ trades = strong evidence)
- P-value (lower = stronger)
- Sustained over time (not just recent burst)

**Thresholds:**
- >95% win rate over 50+ trades: Very strong
- >90% win rate over 100+ trades: Strong
- >85% win rate over 200+ trades: Moderate
- <85% win rate: Insufficient (could be directional skill)

**When to investigate:**
- 90%+ win rate with 100+ trades
- Sustained over multiple months
- Win rate not declining over time

**When to ignore:**
- <30 trades (too small sample)
- Only recent trades are winners (regression incoming)
- Category-specific (e.g., 95% in obscure markets)

### 3. RAPID_GROWTH

**What it is:** New wallet achieving high profit in short timeframe.

**Detection logic:**
```python
if wallet_age_days <= 60 and total_profit >= 10000:
    growth_rate = total_profit / wallet_age_days
    # RAPID_GROWTH detected
```

**Example:**
- Wallet age: 35 days
- Total profit: $15,000
- Daily rate: $428/day

**What it means:**
- Discovered exploitable edge quickly
- Deployed capital efficiently
- Not grinding slowly (has high conviction)
- Possible new strategy (not well-known)

**Strength factors:**
- Profit/age ratio (higher = stronger)
- Consistency (steady vs lucky burst)
- Trade count (more = stronger)

**Thresholds:**
- $500+/day over 30+ days: Very strong
- $300+/day over 45+ days: Strong
- $150+/day over 60+ days: Moderate

**When to investigate:**
- Consistent daily profit (not one big win)
- Diversified across markets (not luck)
- Accelerating growth (not decelerating)

**When to ignore:**
- Single large win accounting for most profit
- Declining growth rate (luck wearing off)
- Only a few trades (small sample)

### 4. MARKET_SPECIALIST

**What it is:** Concentrated success in specific market category.

**Detection logic:**
```python
category_concentration = max(category_profits) / total_profit
if category_concentration > 0.80:
    # MARKET_SPECIALIST detected
```

**Example:**
- Total profit: $20,000
- Political markets: $17,500 (87.5%)
- Sports markets: $2,500 (12.5%)
- Category concentration: 87.5%

**What it means:**
- Domain expertise (deep knowledge)
- Information edge (sources/analysis)
- Pattern recognition (category-specific)
- Replicable (if you have same knowledge)

**Categories commonly specialized:**
- Politics (polling data, expert analysis)
- Sports (statistical models, insider info)
- Crypto (on-chain data, tech understanding)
- Business (industry knowledge)

**Strength factors:**
- Concentration level (higher = stronger)
- Sample size in category (more = stronger)
- Win rate within category (higher = stronger)

**When to investigate:**
- 80%+ in one category with 50+ trades
- Obvious domain expertise opportunity
- You have knowledge in same category

**When to ignore:**
- Category is random/obscure (no clear edge)
- Small total profit (not validated)
- Only one or two markets (too narrow)

### 5. FREQUENCY_SPIKE

**What it is:** Sudden increase in trading frequency.

**Detection logic:**
```python
recent_trades_per_day = last_7_days_trades / 7
spike_day_trades = single_day_trades
if spike_day_trades > (recent_trades_per_day * 5.0):
    # FREQUENCY_SPIKE detected
```

**Example:**
- Normal: 3 trades/day
- Spike day: 18 trades
- Multiplier: 6x

**What it means:**
- Opportunity window opened (e.g., arbitrage)
- Event-driven strategy activated
- Market inefficiency appeared temporarily
- Automation deployed (bot started)

**When to investigate:**
- Frequency spike + profit spike together
- Sustained higher frequency afterward
- Correlation with specific market events

**When to ignore:**
- Frequency spike but no profit increase
- Single day spike (one-off event)
- Declining frequency after spike

### 6. CONSISTENT_EDGE

**What it is:** Positive profit every day over extended period.

**Detection logic:**
```python
daily_profits = group_trades_by_day(trades)
consecutive_positive_days = count_consecutive_positive(daily_profits)
if consecutive_positive_days >= 7:
    # CONSISTENT_EDGE detected
```

**Example:**
- Last 12 days: all positive
- Range: $50 - $800 daily
- No negative days

**What it means:**
- Risk management (cuts losses aggressively)
- High-probability strategy (market making, arbitrage)
- Disciplined execution (not gambling)
- Replicable (process-driven)

**Strength factors:**
- Consecutive days (more = stronger)
- Profit variability (lower = stronger)
- Sustainability (longer = stronger)

**When to investigate:**
- 10+ consecutive positive days
- Reasonable daily amounts (not one big win)
- Clear strategy pattern (not random)

**When to ignore:**
- Very small daily profits (not meaningful)
- Will inevitably break (regression to mean)
- Only a few days (too early)

## Strategy Classification Methodology

poly-scout classifies wallets into five strategy types:

### ARBITRAGE

**Definition:** Exploiting price discrepancies between related outcomes.

**Characteristics:**
- **Paired trades:** Buy YES + NO on same market (sum < $1)
- **High win rate:** 95%+ (mathematical edge, not prediction)
- **Short hold time:** Minutes to hours (close when mispricing corrects)
- **Many markets:** Scan broadly for opportunities
- **Low variance:** Consistent small wins

**Detection heuristics:**
```python
if win_rate > 0.95 and paired_trade_ratio > 0.6 and avg_hold_time < 3600:
    strategy = ARBITRAGE
```

**Example trades:**
```
Market: "Will Bitcoin hit $100k by EOY?"
Buy YES @ 0.52
Buy NO @ 0.46
Cost: 0.98
Payout: 1.00
Guaranteed profit: $0.02 (2% return)
```

**Edge source:** Market inefficiency, slow price updates, fragmented liquidity

**Capital required:** High (need size to scale small edges)

**Replicability:** High (if you can find same opportunities)

**Risks:**
- Mispriced for a reason (event risk)
- Execution slippage (prices move before fill)
- Market resolution risk (ambiguous outcomes)

### MARKET_MAKING

**Definition:** Providing liquidity by posting two-sided limit orders.

**Characteristics:**
- **Maker ratio:** 70%+ trades are maker orders
- **Two-sided:** Bids and asks in same market
- **Inventory management:** Rebalance positions regularly
- **Spread capture:** Profit from bid-ask spread
- **Many small wins:** Death by a thousand cuts (for counterparties)

**Detection heuristics:**
```python
if maker_ratio > 0.7 and two_sided_ratio > 0.5:
    strategy = MARKET_MAKING
```

**Example trades:**
```
Market: "Will Biden win?"
Post bid: Buy YES @ 0.48 (maker)
Post ask: Sell YES @ 0.52 (maker)
Spread: $0.04 (4 cents)
Win on both fills: 4% return
```

**Edge source:** Time value, order flow information, patience

**Capital required:** Medium-high (need inventory)

**Replicability:** Medium (requires infrastructure)

**Risks:**
- Adverse selection (picked off on news)
- Inventory risk (price moves against position)
- Competition (spreads compress)

### DIRECTIONAL

**Definition:** Taking positions based on outcome predictions.

**Characteristics:**
- **Concentrated:** Few markets, large positions
- **Variable win rate:** 60-75% (prediction skill)
- **Hold to resolution:** Days to weeks
- **Single-sided:** Only one outcome per market
- **High conviction:** Large size per bet

**Detection heuristics:**
```python
gini_coefficient = market_concentration(trades)
if gini_coefficient > 0.5 and single_sided_ratio > 0.8:
    strategy = DIRECTIONAL
```

**Example trades:**
```
Market: "Will Trump win nomination?"
Analysis: Polling shows 80% chance
Market price: 0.65
Edge: 0.80 - 0.65 = 0.15 (15% expected value)
Position: Buy YES @ 0.65 for $5,000
Hold until resolution
```

**Edge source:** Information, analysis, domain expertise

**Capital required:** Low-medium (size per bet, not volume)

**Replicability:** Low (requires same information/analysis)

**Risks:**
- Wrong prediction (lose principal)
- Locked capital (illiquid until resolution)
- Event risk (black swans)

### SNIPER

**Definition:** Event-triggered rapid trading around news/catalysts.

**Characteristics:**
- **Burst trading:** Sudden spikes of activity
- **Many markets:** Diversified across opportunities
- **Fast execution:** Seconds to minutes
- **Event correlation:** Trades cluster around news
- **High frequency:** When active, very active

**Detection heuristics:**
```python
if burst_trading_score > 0.7 and unique_markets > 10:
    strategy = SNIPER
```

**Example sequence:**
```
Event: Debate happens at 9pm
9:02pm: 5 trades across political markets
9:15pm: 8 more trades
9:45pm: 3 more trades
Next day: No trades
Pattern: Exploit immediate post-event mispricing
```

**Edge source:** Speed, event interpretation, temporary inefficiency

**Capital required:** Medium (need quick deployment)

**Replicability:** Low (requires speed + decision-making)

**Risks:**
- Wrong interpretation (market corrects against you)
- Execution delays (advantage disappears)
- Overtrading (fees eat profits)

### HYBRID

**Definition:** Combination of multiple strategies.

**Characteristics:**
- **Mixed patterns:** No single dominant strategy
- **Opportunistic:** Adapts to market conditions
- **Diversified methods:** Arbitrage + directional + making
- **Flexible:** Changes approach over time

**Detection:** Falls into multiple categories with moderate confidence.

**Example:**
- 40% of profit from arbitrage
- 35% from directional bets
- 25% from market making
- No clear dominant strategy

## How Reverse-Engineering Works

### Process Overview

**Step 1: Data Collection**
```python
trades = fetch_wallet_activity(address, limit=1000)
```

**Step 2: Pattern Analysis**
```python
analyzer = TradeAnalyzer()
analysis = analyzer.analyze_wallet(trades)
```

**Step 3: Rule Extraction**
```python
reverser = StrategyReverser()
blueprint = reverser.reverse_engineer(trades)
```

**Step 4: Validation**
- Check edge estimate vs actual P&L
- Verify rule consistency
- Test replicability score

### What Gets Extracted

**Entry Rules:**
- Price thresholds (e.g., "buy YES when price < 0.45")
- Market conditions (e.g., "only markets with >$10k volume")
- Timing patterns (e.g., "trade within 1 hour of event")
- Pairs (e.g., "buy YES+NO when sum < 0.98")

**Exit Rules:**
- Take profit (e.g., "sell when profit > 5%")
- Stop loss (e.g., "exit when loss > 2%")
- Time-based (e.g., "close after 4 hours")
- Event-based (e.g., "exit immediately after news")

**Sizing Rules:**
- Fixed (e.g., "$500 per trade")
- Percentage (e.g., "2% of capital per trade")
- Kelly criterion (e.g., "edge/odds sizing")
- Martingale (e.g., "double after loss")
- Progressive (e.g., "increase with profit")

**Market Filters:**
- Category (e.g., "only politics")
- Volume (e.g., ">$50k liquidity")
- Spread (e.g., "<5 cent spread")
- Time to close (e.g., "<7 days until resolution")

### Example Extracted Blueprint

```python
StrategyBlueprint(
    name="Politics Arbitrage",
    strategy_type=StrategyType.ARBITRAGE,
    entry_rules=[
        Rule(
            condition="sum(YES price + NO price) < threshold",
            value=0.99,
            confidence=0.92,
            evidence_count=67,
            rule_type=RuleType.ENTRY_CONDITION,
        ),
        Rule(
            condition="market volume > threshold",
            value=10000.0,
            confidence=0.85,
            evidence_count=67,
            rule_type=RuleType.MARKET_FILTER,
        ),
    ],
    exit_rules=[
        Rule(
            condition="profit > threshold",
            value=0.02,  # 2%
            confidence=0.88,
            evidence_count=64,
            rule_type=RuleType.EXIT_CONDITION,
        ),
    ],
    sizing_rules=[
        Rule(
            condition="fixed size",
            value=750.0,
            confidence=0.91,
            evidence_count=67,
            rule_type=RuleType.SIZING_RULE,
        ),
    ],
    estimated_edge={"per_trade_pct": 1.8, "daily_pnl": 135},
    capital_required=15000.0,
    replicability_score=0.81,
    win_rate=0.96,
)
```

## Tips for Evaluating Discovered Strategies

### Red Flags (Avoid)

**Unsustainable win rates:**
- 99%+ over many trades (likely arbitrage already saturated)
- Perfect 100% (too good to be true, or insufficient sample)

**Decaying performance:**
- Win rate trending down
- Profit per trade declining
- Frequency decreasing (opportunity disappearing)

**Opaque strategy:**
- Can't identify clear pattern
- Rules extracted have low confidence (<0.6)
- Replicability score <0.4

**Luck indicators:**
- Small sample size (<30 trades)
- Recent trader (<14 days old)
- Single large win accounts for most profit
- No clear edge narrative

**Private edge:**
- Directional bets on obscure topics (insider info?)
- Extremely fast execution (bot advantage?)
- Unreplicable timing (manual front-running?)

### Green Flags (Investigate)

**Sustainable edge:**
- Win rate 85-95% (arbitrage/making range)
- OR win rate 60-75% (directional with skill)
- Consistent over 60+ days
- Not declining over time

**Clear strategy:**
- High confidence rules (>0.8)
- Replicability score >0.7
- Obvious edge narrative (arbitrage, category expert, etc.)

**Validated performance:**
- 100+ trades (statistical significance)
- Multiple months of history
- Survived different market conditions

**Replicable advantages:**
- Arbitrage (you can scan for same opportunities)
- Category expertise (you have similar knowledge)
- Systematic process (rules-based, not discretionary)

### Validation Checklist

Before replicating a strategy:

- [ ] Understand the edge source (why does this work?)
- [ ] Check current market conditions (still exploitable?)
- [ ] Verify capital requirements (can you deploy enough?)
- [ ] Test on paper (simulate trades without money)
- [ ] Start small (validate with real money, low risk)
- [ ] Monitor continuously (detect decay early)
- [ ] Adapt as needed (don't follow blindly)

## When to Copy-Trade vs Build Your Own

### Copy-Trade (Follow Directly)

**When:**
- High replicability score (>0.8)
- Arbitrage or market making strategy
- You lack domain expertise
- Small capital (<$5k)
- Want diversification (multiple strategies)

**How:**
- Monitor wallet continuously
- Replicate trades with small delay (<1 min)
- Scale position size to your capital
- Set stop-loss (in case strategy broke)

**Risks:**
- Execution delay (prices move)
- Strategy already crowded (edge compressed)
- Wallet owner adapts (you follow outdated moves)
- Over-reliance (don't understand why it works)

### Build Your Own (Adapt Strategy)

**When:**
- Directional or sniper strategy
- You have domain expertise
- Medium-large capital (>$10k)
- Want to learn, not just follow
- Replicability score <0.7

**How:**
- Extract strategy blueprint
- Understand rule rationale
- Code your own scanner/bot
- Test extensively on paper
- Deploy with risk management

**Advantages:**
- Customizable to your strengths
- No execution delay
- Deeper understanding
- Can improve on original

### Hybrid Approach (Best)

**Recommended:**
1. Start by copy-trading (validate strategy works)
2. Study trade patterns deeply (understand why)
3. Build your own implementation (automate)
4. Adapt and improve (add your edge)
5. Monitor original wallet (detect strategy drift)
6. Iterate continuously (markets evolve)

**Example:**
```
Week 1-2: Copy-trade wallet with arbitrage strategy
Week 3-4: Build scanner for arbitrage opportunities
Week 5-6: Test your scanner vs wallet's trades
Week 7+: Run your own scanner, reference wallet occasionally
```

## Advanced Topics

### Signal Combination

Multiple signals are stronger than one:

**Strong combination example:**
- PROFIT_SPIKE (sudden $5k day)
- WIN_RATE_ANOMALY (94% over 100 trades)
- RAPID_GROWTH ($400/day for 45 days)
- Conclusion: Very high confidence alpha signal

**Weak combination example:**
- PROFIT_SPIKE (one good day)
- 80% win rate (not exceptional)
- New wallet (12 days old)
- Conclusion: Possibly lucky, wait for more data

### Time Decay

Strategies degrade over time as markets adapt:

**Typical lifecycle:**
1. Discovery (wallet finds edge)
2. Exploitation (profits accelerate)
3. Detection (you find wallet)
4. Replication (you + others copy)
5. Saturation (edge compressed)
6. Death (no longer profitable)

**Timeframes:**
- Arbitrage: 1-3 months until saturated
- Market making: 3-6 months until spreads compress
- Directional: Variable (depends on info source)
- Sniper: 2-4 weeks until market adapts

**Solution:** Continuous scanning for NEW alpha, not old winners.

### Meta-Meta Strategy

The ultimate insight: find wallets that are also scanning for alpha.

**Detection:**
- Diversified across many strategies
- Rapidly shifts between approaches
- High trade frequency across categories
- Consistent edge despite changing meta

These are "strategy traders" - they adapt faster than others.

## Conclusion

The meta-strategy approach transforms prediction markets from "predict outcomes" to "predict predictors." By reverse-engineering successful wallets, you capture market-proven alpha without needing domain expertise in every category.

**Key takeaways:**
- Profit is hard to fake (filters noise)
- Strategies decay (scan continuously)
- Understanding > copying (adapt, don't blindly follow)
- Diversification (multiple edge sources)
- Risk management (test before deploying capital)

**Next steps:**
1. Run a scan for emerging traders
2. Analyze top signals
3. Deep dive on 2-3 wallets
4. Extract strategy blueprints
5. Paper trade for validation
6. Deploy small capital
7. Iterate based on results

Remember: past performance doesn't guarantee future results. Markets are adversarial. Your edge is someone else's loss. Trade responsibly.
