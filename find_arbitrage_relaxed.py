#!/usr/bin/env python3
"""
Relaxed arbitrage scanner - shows all near-arbitrage opportunities
"""

import requests
import time
import json
from typing import List, Dict, Any

def get_markets(limit=100, offset=0):
    """Fetch active markets from Polymarket"""
    url = f"https://gamma-api.polymarket.com/markets?closed=false&limit={limit}&offset={offset}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def get_order_book(token_id: str):
    """Get order book for a specific token"""
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Extract best ask (lowest sell price)
        if 'asks' in data and data['asks']:
            best_ask = float(data['asks'][0]['price'])
            size = float(data['asks'][0]['size'])
            return best_ask, size
        return None, None
    except Exception as e:
        return None, None

def find_binary_markets(markets_data):
    """Filter to binary YES/NO markets only"""
    binary_markets = []

    for market in markets_data:
        if 'clobTokenIds' in market:
            try:
                token_ids = json.loads(market['clobTokenIds'])
                if len(token_ids) == 2:
                    outcomes = json.loads(market.get('outcomes', '[]'))
                    if len(outcomes) == 2:
                        yes_idx = None
                        no_idx = None
                        for i, outcome in enumerate(outcomes):
                            if outcome.upper() == 'YES':
                                yes_idx = i
                            elif outcome.upper() == 'NO':
                                no_idx = i
                        if yes_idx is not None and no_idx is not None:
                            binary_markets.append({
                                'question': market.get('question', 'Unknown'),
                                'market_id': market.get('id'),
                                'yes_token': token_ids[yes_idx],
                                'no_token': token_ids[no_idx],
                                'volume': float(market.get('volume', 0)),
                                'liquidity': float(market.get('liquidity', 0))
                            })
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                continue
    return binary_markets

def scan_for_arbitrage(min_liquidity=100, min_edge_pct=0.2):
    """Scan all markets for arbitrage opportunities"""
    print("Fetching markets from Polymarket...")
    print(f"Filters: min_liquidity=${min_liquidity}, min_edge={min_edge_pct}%")
    print()

    opportunities = []
    total_markets_checked = 0

    # Fetch multiple pages of markets
    for offset in [0, 100, 200, 300, 400]:
        try:
            markets_data = get_markets(limit=100, offset=offset)
            binary_markets = find_binary_markets(markets_data)
            print(f"Checking {len(binary_markets)} binary markets at offset {offset}...")

            for market in binary_markets:
                total_markets_checked += 1

                # Rate limit
                time.sleep(0.15)

                # Get order books
                yes_ask, yes_size = get_order_book(market['yes_token'])
                no_ask, no_size = get_order_book(market['no_token'])

                if yes_ask is not None and no_ask is not None:
                    combined_cost = yes_ask + no_ask
                    edge = 1.0 - combined_cost
                    edge_pct = edge * 100

                    # Check for arbitrage (any edge, even negative)
                    min_size = min(yes_size, no_size)
                    liquidity_usd = min_size * combined_cost

                    if liquidity_usd >= min_liquidity and edge_pct >= min_edge_pct:
                        opportunities.append({
                            'market': market['question'],
                            'yes_price': yes_ask,
                            'no_price': no_ask,
                            'combined_cost': combined_cost,
                            'edge_pct': edge_pct,
                            'profit_per_100': edge * 100,
                            'liquidity_usd': liquidity_usd,
                            'max_shares': min_size,
                            'volume_24h': market.get('volume', 0)
                        })

        except Exception as e:
            print(f"Error fetching markets at offset {offset}: {e}")

    print(f"\nTotal markets checked: {total_markets_checked}")
    return opportunities

def main():
    print("=" * 80)
    print("POLYMARKET ARBITRAGE SCANNER - RELAXED FILTERS")
    print("=" * 80)
    print()

    opportunities = scan_for_arbitrage(min_liquidity=100, min_edge_pct=0.2)

    print("\n" + "=" * 80)
    print(f"RESULTS: Found {len(opportunities)} opportunities")
    print("=" * 80)
    print()

    if opportunities:
        # Sort by edge percentage (descending)
        opportunities.sort(key=lambda x: x['edge_pct'], reverse=True)

        # Show top 20
        for i, opp in enumerate(opportunities[:20], 1):
            print(f"{i}. {opp['market'][:70]}")
            print(f"   YES: ${opp['yes_price']:.4f} | NO: ${opp['no_price']:.4f}")
            print(f"   Combined Cost: ${opp['combined_cost']:.4f}")
            print(f"   Edge: {opp['edge_pct']:.3f}% | Profit per $100: ${opp['profit_per_100']:.3f}")
            print(f"   Liquidity: ${opp['liquidity_usd']:.0f} ({opp['max_shares']:.0f} shares)")
            print()

        if len(opportunities) > 20:
            print(f"... and {len(opportunities) - 20} more opportunities")
            print()

        # Statistics
        print("=" * 80)
        print("STATISTICS")
        print("=" * 80)
        avg_edge = sum(o['edge_pct'] for o in opportunities) / len(opportunities)
        max_edge = max(opportunities, key=lambda x: x['edge_pct'])
        total_liquidity = sum(o['liquidity_usd'] for o in opportunities)

        print(f"Average edge: {avg_edge:.3f}%")
        print(f"Best edge: {max_edge['edge_pct']:.3f}% ({max_edge['market'][:50]}...)")
        print(f"Total available liquidity: ${total_liquidity:,.0f}")
        print(f"Opportunities >0.5% edge: {len([o for o in opportunities if o['edge_pct'] > 0.5])}")
        print(f"Opportunities >1.0% edge: {len([o for o in opportunities if o['edge_pct'] > 1.0])}")
        print(f"Opportunities >2.0% edge: {len([o for o in opportunities if o['edge_pct'] > 2.0])}")
    else:
        print("No arbitrage opportunities found.")
        print("The markets are currently very efficient!")

if __name__ == "__main__":
    main()
