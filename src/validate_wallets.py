#!/usr/bin/env python3
"""
Validate Tracked Wallets Win Rates.

Fetches actual position data from Polymarket Data API and calculates
TRUE win rates for our tracked "smart money" wallets.

This provides ground truth on whether these wallets are actually profitable.

Usage:
    python -m src.validate_wallets
"""

import requests
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import defaultdict
import time


def log(msg: str):
    print(f"[VALIDATE] {msg}", flush=True)


# Top wallets to validate - we'll look up addresses by username
TRACKED_WALLETS = [
    {
        "username": "lfc123",
        "claimed_win_rate": "Very Strong",
        "claimed_focus": "NCAA Basketball",
        "claimed_size": "$10K-440K"
    },
    {
        "username": "kch123",
        "claimed_win_rate": "VERY HIGH",
        "claimed_focus": "NHL WHALE",
        "claimed_size": "$2.5K-56K"
    },
    {
        "username": "gatorr",
        "claimed_win_rate": "~70%+",
        "claimed_focus": "NHL totals, CBB",
        "claimed_size": "$2K-25K"
    },
    {
        "username": "wagwag",
        "claimed_win_rate": "Strong",
        "claimed_focus": "NBA spreads",
        "claimed_size": "$2.5K-10K"
    },
    {
        "username": "norrisfan",
        "claimed_win_rate": "~80%",
        "claimed_focus": "Spanish Soccer",
        "claimed_size": "$1.2K-4.5K"
    },
    {
        "username": "Pimping",
        "claimed_win_rate": "High",
        "claimed_focus": "UFC",
        "claimed_size": "$5K-150K"
    },
    {
        "username": "BigGumbaBoots",
        "claimed_win_rate": "~65%+",
        "claimed_focus": "UFC, LoL",
        "claimed_size": "$3K-8K"
    },
    {
        "username": "peter77777",
        "claimed_win_rate": "~95%+",
        "claimed_focus": "LoL Esports",
        "claimed_size": "$50-4,500"
    }
]


def lookup_wallet_address(username: str) -> Optional[str]:
    """Look up wallet address by username via Polymarket API."""
    try:
        # Search leaderboard for username
        url = f"https://data-api.polymarket.com/users?limit=100"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            users = r.json()
            for user in users:
                if user.get("username", "").lower() == username.lower():
                    return user.get("proxyWallet") or user.get("address")

        # Try searching directly
        url = f"https://data-api.polymarket.com/users?username={username}"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            users = r.json()
            if users:
                return users[0].get("proxyWallet") or users[0].get("address")

    except Exception as e:
        log(f"  Error looking up {username}: {e}")

    return None


@dataclass
class Position:
    """A resolved position."""
    market_slug: str
    outcome: str
    cost_basis: float
    cash_pnl: float
    redeemed: float
    is_winner: bool


def fetch_positions(address: str) -> List[Dict]:
    """Fetch all positions for a wallet from Data API."""
    positions = []
    offset = 0
    limit = 100

    while True:
        url = f"https://data-api.polymarket.com/positions?user={address}&limit={limit}&offset={offset}"

        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                log(f"  API error: {r.status_code}")
                break

            data = r.json()
            if not data:
                break

            positions.extend(data)
            log(f"  Fetched {len(data)} positions (total: {len(positions)})")

            if len(data) < limit:
                break

            offset += limit
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            log(f"  Error: {e}")
            break

    return positions


def analyze_positions(positions: List[Dict]) -> Dict:
    """Analyze positions to calculate win rate and P&L."""
    total_positions = len(positions)
    resolved = 0
    wins = 0
    losses = 0
    total_pnl = 0.0
    total_invested = 0.0

    winning_trades = []
    losing_trades = []

    for p in positions:
        # Get position details
        cash_pnl = float(p.get("cashPnl", 0) or 0)
        current_value = float(p.get("currentValue", 0) or 0)
        redeemed = float(p.get("redeemed", 0) or 0)
        size = float(p.get("size", 0) or 0)
        avg_price = float(p.get("avgPrice", 0) or 0)

        # Calculate cost basis
        cost_basis = size * avg_price if size > 0 and avg_price > 0 else 0

        # Determine if position is resolved
        # A position is resolved if it has been redeemed or has non-zero cashPnl
        if redeemed > 0 or cash_pnl != 0:
            resolved += 1
            total_pnl += cash_pnl
            total_invested += cost_basis

            if cash_pnl > 0:
                wins += 1
                winning_trades.append({
                    "market": p.get("market_slug", "Unknown"),
                    "pnl": cash_pnl,
                    "size": size
                })
            elif cash_pnl < 0:
                losses += 1
                losing_trades.append({
                    "market": p.get("market_slug", "Unknown"),
                    "pnl": cash_pnl,
                    "size": size
                })
            # cash_pnl == 0 can mean break-even or not resolved yet

    win_rate = wins / resolved if resolved > 0 else 0
    roi = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    return {
        "total_positions": total_positions,
        "resolved": resolved,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_invested": total_invested,
        "roi": roi,
        "top_wins": sorted(winning_trades, key=lambda x: x["pnl"], reverse=True)[:5],
        "top_losses": sorted(losing_trades, key=lambda x: x["pnl"])[:5]
    }


def validate_all_wallets():
    """Validate all tracked wallets."""
    log("=" * 70)
    log("TRACKED WALLET VALIDATION")
    log("=" * 70)
    log("Fetching actual position data from Polymarket Data API")
    log("Calculating TRUE win rates for claimed 'smart money' wallets")
    log("=" * 70)

    results = []

    for wallet in TRACKED_WALLETS:
        log(f"\n{'='*50}")
        log(f"Looking up: {wallet['username']}")

        # Look up address by username
        address = lookup_wallet_address(wallet['username'])
        if not address:
            log(f"  Could not find address for {wallet['username']}")
            results.append({
                "username": wallet["username"],
                "error": "Address not found"
            })
            continue

        log(f"  Found address: {address[:10]}...")
        log(f"Claimed: {wallet['claimed_win_rate']} on {wallet['claimed_focus']}")
        log("=" * 50)

        positions = fetch_positions(address)

        if not positions:
            log("  No positions found (may need different address format)")
            results.append({
                "username": wallet["username"],
                "error": "No positions found"
            })
            continue

        analysis = analyze_positions(positions)

        log(f"\nRESULTS:")
        log(f"  Total Positions: {analysis['total_positions']}")
        log(f"  Resolved: {analysis['resolved']}")
        log(f"  Wins: {analysis['wins']} | Losses: {analysis['losses']}")
        log(f"  WIN RATE: {analysis['win_rate']:.1%}")
        log(f"  Total P&L: ${analysis['total_pnl']:,.2f}")
        log(f"  ROI: {analysis['roi']:.1f}%")

        if analysis['top_wins']:
            log(f"\n  Top Wins:")
            for w in analysis['top_wins'][:3]:
                log(f"    ${w['pnl']:,.2f} on {w['market'][:40]}...")

        if analysis['top_losses']:
            log(f"\n  Top Losses:")
            for l in analysis['top_losses'][:3]:
                log(f"    ${l['pnl']:,.2f} on {l['market'][:40]}...")

        # Compare to claimed
        claimed = wallet['claimed_win_rate']
        actual = analysis['win_rate']

        if "95" in claimed and actual >= 0.90:
            verdict = "✅ CONFIRMED"
        elif "80" in claimed and actual >= 0.70:
            verdict = "✅ CLOSE"
        elif "70" in claimed and actual >= 0.60:
            verdict = "✅ CLOSE"
        elif "Strong" in claimed and actual >= 0.55:
            verdict = "⚠️ MODERATE"
        elif actual >= 0.55:
            verdict = "⚠️ PROFITABLE"
        else:
            verdict = "❌ BELOW CLAIMS"

        log(f"\n  Claimed: {claimed}")
        log(f"  Actual: {actual:.1%}")
        log(f"  Verdict: {verdict}")

        results.append({
            "username": wallet["username"],
            "claimed": claimed,
            "actual_win_rate": actual,
            "total_pnl": analysis["total_pnl"],
            "roi": analysis["roi"],
            "resolved": analysis["resolved"],
            "verdict": verdict
        })

        time.sleep(1)  # Rate limiting between wallets

    # Summary
    log("\n" + "=" * 70)
    log("SUMMARY")
    log("=" * 70)

    for r in results:
        if "error" in r:
            log(f"{r['username']}: {r['error']}")
        else:
            log(f"{r['username']:20} | WR: {r['actual_win_rate']:6.1%} | "
                f"P&L: ${r['total_pnl']:>10,.2f} | {r['verdict']}")

    return results


def main():
    results = validate_all_wallets()
    return results


if __name__ == "__main__":
    main()
