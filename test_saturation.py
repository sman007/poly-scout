"""
Test script for saturation analysis features.
Demonstrates the new find_similar_wallets() and saturation tracking functions.
"""

import asyncio
import json
from src.daemon import (
    load_saturation_history,
    save_saturation_history,
    get_saturation_trend,
    update_saturation_snapshot,
    log
)


async def test_saturation_tracking():
    """Test saturation history tracking functions."""

    print("\n" + "="*60)
    print("TESTING SATURATION TRACKING")
    print("="*60 + "\n")

    # Test 1: Update saturation snapshot
    print("Test 1: Updating saturation snapshot...")
    strategy_key = "BINANCE_SIGNAL_BTC"
    wallet_count = 5
    total_capital = 250000.0

    trend = update_saturation_snapshot(strategy_key, wallet_count, total_capital)
    print(f"  Result: Trend = {trend}\n")

    # Test 2: Load history
    print("Test 2: Loading saturation history...")
    history = load_saturation_history()
    print(f"  Loaded {len(history)} strategies")

    if strategy_key in history:
        dates = sorted(history[strategy_key].keys(), reverse=True)
        print(f"  {strategy_key} has {len(dates)} data points:")
        for date in dates[:3]:  # Show first 3
            data = history[strategy_key][date]
            print(f"    - {date}: {data['wallets']} wallets, ${data['capital']:,.0f}")
    print()

    # Test 3: Get trend
    print("Test 3: Calculating trend...")
    trend = get_saturation_trend(strategy_key, history)
    print(f"  Trend for {strategy_key}: {trend}\n")

    # Test 4: Simulate multiple days
    print("Test 4: Simulating 10 days of data...")
    from datetime import datetime, timedelta

    history = load_saturation_history()
    if strategy_key not in history:
        history[strategy_key] = {}

    # Create 10 days of fake data showing increasing saturation
    base_date = datetime.now() - timedelta(days=9)
    for i in range(10):
        date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        history[strategy_key][date] = {
            "wallets": 3 + i,  # Increasing from 3 to 12
            "capital": 100000 + (i * 20000)  # Increasing capital
        }

    save_saturation_history(history)

    # Check trend
    trend = get_saturation_trend(strategy_key, history)
    print(f"  After 10 days of increasing wallets (3 -> 12): trend = {trend}")
    status = "PASS" if trend == "increasing" else "FAIL"
    print(f"  Expected: 'increasing' - {status}\n")

    print("="*60)
    print("SATURATION TRACKING TESTS COMPLETE")
    print("="*60 + "\n")


async def test_find_similar_wallets():
    """Test find_similar_wallets() method."""

    print("\n" + "="*60)
    print("TESTING FIND_SIMILAR_WALLETS")
    print("="*60 + "\n")

    from src.scanner import WalletScanner

    # Create sample reference parameters
    reference_params = {
        "markets": ["btc-up-or-down-15min", "eth-up-or-down-15min", "sol-up-or-down-15min"],
        "timing_pattern": "at_resolution",
        "entry_price_ranges": {
            "btc-up-or-down-15min": 0.48,
            "eth-up-or-down-15min": 0.49,
            "sol-up-or-down-15min": 0.47
        },
        "likely_strategy": "BINANCE_SIGNAL"
    }

    print("Reference strategy parameters:")
    print(f"  Markets: {', '.join(reference_params['markets'])}")
    print(f"  Strategy: {reference_params['likely_strategy']}")
    print(f"  Entry prices: {reference_params['entry_price_ranges']}\n")

    print("Scanning for similar wallets (limited to 20 for testing)...\n")

    async with WalletScanner() as scanner:
        result = await scanner.find_similar_wallets(reference_params, limit=20)

        print("Results:")
        print(f"  Similar wallets found: {result['wallet_count']}")
        print(f"  Estimated total capital: ${result['total_capital']:,.0f}")
        print(f"  Trend: {result['trend']}")

        if result['wallet_count'] > 0 and 'wallet_details' in result:
            print(f"\n  Top 5 similar wallets:")
            for i, wallet in enumerate(result['wallet_details'][:5], 1):
                print(f"    {i}. {wallet['address'][:16]}...")
                print(f"       Market overlap: {wallet['market_overlap']:.1%}")
                print(f"       Price similarity: {wallet['price_similarity']:.1%}")
                print(f"       Est. capital: ${wallet['estimated_capital']:,.0f}")

        if 'error' in result:
            print(f"\n  Error: {result['error']}")

    print("\n" + "="*60)
    print("FIND_SIMILAR_WALLETS TEST COMPLETE")
    print("="*60 + "\n")


async def main():
    """Run all tests."""
    print("\n")
    print("#" * 60)
    print("# SATURATION ANALYSIS TEST SUITE")
    print("#" * 60)

    # Test saturation tracking
    await test_saturation_tracking()

    # Test find_similar_wallets (commented out by default - requires API access)
    # Uncomment to test with real Polymarket data:
    # await test_find_similar_wallets()

    print("\nAll tests completed!\n")


if __name__ == "__main__":
    asyncio.run(main())
