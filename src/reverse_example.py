"""
Example usage of the strategy reverse engineering module
"""

from datetime import datetime, timedelta
from reverse import (
    StrategyReverser,
    Trade,
    WalletProfile,
    WalletAnalysis,
    to_json,
    to_markdown,
    to_config,
    StrategyType
)


def example_binary_arbitrage():
    """
    Example: Reverse engineer a binary arbitrage strategy
    Similar to the Reference Wallet's original 15-min crypto strategy
    """
    print("=" * 80)
    print("EXAMPLE 1: Binary Arbitrage Strategy")
    print("=" * 80)
    print()

    # Create example wallet profile
    wallet = WalletProfile(
        address="0x8e9eedf20dfa70956d49f608a205e402d9df38e4",
        total_trades=517190,
        active_days=378,
        creation_date=datetime.now() - timedelta(days=421),
        total_pnl=8960000.0,
        current_balance=23578.0
    )

    # Create example trades (simulating binary arbitrage pattern)
    trades = []
    base_time = datetime.now() - timedelta(days=30)

    # Simulate 100 paired YES/NO arbitrage trades
    for i in range(100):
        trade_time = base_time + timedelta(minutes=i * 15)

        # YES purchase
        trades.append(Trade(
            timestamp=trade_time,
            market_id=f"btc_up_down_{i}",
            market_title=f"BTC UP in next 15 minutes (slot {i})",
            outcome="YES",
            side="BUY",
            shares=10000,
            price=0.48,
            value=4800.0,
            market_type="binary",
            metadata={"timeframe": "15min"}
        ))

        # NO purchase (paired, within 30 seconds)
        trades.append(Trade(
            timestamp=trade_time + timedelta(seconds=5),
            market_id=f"btc_up_down_{i}",
            market_title=f"BTC UP in next 15 minutes (slot {i})",
            outcome="NO",
            side="BUY",
            shares=10000,
            price=0.46,
            value=4600.0,
            market_type="binary",
            metadata={"timeframe": "15min"}
        ))

    # Create analysis
    analysis = WalletAnalysis(
        wallet=wallet,
        primary_markets=["crypto", "btc", "15min"],
        avg_trade_size=4700.0,
        avg_holding_period=timedelta(minutes=15),
        win_rate=0.98,
        peak_exposure=20000.0,
        trading_hours=list(range(24)),  # 24/7
        patterns={"paired_trades": True, "hedge_ratio": 1.0}
    )

    # Reverse engineer the strategy
    reverser = StrategyReverser(min_confidence=0.7, min_evidence=5)
    blueprint = reverser.reverse_engineer(wallet, trades, analysis)

    # Output results
    print("\n" + "=" * 80)
    print("STRATEGY BLUEPRINT")
    print("=" * 80)
    print()
    print(to_markdown(blueprint))

    print("\n" + "=" * 80)
    print("PSEUDOCODE")
    print("=" * 80)
    print()
    print(reverser.generate_pseudocode(blueprint))

    return blueprint


def example_multi_outcome_arbitrage():
    """
    Example: Reverse engineer a multi-outcome arbitrage strategy
    Similar to the Reference Wallet's current political arbitrage approach
    """
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Multi-Outcome Political Arbitrage Strategy")
    print("=" * 80)
    print()

    # Create example wallet profile
    wallet = WalletProfile(
        address="0x8e9eedf20dfa70956d49f608a205e402d9df38e4",
        total_trades=150,
        active_days=60,
        creation_date=datetime.now() - timedelta(days=90),
        total_pnl=430600.0,
        current_balance=99400.0
    )

    # Create example trades (simulating multi-outcome arbitrage)
    trades = []
    base_time = datetime.now() - timedelta(days=30)

    # South Korea election - 14 candidates
    candidates = [f"Candidate_{i}" for i in range(1, 15)]

    for i, candidate in enumerate(candidates):
        trades.append(Trade(
            timestamp=base_time + timedelta(minutes=i * 5),
            market_id="south_korea_president_2026",
            market_title="South Korea President 2026",
            outcome=candidate,
            side="BUY",
            shares=530000,
            price=0.0134,
            value=7102.0,  # 530000 * 0.0134
            market_type="multi",
            metadata={"event_type": "election", "total_outcomes": 14}
        ))

    # Romania election - 8 candidates (second market)
    romania_candidates = [f"Romania_Candidate_{i}" for i in range(1, 9)]

    for i, candidate in enumerate(romania_candidates):
        trades.append(Trade(
            timestamp=base_time + timedelta(hours=2, minutes=i * 5),
            market_id="romania_president_2026",
            market_title="Romania President 2026",
            outcome=candidate,
            side="BUY",
            shares=495000,
            price=0.021,
            value=10395.0,
            market_type="multi",
            metadata={"event_type": "election", "total_outcomes": 8}
        ))

    # Create analysis
    analysis = WalletAnalysis(
        wallet=wallet,
        primary_markets=["politics", "election", "president"],
        avg_trade_size=8748.0,
        avg_holding_period=timedelta(days=45),  # Long holding period
        win_rate=1.0,  # 100% - arbitrage is guaranteed
        peak_exposure=99400.0,
        trading_hours=[9, 10, 11, 12, 13, 14, 15, 16],  # Business hours
        patterns={"multi_outcome": True, "equal_shares": True}
    )

    # Reverse engineer the strategy
    reverser = StrategyReverser(min_confidence=0.7, min_evidence=3)
    blueprint = reverser.reverse_engineer(wallet, trades, analysis)

    # Output results
    print("\n" + "=" * 80)
    print("STRATEGY BLUEPRINT")
    print("=" * 80)
    print()
    print(to_markdown(blueprint))

    print("\n" + "=" * 80)
    print("CONFIGURATION FOR BOT")
    print("=" * 80)
    print()
    import json
    print(json.dumps(to_config(blueprint), indent=2))

    return blueprint


def example_directional_trading():
    """
    Example: Reverse engineer a directional trading strategy
    """
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Directional Trading Strategy")
    print("=" * 80)
    print()

    wallet = WalletProfile(
        address="0xdirectional_trader_example",
        total_trades=250,
        active_days=90,
        creation_date=datetime.now() - timedelta(days=100),
        total_pnl=15000.0,
        current_balance=65000.0
    )

    trades = []
    base_time = datetime.now() - timedelta(days=90)

    # Simulate directional trades with varying success
    for i in range(50):
        entry_time = base_time + timedelta(days=i * 1.5)

        # Buy YES on events (bullish stance)
        entry_price = 0.35 + (i % 10) * 0.03  # Varying entry prices
        trades.append(Trade(
            timestamp=entry_time,
            market_id=f"event_{i}",
            market_title=f"Will event {i} happen by deadline?",
            outcome="YES",
            side="BUY",
            shares=1000,
            price=entry_price,
            value=entry_price * 1000,
            market_type="binary"
        ))

        # Simulate exit (70% of positions)
        if i % 10 < 7:  # 70% of trades have exits
            exit_time = entry_time + timedelta(hours=12 + i % 48)
            exit_price = entry_price + 0.08 if i % 10 < 6 else entry_price - 0.05

            trades.append(Trade(
                timestamp=exit_time,
                market_id=f"event_{i}",
                market_title=f"Will event {i} happen by deadline?",
                outcome="YES",
                side="SELL",
                shares=1000,
                price=exit_price,
                value=exit_price * 1000,
                market_type="binary"
            ))

    analysis = WalletAnalysis(
        wallet=wallet,
        primary_markets=["politics", "sports", "crypto"],
        avg_trade_size=400.0,
        avg_holding_period=timedelta(hours=30),
        win_rate=0.68,
        peak_exposure=8000.0,
        trading_hours=[8, 9, 10, 11, 18, 19, 20, 21],
        patterns={"directional": True, "exit_discipline": True}
    )

    reverser = StrategyReverser(min_confidence=0.6, min_evidence=5)
    blueprint = reverser.reverse_engineer(wallet, trades, analysis)

    print("\n" + "=" * 80)
    print("STRATEGY BLUEPRINT")
    print("=" * 80)
    print()
    print(to_markdown(blueprint))

    return blueprint


if __name__ == "__main__":
    # Run all examples

    # Example 1: Binary Arbitrage (original Reference Wallet strategy)
    binary_blueprint = example_binary_arbitrage()

    # Example 2: Multi-Outcome Arbitrage (current Reference Wallet strategy)
    multi_blueprint = example_multi_outcome_arbitrage()

    # Example 3: Directional Trading
    directional_blueprint = example_directional_trading()

    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Binary Arbitrage Replicability: {binary_blueprint.replicability_score:.1%}")
    print(f"Multi-Outcome Arbitrage Replicability: {multi_blueprint.replicability_score:.1%}")
    print(f"Directional Trading Replicability: {directional_blueprint.replicability_score:.1%}")
    print()
    print("All examples completed successfully!")
