#!/usr/bin/env python3
"""
Analyze DiviLungaoBBW wallet (0xb45a797faa52b0fd8a)
SPORTS_ARB Strategy Analysis
"""

import requests
import json
from collections import defaultdict
from datetime import datetime

# Full wallet address from seen_wallets.json
WALLET = '0xb45a797faa52b0fd8adc56d30382022b7b12192c'

def log(msg):
    print(f"[DIVI-ANALYSIS] {msg}", flush=True)

def fetch_leaderboard():
    """Fetch leaderboard to find wallet stats."""
    url = "https://data-api.polymarket.com/leaderboard?limit=500"
    log(f"Fetching leaderboard...")

    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            log(f"Error: {r.status_code} - {r.text}")
            return []
    except Exception as e:
        log(f"Exception: {e}")
        return []

def find_wallet_in_leaderboard(leaderboard, wallet):
    """Find specific wallet in leaderboard."""
    for trader in leaderboard:
        if trader.get('address', '').lower() == wallet.lower():
            return trader
    return None

def analyze_trader_profile(trader):
    """Analyze trader profile from leaderboard data."""
    log("\n" + "="*70)
    log("TRADER PROFILE")
    log("="*70)

    log(f"Address: {trader.get('address', 'N/A')}")
    log(f"Username: {trader.get('name', 'N/A')}")
    log(f"Profit: ${trader.get('profit', 0):,.2f}")
    log(f"Volume: ${trader.get('volume', 0):,.2f}")
    log(f"Trades: {trader.get('trade_count', 0):,}")
    log(f"Markets: {trader.get('markets_traded', 0):,}")
    log(f"Win Rate: {trader.get('win_rate', 0)*100:.1f}%")
    log(f"Rank: #{trader.get('rank', 'N/A')}")

    if trader.get('trade_count', 0) > 0:
        log(f"Avg Profit/Trade: ${trader.get('profit', 0) / trader.get('trade_count', 1):,.2f}")

def main():
    log("="*70)
    log("DIVILUNGAOBBW WALLET ANALYSIS")
    log(f"Wallet: {WALLET}")
    log(f"Time: {datetime.now().isoformat()}")
    log("="*70)

    # Fetch leaderboard
    leaderboard = fetch_leaderboard()
    log(f"Leaderboard entries: {len(leaderboard)}")

    # Find wallet
    trader = find_wallet_in_leaderboard(leaderboard, WALLET)

    if trader:
        log("\nWallet FOUND in leaderboard!")
        analyze_trader_profile(trader)

        # Save to file
        output_file = "C:/Projects/poly-scout/output/divi_profile.json"
        with open(output_file, 'w') as f:
            json.dump(trader, f, indent=2)
        log(f"\nSaved profile to: {output_file}")
    else:
        log("\nWallet NOT FOUND in top 500 leaderboard")
        log("This wallet may not have enough activity/profit to rank")

    log("\n" + "="*70)
    log("ANALYSIS COMPLETE")
    log("="*70)

if __name__ == "__main__":
    main()
