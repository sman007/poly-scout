#!/usr/bin/env python3
"""Scout specific wallets through validation."""
import requests
import sys
sys.path.insert(0, ".")
from src.wallet_validator import validate_wallet

def analyze_wallet(address, name):
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"SCOUTING: {name}")
    print(f"Wallet: {address}")
    print(sep)

    # Get positions
    r = requests.get(f"https://data-api.polymarket.com/positions?user={address}", timeout=15)
    positions = r.json()

    # Get activity/trades
    r2 = requests.get(f"https://data-api.polymarket.com/activity?user={address}&limit=500", timeout=15)
    trades = r2.json()

    print(f"\nDATA RETRIEVED:")
    print(f"  Positions: {len(positions)}")
    print(f"  Trades (recent): {len(trades)}")

    # Calculate basic stats
    total_pnl = sum(float(p.get("cashPnl", 0) or 0) for p in positions)
    wins = sum(1 for p in positions if float(p.get("cashPnl", 0) or 0) > 0)
    losses = sum(1 for p in positions if float(p.get("cashPnl", 0) or 0) < 0)
    open_pos = sum(1 for p in positions if float(p.get("currentValue", 0) or 0) > 0)

    print(f"\nPOSITION STATS:")
    print(f"  Total PnL: ${total_pnl:,.2f}")
    print(f"  Wins: {wins} | Losses: {losses} | Open: {open_pos}")
    if (wins + losses) > 0:
        print(f"  Win Rate: {wins/(wins+losses)*100:.1f}%")
    else:
        print(f"  Win Rate: N/A")

    # Run statistical validation
    print(f"\nSTATISTICAL VALIDATION:")
    result = validate_wallet(positions, trades)
    print(f"  Valid: {result.is_valid}")
    print(f"  Win Rate: {result.win_rate:.1%}")
    print(f"  P-value: {result.win_rate_pvalue:.6f}")
    print(f"  Consistency: {result.consistency_variance:.4f}")
    print(f"  Sample Size: {result.sample_size}")
    print(f"  Confidence: {result.confidence_level}")
    if result.rejection_reason:
        print(f"  Rejection: {result.rejection_reason}")

    # Category breakdown
    weather = [p for p in positions if any(x in str(p.get("title","")).lower() for x in ["temp", "weather", "celsius", "fahrenheit"])]
    sports = [p for p in positions if any(x in str(p.get("title","")).lower() for x in ["nba", "nfl", "soccer", "tennis", "hockey", "bulls", "lakers", "celtics", "spread", "magic", "nuggets"])]
    btc = [p for p in positions if "btc" in str(p.get("title","")).lower() or "bitcoin" in str(p.get("title","")).lower()]
    politics = [p for p in positions if any(x in str(p.get("title","")).lower() for x in ["trump", "biden", "election", "president", "congress"])]

    print(f"\nCATEGORY BREAKDOWN:")
    print(f"  Weather: {len(weather)} positions")
    print(f"  Sports: {len(sports)} positions")
    print(f"  BTC/Crypto: {len(btc)} positions")
    print(f"  Politics: {len(politics)} positions")

    # Top 5 positions
    print(f"\nTOP 5 POSITIONS BY PNL:")
    top = sorted(positions, key=lambda x: float(x.get("cashPnl", 0) or 0), reverse=True)[:5]
    for i, p in enumerate(top, 1):
        pnl = float(p.get("cashPnl", 0) or 0)
        title = str(p.get("title", ""))[:50]
        print(f"  {i}. ${pnl:+,.0f}: {title}")

    # Recent activity
    print(f"\nRECENT TRADES (last 5):")
    for t in trades[:5]:
        ttype = t.get("type", "")
        title = str(t.get("title", ""))[:40]
        value = float(t.get("value", 0) or 0)
        print(f"  {ttype}: ${value:.2f} - {title}")

    return result


if __name__ == "__main__":
    # Scout the two wallets
    wallets = [
        ("0x0f37cb80dee49d55b5f6d9e595d52591d6371410", "Hans323 (Weather)"),
        ("0x204f72f35326db932158cba6adff0b9a1da95e14", "@swisstony ($3.7M)")
    ]

    for addr, name in wallets:
        try:
            analyze_wallet(addr, name)
        except Exception as e:
            print(f"ERROR analyzing {name}: {e}")

    sep = "=" * 70
    print(f"\n{sep}")
    print("SCOUT COMPLETE")
    print(sep)
