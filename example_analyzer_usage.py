"""
Example usage of the TradeAnalyzer module.

Demonstrates how to analyze trading patterns from Polymarket wallets.
"""

from datetime import datetime, timedelta
from src.analyzer import Trade, TradeAnalyzer, StrategyType


def create_sample_arbitrage_trades() -> list[Trade]:
    """Create sample trades that look like arbitrage strategy."""
    trades = []
    base_time = datetime(2024, 1, 1, 10, 0, 0)

    for i in range(50):
        # Paired YES/NO trades in same market (arbitrage pattern)
        market_id = f"market_{i % 10}"
        timestamp = base_time + timedelta(hours=i * 2)

        # YES trade
        trades.append(Trade(
            timestamp=timestamp,
            market_id=market_id,
            side='YES',
            size=1000.0,
            price=0.48,
            is_maker=True,
            realized_pnl=15.0,
            exit_timestamp=timestamp + timedelta(minutes=30)
        ))

        # NO trade (paired)
        trades.append(Trade(
            timestamp=timestamp + timedelta(minutes=1),
            market_id=market_id,
            side='NO',
            size=1000.0,
            price=0.51,
            is_maker=True,
            realized_pnl=10.0,
            exit_timestamp=timestamp + timedelta(minutes=31)
        ))

    return trades


def create_sample_directional_trades() -> list[Trade]:
    """Create sample trades that look like directional strategy."""
    trades = []
    base_time = datetime(2024, 1, 1, 10, 0, 0)

    for i in range(30):
        # Concentrated bets on few markets
        market_id = f"market_{i % 3}"  # Only 3 markets
        timestamp = base_time + timedelta(days=i)

        # Larger, more variable position sizes
        size = 500.0 + (i * 100) if i % 3 == 0 else 1000.0

        # Variable PnL (not all winners)
        pnl = 100.0 if i % 4 != 0 else -50.0

        trades.append(Trade(
            timestamp=timestamp,
            market_id=market_id,
            side='YES' if i % 2 == 0 else 'NO',
            size=size,
            price=0.65,
            is_maker=False,  # Taker orders
            realized_pnl=pnl,
            exit_timestamp=timestamp + timedelta(days=2)
        ))

    return trades


def create_sample_sniper_trades() -> list[Trade]:
    """Create sample trades that look like sniper strategy."""
    trades = []
    base_time = datetime(2024, 1, 1, 9, 0, 0)

    for i in range(40):
        # Burst trading at market open (9 AM)
        day_offset = i // 5
        trade_in_burst = i % 5

        timestamp = base_time + timedelta(days=day_offset, minutes=trade_in_burst * 2)

        # Many different markets
        market_id = f"market_{i}"

        trades.append(Trade(
            timestamp=timestamp,
            market_id=market_id,
            side='YES',
            size=500.0,
            price=0.70,
            is_maker=False,
            realized_pnl=25.0,
            exit_timestamp=timestamp + timedelta(hours=3)
        ))

    return trades


def main():
    """Run analysis examples."""
    analyzer = TradeAnalyzer(min_trades=10)

    print("=" * 80)
    print("POLYMARKET TRADE ANALYZER - Example Usage")
    print("=" * 80)

    # Analyze arbitrage strategy
    print("\n1. ARBITRAGE STRATEGY ANALYSIS")
    print("-" * 80)
    arb_trades = create_sample_arbitrage_trades()
    arb_analysis = analyzer.analyze_wallet(arb_trades)

    print(f"Strategy Type: {arb_analysis.strategy_type.value}")
    print(f"Confidence: {arb_analysis.confidence:.2%}")
    print(f"Edge Estimate: {arb_analysis.edge_estimate:.2f}%")
    print(f"Win Rate: {arb_analysis.win_rate:.2%}")
    print(f"Maker/Taker Ratio: {arb_analysis.maker_taker_ratio:.2%}")
    print(f"Risk Score: {arb_analysis.risk_score:.1f}/10")
    print(f"Replicability Score: {arb_analysis.replicability_score:.1f}/10")
    print(f"Markets Traded: {arb_analysis.markets}")
    print(f"Avg Hold Time: {arb_analysis.timing.avg_hold_time / 3600:.1f} hours")
    print(f"Total PnL: ${arb_analysis.total_pnl:,.2f}")
    print(f"Sharpe Ratio: {arb_analysis.sharpe_ratio:.2f}")

    # Analyze directional strategy
    print("\n2. DIRECTIONAL STRATEGY ANALYSIS")
    print("-" * 80)
    dir_trades = create_sample_directional_trades()
    dir_analysis = analyzer.analyze_wallet(dir_trades)

    print(f"Strategy Type: {dir_analysis.strategy_type.value}")
    print(f"Confidence: {dir_analysis.confidence:.2%}")
    print(f"Edge Estimate: {dir_analysis.edge_estimate:.2f}%")
    print(f"Win Rate: {dir_analysis.win_rate:.2%}")
    print(f"Maker/Taker Ratio: {dir_analysis.maker_taker_ratio:.2%}")
    print(f"Risk Score: {dir_analysis.risk_score:.1f}/10")
    print(f"Replicability Score: {dir_analysis.replicability_score:.1f}/10")
    print(f"Markets Traded: {dir_analysis.markets}")
    print(f"Position Sizing Pattern: {dir_analysis.sizing.scaling_pattern}")
    print(f"Total PnL: ${dir_analysis.total_pnl:,.2f}")

    # Analyze sniper strategy
    print("\n3. SNIPER STRATEGY ANALYSIS")
    print("-" * 80)
    sniper_trades = create_sample_sniper_trades()
    sniper_analysis = analyzer.analyze_wallet(sniper_trades)

    print(f"Strategy Type: {sniper_analysis.strategy_type.value}")
    print(f"Confidence: {sniper_analysis.confidence:.2%}")
    print(f"Edge Estimate: {sniper_analysis.edge_estimate:.2f}%")
    print(f"Win Rate: {sniper_analysis.win_rate:.2%}")
    print(f"Burst Trading Score: {sniper_analysis.timing.burst_trading_score:.2f}")
    print(f"Risk Score: {sniper_analysis.risk_score:.1f}/10")
    print(f"Replicability Score: {sniper_analysis.replicability_score:.1f}/10")
    print(f"Markets Traded: {sniper_analysis.markets}")
    print(f"Trade Frequency: {sniper_analysis.timing.trade_frequency:.1f} trades/day")

    # Calculate profit acceleration
    print("\n4. PROFIT ACCELERATION ANALYSIS")
    print("-" * 80)
    arb_accel = analyzer.calculate_profit_acceleration(arb_trades)
    dir_accel = analyzer.calculate_profit_acceleration(dir_trades)
    sniper_accel = analyzer.calculate_profit_acceleration(sniper_trades)

    print(f"Arbitrage acceleration: {arb_accel:.3f}x")
    print(f"Directional acceleration: {dir_accel:.3f}x")
    print(f"Sniper acceleration: {sniper_accel:.3f}x")
    print("\n(>1.0 = profits accelerating, <1.0 = profits decelerating)")

    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
