"""
Example usage of the Polymarket Wallet Scanner

This script demonstrates how to use the scanner module to find emerging traders.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner import WalletScanner, quick_scan, get_wallet_info


async def example_1_basic_leaderboard():
    """Example 1: Fetch and display the leaderboard."""
    print("=" * 80)
    print("EXAMPLE 1: Fetch Leaderboard")
    print("=" * 80)

    async with WalletScanner() as scanner:
        leaderboard = await scanner.fetch_leaderboard(limit=10)

        print(f"\nTop {len(leaderboard)} traders on Polymarket:\n")
        for profile in leaderboard:
            print(f"#{profile.rank:3d} | {profile.username or profile.address[:10]:20s} | "
                  f"Profit: ${profile.profit:>10,.2f} | "
                  f"Win Rate: {profile.win_rate*100:5.1f}% | "
                  f"Trades: {profile.trade_count:4d}")


async def example_2_wallet_details():
    """Example 2: Get detailed stats for a specific wallet."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Get Wallet Details")
    print("=" * 80)

    # First get a wallet address from leaderboard
    async with WalletScanner() as scanner:
        leaderboard = await scanner.fetch_leaderboard(limit=5)

        if not leaderboard:
            print("No traders found on leaderboard")
            return

        # Pick the top trader
        top_trader_address = leaderboard[0].address
        print(f"\nAnalyzing top trader: {top_trader_address}\n")

        # Get detailed stats
        profile = await scanner.fetch_wallet_stats(top_trader_address)

        if profile:
            print(f"Address:             {profile.address}")
            print(f"Username:            {profile.username or 'N/A'}")
            print(f"Profit:              ${profile.profit:,.2f}")
            print(f"Win Rate:            {profile.win_rate*100:.1f}%")
            print(f"Trade Count:         {profile.trade_count}")
            print(f"Markets Traded:      {profile.markets_traded}")
            print(f"Volume:              ${profile.volume:,.2f}")
            print(f"Avg Position Size:   ${profile.avg_position_size:,.2f}")
            print(f"Largest Win:         ${profile.largest_win:,.2f}")
            print(f"Largest Loss:        ${profile.largest_loss:,.2f}")
            print(f"Avg Profit/Trade:    ${profile.avg_profit_per_trade:,.2f}")
            print(f"Account Age:         {profile.age_days} days" if profile.age_days else "Unknown")

            # Show recent trades
            if profile.trades:
                print(f"\nRecent trades ({len(profile.trades)}):")
                for trade in profile.trades[:5]:
                    print(f"  {trade.timestamp.strftime('%Y-%m-%d %H:%M')} | "
                          f"{trade.side:4s} | "
                          f"${trade.size:8,.2f} @ {trade.price:.3f} | "
                          f"P&L: ${trade.profit:+8,.2f}")


async def example_3_scan_emerging_traders():
    """Example 3: Scan for emerging alpha traders."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Scan for Emerging Traders")
    print("=" * 80)

    # Define criteria
    min_profit = 5000.0  # $5k minimum profit
    min_win_rate = 0.85  # 85% win rate
    max_age_days = 60    # Account less than 60 days old

    print(f"\nSearching for traders with:")
    print(f"  - Profit >= ${min_profit:,.0f}")
    print(f"  - Win Rate >= {min_win_rate*100:.0f}%")
    print(f"  - Account Age <= {max_age_days} days")
    print()

    async with WalletScanner(rate_limit=5.0) as scanner:
        emerging_traders = await scanner.scan_for_emerging_traders(
            min_profit=min_profit,
            min_win_rate=min_win_rate,
            max_age_days=max_age_days,
            leaderboard_limit=100,  # Scan top 100 traders
        )

        print(f"\n{'=' * 80}")
        print(f"RESULTS: Found {len(emerging_traders)} emerging traders")
        print(f"{'=' * 80}\n")

        if emerging_traders:
            for i, trader in enumerate(emerging_traders, start=1):
                print(f"{i}. {trader.username or trader.address[:10]}")
                print(f"   Address:     {trader.address}")
                print(f"   Profit:      ${trader.profit:,.2f}")
                print(f"   Win Rate:    {trader.win_rate*100:.1f}%")
                print(f"   Trades:      {trader.trade_count}")
                print(f"   Markets:     {trader.markets_traded}")
                print(f"   Age:         {trader.age_days} days")
                print(f"   Avg P&L:     ${trader.avg_profit_per_trade:,.2f} per trade")
                print()
        else:
            print("No emerging traders found matching the criteria.")


async def example_4_batch_analysis():
    """Example 4: Analyze multiple wallets in batch."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Batch Wallet Analysis")
    print("=" * 80)

    # Get some wallet addresses from leaderboard
    async with WalletScanner() as scanner:
        leaderboard = await scanner.fetch_leaderboard(limit=20)
        addresses = [profile.address for profile in leaderboard[:10]]

        print(f"\nAnalyzing {len(addresses)} wallets in batch...\n")

        # Fetch stats for all wallets concurrently
        profiles = await scanner.batch_fetch_wallet_stats(addresses, max_concurrent=5)

        print(f"Successfully fetched data for {len(profiles)} wallets\n")

        # Calculate some aggregate statistics
        if profiles:
            total_profit = sum(p.profit for p in profiles)
            avg_win_rate = sum(p.win_rate for p in profiles) / len(profiles)
            total_trades = sum(p.trade_count for p in profiles)

            print("Aggregate Statistics:")
            print(f"  Total Profit:     ${total_profit:,.2f}")
            print(f"  Average Win Rate: {avg_win_rate*100:.1f}%")
            print(f"  Total Trades:     {total_trades:,}")
            print(f"  Avg Trades/User:  {total_trades/len(profiles):.0f}")


async def example_5_convenience_functions():
    """Example 5: Using convenience functions."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Convenience Functions")
    print("=" * 80)

    print("\nUsing quick_scan()...")
    emerging = await quick_scan(
        min_profit=3000,
        min_win_rate=0.80,
        max_age_days=90,
    )
    print(f"Found {len(emerging)} traders using quick_scan()")

    # Get info for first trader if available
    if emerging:
        address = emerging[0].address
        print(f"\nUsing get_wallet_info() for {address[:10]}...")
        info = await get_wallet_info(address)
        if info:
            print(f"  Profit: ${info.profit:,.2f}")
            print(f"  Win Rate: {info.win_rate*100:.1f}%")


async def main():
    """Run all examples."""
    try:
        await example_1_basic_leaderboard()
        await asyncio.sleep(1)  # Brief pause between examples

        await example_2_wallet_details()
        await asyncio.sleep(1)

        await example_3_scan_emerging_traders()
        await asyncio.sleep(1)

        await example_4_batch_analysis()
        await asyncio.sleep(1)

        await example_5_convenience_functions()

        print("\n" + "=" * 80)
        print("All examples completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
