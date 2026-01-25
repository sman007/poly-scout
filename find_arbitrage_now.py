#!/usr/bin/env python3
"""
Quick arbitrage scanner for Polymarket
Finds live YES+NO arbitrage opportunities where sum(best_ask_yes, best_ask_no) < 1.00
"""

import requests
import time
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
        print(f"Error fetching order book for {token_id[:20]}...: {e}")
        return None, None

def find_binary_markets(markets_data):
    """Filter to binary YES/NO markets only"""
    import json
    binary_markets = []

    for market in markets_data:
        # Check for clobTokenIds field (this contains the token IDs)
        if 'clobTokenIds' in market:
            try:
                token_ids = json.loads(market['clobTokenIds'])

                # Binary markets have exactly 2 tokens
                if len(token_ids) == 2:
                    # Parse outcomes
                    outcomes = json.loads(market.get('outcomes', '[]'))

                    # Check if it's YES/NO
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

def scan_for_arbitrage(min_liquidity=500, min_edge_pct=1.0):
    """Scan all markets for arbitrage opportunities"""
    print("Fetching markets from Polymarket...")

    opportunities = []

    # Fetch multiple pages of markets
    for offset in [0, 100, 200]:
        try:
            markets_data = get_markets(limit=100, offset=offset)
            binary_markets = find_binary_markets(markets_data)
            print(f"Found {len(binary_markets)} binary markets at offset {offset}")

            for market in binary_markets:
                # Rate limit
                time.sleep(0.1)

                # Get order books
                yes_ask, yes_size = get_order_book(market['yes_token'])
                no_ask, no_size = get_order_book(market['no_token'])

                if yes_ask is not None and no_ask is not None:
                    combined_cost = yes_ask + no_ask
                    edge = 1.0 - combined_cost
                    edge_pct = edge * 100

                    # Check for arbitrage
                    if combined_cost < 1.0:
                        # Estimate available liquidity
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

                            print(f"✓ ARBITRAGE FOUND: {market['question'][:60]}...")
                            print(f"  YES: ${yes_ask:.3f}, NO: ${no_ask:.3f}, Combined: ${combined_cost:.3f}")
                            print(f"  Edge: {edge_pct:.2f}%, Profit per $100: ${edge * 100:.2f}")
                            print(f"  Liquidity: ${liquidity_usd:.0f}")
                            print()

        except Exception as e:
            print(f"Error fetching markets at offset {offset}: {e}")

    return opportunities

def main():
    print("=" * 80)
    print("POLYMARKET LIVE ARBITRAGE SCANNER")
    print("=" * 80)
    print()

    opportunities = scan_for_arbitrage(min_liquidity=500, min_edge_pct=1.0)

    print("\n" + "=" * 80)
    print(f"SUMMARY: Found {len(opportunities)} arbitrage opportunities")
    print("=" * 80)
    print()

    if opportunities:
        # Sort by edge percentage (descending)
        opportunities.sort(key=lambda x: x['edge_pct'], reverse=True)

        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp['market']}")
            print(f"   YES: ${opp['yes_price']:.3f} | NO: ${opp['no_price']:.3f}")
            print(f"   Combined Cost: ${opp['combined_cost']:.3f}")
            print(f"   Edge: {opp['edge_pct']:.2f}% | Profit per $100: ${opp['profit_per_100']:.2f}")
            print(f"   Liquidity Available: ${opp['liquidity_usd']:.0f} ({opp['max_shares']:.0f} shares)")
            print(f"   24h Volume: ${opp.get('volume_24h', 0):,.0f}")
            print()
    else:
        print("No arbitrage opportunities found with current filters.")
        print("(min_liquidity=$500, min_edge=1.0%)")
        print()
        print("The markets are currently efficient. Try:")
        print("1. Lower min_edge to 0.5% to see smaller edges")
        print("2. Lower min_liquidity to $100 for smaller opportunities")
        print("3. Check again in a few minutes as prices update")

if __name__ == "__main__":
    main()
