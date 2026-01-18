"""
Example usage of the signals module.

This demonstrates how to use the SignalDetector to identify wallets with potential edge.
"""

from datetime import datetime, timedelta
from signals import SignalDetector, Signal, Trade, WalletProfile


def example_usage():
    """Demonstrate signal detection on example wallet data."""

    # Create example wallet profile
    wallet = WalletProfile(
        address="0xabc123...",
        first_seen=datetime.utcnow() - timedelta(days=45),
        total_profit=15000.0,
        total_trades=150,
        win_rate=0.92,
        avg_trade_size=500.0,
        markets_traded=25
    )

    # Create example trades (simulating a profitable trader)
    trades = []
    base_time = datetime.utcnow() - timedelta(days=45)

    # First month: moderate activity
    for i in range(50):
        trades.append(Trade(
            timestamp=base_time + timedelta(days=i * 0.6),
            profit=100.0 if i % 10 != 0 else -50.0,  # 90% win rate
            outcome="win" if i % 10 != 0 else "loss",
            market_id=f"market_{i % 10}",
            market_category="politics" if i % 2 == 0 else "sports",
            amount=500.0
        ))

    # Last 7 days: profit spike
    for i in range(100):
        trades.append(Trade(
            timestamp=datetime.utcnow() - timedelta(days=7 - i * 0.07),
            profit=200.0 if i % 10 != 0 else -30.0,
            outcome="win" if i % 10 != 0 else "loss",
            market_id=f"market_{i % 5}",
            market_category="politics",  # Concentrated in politics
            amount=600.0
        ))

    # Initialize detector and run all signal checks
    detector = SignalDetector()
    signals = detector.detect_all_signals(wallet, trades)

    # Display results
    print(f"Analyzing wallet: {wallet.address}")
    print(f"Total profit: ${wallet.total_profit:.2f}")
    print(f"Win rate: {wallet.win_rate * 100:.1f}%")
    print(f"Total trades: {wallet.total_trades}")
    print(f"\nDetected {len(signals)} signals:\n")

    for signal in signals:
        print(f"[{signal.signal_type}] Strength: {signal.strength:.2f}")
        print(f"  {signal.description}")
        print(f"  Evidence: {signal.evidence}")
        print()

    # Calculate composite alpha score
    alpha_score = detector.calculate_alpha_score(signals)
    print(f"Composite Alpha Score: {alpha_score:.3f}")

    if alpha_score >= 0.7:
        print("VERDICT: Strong evidence of edge - HIGH PRIORITY WATCH")
    elif alpha_score >= 0.5:
        print("VERDICT: Moderate evidence of edge - worth monitoring")
    elif alpha_score >= 0.3:
        print("VERDICT: Some evidence of edge - keep on watchlist")
    else:
        print("VERDICT: Insufficient evidence of edge")


def test_individual_signals():
    """Test each signal type individually."""

    detector = SignalDetector()

    # Test 1: Win Rate Anomaly
    print("\n=== Test 1: Win Rate Anomaly ===")
    signal = detector.win_rate_anomaly_signal(
        win_rate=0.93,
        trade_count=200
    )
    if signal:
        print(f"Detected: {signal.description}")
        print(f"Strength: {signal.strength:.2f}")
        print(f"P-value: {signal.evidence['p_value']:.2e}")

    # Test 2: New Wallet Success
    print("\n=== Test 2: New Wallet Success ===")
    signal = detector.new_wallet_success_signal(
        first_seen=datetime.utcnow() - timedelta(days=30),
        profit=12000.0
    )
    if signal:
        print(f"Detected: {signal.description}")
        print(f"Strength: {signal.strength:.2f}")

    # Test 3: Market Specialist
    print("\n=== Test 3: Market Concentration ===")
    market_dist = {
        "politics": 0.85,
        "sports": 0.10,
        "crypto": 0.05
    }
    signal = detector.concentration_signal(market_dist)
    if signal:
        print(f"Detected: {signal.description}")
        print(f"Strength: {signal.strength:.2f}")


if __name__ == "__main__":
    print("Signal Detection Example\n")
    print("=" * 60)

    test_individual_signals()

    print("\n" + "=" * 60)
    print("\nFull Analysis Example:")
    print("=" * 60)

    example_usage()
