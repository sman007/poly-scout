# Usage Examples

Practical examples for common poly-scout operations.

## Table of Contents

1. [Basic Scan for Emerging Traders](#basic-scan-for-emerging-traders)
2. [Deep Analysis of Specific Wallet](#deep-analysis-of-specific-wallet)
3. [Continuous Monitoring Setup](#continuous-monitoring-setup)
4. [Generating Reports](#generating-reports)
5. [Interpreting Results](#interpreting-results)
6. [Advanced Workflows](#advanced-workflows)

## Basic Scan for Emerging Traders

### Example 1: Quick Scan with Defaults

Find new traders making significant profit:

```python
import asyncio
from src.scanner import WalletScanner

async def quick_scan():
    async with WalletScanner() as scanner:
        emerging = await scanner.scan_for_emerging_traders(
            min_profit=5000,      # At least $5k profit
            min_win_rate=0.85,    # 85%+ win rate
            max_age_days=60,      # Less than 60 days old
        )

        print(f"Found {len(emerging)} emerging traders\n")

        for i, trader in enumerate(emerging[:10], 1):
            print(f"{i}. {trader.username or trader.address[:10]}")
            print(f"   Profit: ${trader.profit:,.2f}")
            print(f"   Win Rate: {trader.win_rate:.1%}")
            print(f"   Age: {trader.age_days} days")
            print(f"   Trades: {trader.trade_count}")
            print()

asyncio.run(quick_scan())
```

**Output:**
```
Found 3 emerging traders

1. 0xabcd1234
   Profit: $12,450.00
   Win Rate: 92.3%
   Age: 28 days
   Trades: 65

2. 0x5678efgh
   Profit: $8,920.00
   Win Rate: 88.7%
   Age: 45 days
   Trades: 47
...
```

### Example 2: Aggressive Scan (High Thresholds)

Find only the most exceptional traders:

```python
async def aggressive_scan():
    async with WalletScanner() as scanner:
        elite = await scanner.scan_for_emerging_traders(
            min_profit=20000,     # $20k+ profit
            min_win_rate=0.93,    # 93%+ win rate
            max_age_days=45,      # Less than 45 days old
            leaderboard_limit=1000,  # Scan top 1000
        )

        print(f"Elite traders found: {len(elite)}")
        for trader in elite:
            print(f"  {trader.address}: ${trader.profit:,.0f} @ {trader.win_rate:.1%}")

asyncio.run(aggressive_scan())
```

### Example 3: Conservative Scan (Lower Thresholds)

Cast a wider net to find more candidates:

```python
async def conservative_scan():
    async with WalletScanner() as scanner:
        candidates = await scanner.scan_for_emerging_traders(
            min_profit=3000,      # $3k+ (lower bar)
            min_win_rate=0.80,    # 80%+ (more inclusive)
            max_age_days=90,      # 3 months old (longer history)
        )

        print(f"Found {len(candidates)} candidates")
        # Filter further with custom logic
        high_frequency = [t for t in candidates if t.trade_count > 100]
        print(f"High-frequency traders: {len(high_frequency)}")

asyncio.run(conservative_scan())
```

### Example 4: CLI Scan

Use the command-line interface:

```bash
# Basic scan
poly-scout scan

# Custom thresholds
poly-scout scan --min-profit 15000 --min-win-rate 0.92 --max-age-days 30

# Save results to JSON
poly-scout scan --output results.json --output-format json

# Limit results
poly-scout scan --limit 20
```

## Deep Analysis of Specific Wallet

### Example 5: Complete Wallet Analysis

Analyze a wallet's strategy, signals, and patterns:

```python
import asyncio
from src.scanner import WalletScanner
from src.analyzer import TradeAnalyzer
from src.signals import SignalDetector
from src.reverse import StrategyReverser

async def analyze_wallet(address: str):
    async with WalletScanner() as scanner:
        # Fetch wallet data
        print(f"Analyzing {address}...\n")
        profile = await scanner.fetch_wallet_stats(address)
        trades = await scanner.fetch_wallet_activity(address, limit=500)

        if not profile or not trades:
            print("Wallet not found or no trades")
            return

        # Basic stats
        print("=== Basic Stats ===")
        print(f"Username: {profile.username or 'Anonymous'}")
        print(f"Profit: ${profile.profit:,.2f}")
        print(f"Win Rate: {profile.win_rate:.1%}")
        print(f"Trades: {profile.trade_count}")
        print(f"Markets: {profile.markets_traded}")
        print(f"Age: {profile.age_days} days")
        print(f"Volume: ${profile.volume:,.2f}")
        print()

        # Strategy analysis
        print("=== Strategy Analysis ===")
        analyzer = TradeAnalyzer(min_trades=10)
        analysis = analyzer.analyze_wallet(trades)

        if analysis:
            print(f"Strategy Type: {analysis.strategy_type.value}")
            print(f"Confidence: {analysis.confidence:.1%}")
            print(f"Edge Estimate: {analysis.edge_estimate:.2f}%")
            print(f"Risk Score: {analysis.risk_score:.1f}/10")
            print(f"Replicability: {analysis.replicability_score:.1f}/10")
            print(f"Sharpe Ratio: {analysis.sharpe_ratio:.2f}")
            print(f"Maker/Taker: {analysis.maker_taker_ratio:.1%} maker")
            print()

            # Timing patterns
            print("=== Timing Patterns ===")
            print(f"Avg Hold Time: {analysis.timing.avg_hold_time/3600:.1f} hours")
            print(f"Trade Frequency: {analysis.timing.trade_frequency:.1f} per day")
            print(f"Burst Score: {analysis.timing.burst_trading_score:.2f}")
            print()

            # Position sizing
            print("=== Position Sizing ===")
            print(f"Avg Size: ${analysis.sizing.avg_size:,.2f}")
            print(f"Max Size: ${analysis.sizing.max_size:,.2f}")
            print(f"Pattern: {analysis.sizing.scaling_pattern}")
            print()

        # Signal detection
        print("=== Signals Detected ===")
        detector = SignalDetector()
        signals = detector.detect_all_signals(trades, profile)

        if signals:
            for signal in signals:
                print(f"[{signal.signal_type}]")
                print(f"  Strength: {signal.strength:.2f}")
                print(f"  {signal.description}")
                print()
        else:
            print("No anomalous signals detected")
            print()

        # Strategy reverse-engineering
        print("=== Strategy Blueprint ===")
        reverser = StrategyReverser(min_confidence=0.6)
        blueprint = reverser.reverse_engineer(trades, analysis)

        print(f"Strategy: {blueprint.name}")
        print(f"Type: {blueprint.strategy_type.value}")
        print(f"Capital Required: ${blueprint.capital_required:,.0f}")
        print(f"Replicability: {blueprint.replicability_score:.1%}")
        print(f"Win Rate: {blueprint.win_rate:.1%}")
        print()

        print("Entry Rules:")
        for rule in blueprint.entry_rules[:3]:
            print(f"  - {rule.condition}: {rule.value} (conf: {rule.confidence:.2f})")

        print("\nExit Rules:")
        for rule in blueprint.exit_rules[:3]:
            print(f"  - {rule.condition}: {rule.value} (conf: {rule.confidence:.2f})")

        print("\nSizing Rules:")
        for rule in blueprint.sizing_rules[:3]:
            print(f"  - {rule.condition}: {rule.value} (conf: {rule.confidence:.2f})")

# Run analysis
asyncio.run(analyze_wallet("0x1234567890abcdef..."))
```

### Example 6: CLI Analysis

```bash
# Basic analysis
poly-scout analyze 0x1234567890abcdef...

# Save to file
poly-scout analyze 0x1234... --output analysis.json --output-format json

# Add to watchlist
poly-scout analyze 0x1234... --add-to-watchlist
```

### Example 7: Batch Analysis

Analyze multiple wallets efficiently:

```python
async def batch_analysis(addresses: list):
    async with WalletScanner() as scanner:
        # Fetch all profiles concurrently
        profiles = await scanner.batch_fetch_wallet_stats(
            addresses,
            max_concurrent=5
        )

        # Analyze each
        analyzer = TradeAnalyzer()
        results = []

        for profile in profiles:
            trades = await scanner.fetch_wallet_activity(profile.address)
            analysis = analyzer.analyze_wallet(trades)
            results.append({
                'address': profile.address,
                'profit': profile.profit,
                'strategy': analysis.strategy_type.value if analysis else 'unknown',
                'edge': analysis.edge_estimate if analysis else 0,
            })

        # Sort by edge
        results.sort(key=lambda x: x['edge'], reverse=True)

        print("Top strategies by edge:")
        for r in results[:5]:
            print(f"{r['address'][:10]}: {r['strategy']} ({r['edge']:.2f}% edge)")

addresses = ["0x1234...", "0x5678...", "0x9abc..."]
asyncio.run(batch_analysis(addresses))
```

## Continuous Monitoring Setup

### Example 8: Watchlist Monitor

Monitor saved wallets for changes:

```python
import asyncio
import json
from pathlib import Path
from datetime import datetime
from src.scanner import WalletScanner

async def monitor_watchlist(interval_seconds: int = 300):
    """Monitor watchlist and alert on significant changes."""

    watchlist_path = Path("./data/watchlist.json")

    # Load watchlist
    if not watchlist_path.exists():
        print("Watchlist not found")
        return

    with open(watchlist_path) as f:
        watchlist = json.load(f)

    addresses = [w['address'] for w in watchlist]
    print(f"Monitoring {len(addresses)} wallets every {interval_seconds}s")
    print("Press Ctrl+C to stop\n")

    # Store previous state
    previous_state = {}

    async with WalletScanner() as scanner:
        while True:
            try:
                print(f"[{datetime.now():%H:%M:%S}] Checking wallets...")

                profiles = await scanner.batch_fetch_wallet_stats(
                    addresses,
                    max_concurrent=5
                )

                for profile in profiles:
                    addr = profile.address[:10]
                    prev = previous_state.get(profile.address)

                    if prev:
                        # Check for significant changes
                        profit_delta = profile.profit - prev['profit']
                        trade_delta = profile.trade_count - prev['trades']

                        if profit_delta > 1000:  # $1k+ gain
                            print(f"  [ALERT] {addr} +${profit_delta:,.0f} profit")

                        if trade_delta > 10:  # 10+ new trades
                            print(f"  [ALERT] {addr} +{trade_delta} trades")

                    # Update state
                    previous_state[profile.address] = {
                        'profit': profile.profit,
                        'trades': profile.trade_count,
                    }

                print(f"  All clear. Next check in {interval_seconds}s\n")
                await asyncio.sleep(interval_seconds)

            except KeyboardInterrupt:
                print("\nMonitoring stopped")
                break
            except Exception as e:
                print(f"  Error: {e}")
                await asyncio.sleep(interval_seconds)

asyncio.run(monitor_watchlist(interval_seconds=300))
```

### Example 9: CLI Watch Mode

```bash
# Monitor every 60 seconds
poly-scout watch --interval 60

# Alert on $10k+ moves
poly-scout watch --min-profit 10000

# Watchlist only
poly-scout watch --watchlist-only
```

### Example 10: Continuous Scan

Repeatedly scan for new emerging traders:

```python
async def continuous_scan(interval_minutes: int = 60):
    """Scan for new emerging traders every N minutes."""

    print(f"Scanning every {interval_minutes} minutes")
    print("Press Ctrl+C to stop\n")

    seen_addresses = set()

    async with WalletScanner() as scanner:
        while True:
            try:
                print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Scanning...")

                emerging = await scanner.scan_for_emerging_traders(
                    min_profit=8000,
                    min_win_rate=0.88,
                    max_age_days=45,
                )

                # Find new traders (not seen before)
                new_traders = [
                    t for t in emerging
                    if t.address not in seen_addresses
                ]

                if new_traders:
                    print(f"Found {len(new_traders)} NEW emerging traders:")
                    for trader in new_traders:
                        print(f"  {trader.address[:10]}: ${trader.profit:,.0f}")
                        seen_addresses.add(trader.address)
                else:
                    print("No new traders found")

                print(f"Next scan in {interval_minutes} minutes\n")
                await asyncio.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                print("\nScanning stopped")
                break
            except Exception as e:
                print(f"Error: {e}\n")
                await asyncio.sleep(interval_minutes * 60)

asyncio.run(continuous_scan(interval_minutes=60))
```

## Generating Reports

### Example 11: HTML Report

Generate a formatted HTML report:

```python
async def generate_html_report(output_path: str = "report.html"):
    """Generate comprehensive HTML report."""

    async with WalletScanner() as scanner:
        emerging = await scanner.scan_for_emerging_traders()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>poly-scout Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #2c3e50; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #3498db; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .profit {{ color: #27ae60; font-weight: bold; }}
                .win-rate {{ color: #2980b9; }}
            </style>
        </head>
        <body>
            <h1>Emerging Traders Report</h1>
            <p>Generated: {datetime.now():%Y-%m-%d %H:%M:%S}</p>
            <p>Traders found: {len(emerging)}</p>

            <table>
                <tr>
                    <th>Rank</th>
                    <th>Address</th>
                    <th>Profit</th>
                    <th>Win Rate</th>
                    <th>Trades</th>
                    <th>Age (days)</th>
                </tr>
        """

        for i, trader in enumerate(emerging, 1):
            html += f"""
                <tr>
                    <td>{i}</td>
                    <td><code>{trader.address[:16]}...</code></td>
                    <td class="profit">${trader.profit:,.2f}</td>
                    <td class="win-rate">{trader.win_rate:.1%}</td>
                    <td>{trader.trade_count}</td>
                    <td>{trader.age_days}</td>
                </tr>
            """

        html += """
            </table>
        </body>
        </html>
        """

        with open(output_path, 'w') as f:
            f.write(html)

        print(f"Report saved to {output_path}")

asyncio.run(generate_html_report())
```

### Example 12: JSON Export

Export data for external analysis:

```python
async def export_to_json(output_path: str = "export.json"):
    """Export emerging traders to JSON."""

    async with WalletScanner() as scanner:
        emerging = await scanner.scan_for_emerging_traders()

        # Convert to serializable format
        data = {
            'timestamp': datetime.now().isoformat(),
            'count': len(emerging),
            'traders': [trader.to_dict() for trader in emerging],
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(emerging)} traders to {output_path}")

asyncio.run(export_to_json())
```

### Example 13: CLI Report

```bash
# Table format (default)
poly-scout report

# Detailed statistics
poly-scout report --detailed

# Save to file
poly-scout report --output report.html --output-format html

# JSON export
poly-scout report --output report.json --output-format json
```

## Interpreting Results

### Example 14: Strategy Classification

Understanding strategy types:

```python
from src.analyzer import StrategyType

def interpret_strategy(strategy_type: StrategyType, analysis):
    """Provide human-readable interpretation."""

    interpretations = {
        StrategyType.ARBITRAGE: """
        ARBITRAGE Strategy Detected:
        - Exploits price discrepancies between YES/NO outcomes
        - Very high win rate (95%+) with low variance
        - Short holding periods (minutes to hours)
        - Requires significant capital to scale
        - Highly replicable if you can find same opportunities
        """,

        StrategyType.MARKET_MAKING: """
        MARKET MAKING Strategy Detected:
        - Provides liquidity by posting two-sided orders
        - Captures bid-ask spread
        - High maker ratio (70%+)
        - Requires inventory management and speed
        - Moderately replicable with infrastructure
        """,

        StrategyType.DIRECTIONAL: """
        DIRECTIONAL Strategy Detected:
        - Takes positions based on outcome predictions
        - Concentrated bets on few markets
        - Win rate 60-75% (skill-based)
        - Requires domain expertise or information edge
        - Low replicability (hard to copy analysis)
        """,

        StrategyType.SNIPER: """
        SNIPER Strategy Detected:
        - Event-triggered rapid trading
        - Burst activity around news/catalysts
        - Many markets, fast execution
        - Requires speed and decision-making
        - Low replicability (need same advantages)
        """,
    }

    interpretation = interpretations.get(
        strategy_type,
        "UNKNOWN: Cannot classify with confidence"
    )

    print(interpretation)
    print(f"\nConfidence: {analysis.confidence:.1%}")
    print(f"Edge Estimate: {analysis.edge_estimate:.2f}%")
    print(f"Risk Score: {analysis.risk_score:.1f}/10")
    print(f"Replicability: {analysis.replicability_score:.1f}/10")

# Usage
# interpret_strategy(analysis.strategy_type, analysis)
```

### Example 15: Signal Strength Interpretation

Understanding signal strengths:

```python
def interpret_signal_strength(signal):
    """Interpret signal strength levels."""

    if signal.strength >= 0.8:
        level = "VERY STRONG"
        action = "Investigate immediately"
    elif signal.strength >= 0.6:
        level = "STRONG"
        action = "High priority investigation"
    elif signal.strength >= 0.4:
        level = "MODERATE"
        action = "Monitor and collect more data"
    else:
        level = "WEAK"
        action = "Note but don't act yet"

    print(f"[{signal.signal_type}]")
    print(f"Strength: {signal.strength:.2f} ({level})")
    print(f"Action: {action}")
    print(f"Evidence: {signal.evidence}")
    print()

# Usage
# for signal in signals:
#     interpret_signal_strength(signal)
```

### Example 16: Risk Assessment

Evaluate whether to replicate a strategy:

```python
def assess_replication_risk(blueprint, analysis):
    """Assess risk of replicating a strategy."""

    print("=== Replication Risk Assessment ===\n")

    # Check replicability score
    if blueprint.replicability_score < 0.5:
        print("[HIGH RISK] Replicability score < 0.5")
        print("  Strategy may require unique advantages")
        print("  Consider: private info, speed, capital\n")
    elif blueprint.replicability_score < 0.7:
        print("[MEDIUM RISK] Replicability score 0.5-0.7")
        print("  Requires infrastructure or expertise")
        print("  Test thoroughly before deploying\n")
    else:
        print("[LOW RISK] Replicability score >= 0.7")
        print("  Strategy appears systematic and replicable\n")

    # Check capital requirements
    if blueprint.capital_required > 50000:
        print(f"[WARNING] High capital required: ${blueprint.capital_required:,.0f}")
        print("  May not be suitable for small accounts\n")

    # Check risk score
    if analysis.risk_score > 7:
        print(f"[HIGH RISK] Risk score: {analysis.risk_score:.1f}/10")
        print("  Strategy exhibits high risk characteristics")
        print("  Use proper position sizing and risk management\n")

    # Check win rate sustainability
    if analysis.win_rate > 0.95:
        print("[CAUTION] Very high win rate (>95%)")
        print("  Likely arbitrage - opportunity may be saturated")
        print("  Edge may compress quickly\n")

    # Check sample size
    if analysis.timing.trade_frequency * 30 < 50:  # <50 trades in 30 days
        print("[WARNING] Low sample size")
        print("  Not enough trades for statistical confidence")
        print("  Collect more data before replicating\n")

    # Overall recommendation
    print("=== Recommendation ===")
    risk_factors = sum([
        blueprint.replicability_score < 0.6,
        blueprint.capital_required > 50000,
        analysis.risk_score > 7,
        analysis.win_rate > 0.97,
        analysis.timing.trade_frequency * 30 < 50,
    ])

    if risk_factors == 0:
        print("LOW RISK: Consider replicating with small capital")
    elif risk_factors <= 2:
        print("MEDIUM RISK: Paper trade first, then deploy small")
    else:
        print("HIGH RISK: Avoid replication or deep research first")

# Usage
# assess_replication_risk(blueprint, analysis)
```

## Advanced Workflows

### Example 17: Full Pipeline

Complete workflow from scan to replication decision:

```python
async def full_pipeline():
    """Complete analysis pipeline."""

    print("=== STAGE 1: SCAN ===\n")
    async with WalletScanner() as scanner:
        emerging = await scanner.scan_for_emerging_traders(
            min_profit=10000,
            min_win_rate=0.90,
            max_age_days=45,
        )
        print(f"Found {len(emerging)} emerging traders\n")

    print("=== STAGE 2: SIGNAL DETECTION ===\n")
    detector = SignalDetector()
    high_signal_wallets = []

    for trader in emerging:
        trades = await scanner.fetch_wallet_activity(trader.address)
        signals = detector.detect_all_signals(trades, trader)
        strong_signals = [s for s in signals if s.strength > 0.7]

        if strong_signals:
            high_signal_wallets.append({
                'trader': trader,
                'signals': strong_signals,
                'trades': trades,
            })

    print(f"Found {len(high_signal_wallets)} wallets with strong signals\n")

    print("=== STAGE 3: STRATEGY ANALYSIS ===\n")
    analyzer = TradeAnalyzer()
    reverser = StrategyReverser()

    candidates = []
    for item in high_signal_wallets:
        analysis = analyzer.analyze_wallet(item['trades'])
        blueprint = reverser.reverse_engineer(item['trades'], analysis)

        if blueprint.replicability_score > 0.7:
            candidates.append({
                'trader': item['trader'],
                'analysis': analysis,
                'blueprint': blueprint,
                'signals': item['signals'],
            })

    print(f"Found {len(candidates)} replicable strategies\n")

    print("=== STAGE 4: RANKING ===\n")
    # Sort by combined score
    for c in candidates:
        c['score'] = (
            c['blueprint'].replicability_score * 0.4 +
            c['analysis'].confidence * 0.3 +
            (c['analysis'].edge_estimate / 10) * 0.3
        )

    candidates.sort(key=lambda x: x['score'], reverse=True)

    print("Top 3 strategies to investigate:\n")
    for i, c in enumerate(candidates[:3], 1):
        print(f"{i}. {c['trader'].address[:10]}")
        print(f"   Strategy: {c['blueprint'].strategy_type.value}")
        print(f"   Edge: {c['analysis'].edge_estimate:.2f}%")
        print(f"   Replicability: {c['blueprint'].replicability_score:.1%}")
        print(f"   Score: {c['score']:.3f}")
        print()

    print("=== STAGE 5: ACTION ITEMS ===\n")
    for i, c in enumerate(candidates[:3], 1):
        print(f"Strategy {i}:")
        print(f"  1. Paper trade for 7 days")
        print(f"  2. Monitor wallet for changes")
        print(f"  3. Deploy ${c['blueprint'].capital_required * 0.1:,.0f} (10% of requirement)")
        print(f"  4. Scale if successful")
        print()

asyncio.run(full_pipeline())
```

### Example 18: Strategy Comparison

Compare multiple strategies side by side:

```python
async def compare_strategies(addresses: list):
    """Compare strategies from multiple wallets."""

    async with WalletScanner() as scanner:
        analyzer = TradeAnalyzer()

        comparisons = []
        for addr in addresses:
            trades = await scanner.fetch_wallet_activity(addr)
            analysis = analyzer.analyze_wallet(trades)

            if analysis:
                comparisons.append({
                    'address': addr[:10],
                    'strategy': analysis.strategy_type.value,
                    'edge': analysis.edge_estimate,
                    'win_rate': analysis.win_rate,
                    'risk': analysis.risk_score,
                    'replicability': analysis.replicability_score,
                })

        # Print comparison table
        print(f"{'Address':<12} {'Strategy':<15} {'Edge':<8} {'Win Rate':<10} {'Risk':<8} {'Replic':<8}")
        print("-" * 75)

        for c in comparisons:
            print(f"{c['address']:<12} {c['strategy']:<15} {c['edge']:>6.2f}% {c['win_rate']:>8.1%} {c['risk']:>6.1f} {c['replicability']:>6.1%}")

addresses = ["0x1234...", "0x5678...", "0x9abc..."]
asyncio.run(compare_strategies(addresses))
```

### Example 19: Automated Watchlist Management

Automatically add/remove wallets from watchlist:

```python
async def auto_manage_watchlist():
    """Automatically update watchlist based on performance."""

    watchlist_path = Path("./data/watchlist.json")

    async with WalletScanner() as scanner:
        # Scan for new candidates
        emerging = await scanner.scan_for_emerging_traders()

        # Load existing watchlist
        if watchlist_path.exists():
            with open(watchlist_path) as f:
                watchlist = json.load(f)
        else:
            watchlist = []

        existing_addresses = {w['address'] for w in watchlist}

        # Add new high-performers
        added = 0
        for trader in emerging[:10]:  # Top 10
            if trader.address not in existing_addresses:
                watchlist.append({
                    'address': trader.address,
                    'added_at': datetime.now().isoformat(),
                    'profit_at_add': trader.profit,
                    'reason': 'emerging_trader_scan',
                })
                added += 1

        # Remove underperformers
        removed = 0
        updated_watchlist = []

        for item in watchlist:
            profile = await scanner.fetch_wallet_stats(item['address'])

            if profile:
                # Keep if still profitable
                profit_delta = profile.profit - item.get('profit_at_add', 0)
                if profit_delta >= 0:  # Still gaining
                    updated_watchlist.append(item)
                else:
                    removed += 1
                    print(f"Removed {item['address'][:10]} (declining profit)")
            else:
                removed += 1

        # Save updated watchlist
        with open(watchlist_path, 'w') as f:
            json.dump(updated_watchlist, f, indent=2)

        print(f"\nWatchlist updated:")
        print(f"  Added: {added}")
        print(f"  Removed: {removed}")
        print(f"  Total: {len(updated_watchlist)}")

asyncio.run(auto_manage_watchlist())
```

### Example 20: Performance Tracking

Track strategy performance over time:

```python
async def track_performance(address: str, days: int = 30):
    """Track wallet performance over time."""

    async with WalletScanner() as scanner:
        profile = await scanner.fetch_wallet_stats(address)
        trades = await scanner.fetch_wallet_activity(address, limit=1000)

        # Group by day
        daily_stats = defaultdict(lambda: {'profit': 0, 'trades': 0})

        for trade in trades:
            day = trade.timestamp.date()
            daily_stats[day]['profit'] += trade.profit
            daily_stats[day]['trades'] += 1

        # Sort by date
        sorted_days = sorted(daily_stats.keys())[-days:]

        print(f"Performance tracking for {address[:10]} (last {days} days)\n")
        print(f"{'Date':<12} {'Profit':<12} {'Trades':<8} {'Cumulative':<12}")
        print("-" * 50)

        cumulative = 0
        for day in sorted_days:
            stats = daily_stats[day]
            cumulative += stats['profit']
            print(f"{day} ${stats['profit']:>9.2f} {stats['trades']:>6} ${cumulative:>9.2f}")

        # Calculate trends
        recent_profit = sum(daily_stats[d]['profit'] for d in sorted_days[-7:])
        avg_daily = recent_profit / 7

        print(f"\nLast 7 days: ${recent_profit:,.2f}")
        print(f"Avg daily: ${avg_daily:,.2f}")

asyncio.run(track_performance("0x1234...", days=30))
```

## Summary

These examples cover the most common poly-scout use cases:

1. **Scanning**: Find emerging traders with various criteria
2. **Analysis**: Deep dive into specific wallets
3. **Monitoring**: Track wallets continuously
4. **Reporting**: Generate formatted reports
5. **Interpretation**: Understand results and make decisions
6. **Advanced**: Full pipelines and automation

Combine these patterns to build custom workflows tailored to your needs.

For more details, see:
- [API Reference](API.md) - Complete API documentation
- [Strategy Guide](STRATEGY.md) - Understanding strategies and signals
- [README](../README.md) - Installation and quick start
