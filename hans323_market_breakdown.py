#!/usr/bin/env python3
"""Breakdown of Hans323 activity by market type."""
import requests
from collections import defaultdict

WALLET = '0x0f37cb80dee49d55b5f6d9e595d52591d6371410'

print('='*70)
print('HANS323 MARKET BREAKDOWN')
print('='*70)

# Get all activity
print('\nFetching all activity...')
all_activity = []
offset = 0
while True:
    r = requests.get(
        f'https://data-api.polymarket.com/activity?user={WALLET}&limit=500&offset={offset}',
        timeout=30
    )
    batch = r.json()
    if not batch:
        break
    all_activity.extend(batch)
    if len(batch) < 500:
        break
    offset += 500
    print(f'  Fetched {len(all_activity)}...')

print(f'Total activity records: {len(all_activity)}')

# Categorize by market
market_stats = defaultdict(lambda: {'trades': 0, 'buy_vol': 0.0, 'sell_vol': 0.0, 'redeem_vol': 0.0})

for a in all_activity:
    title = a.get('title', 'Unknown')[:60]
    t = a.get('type')
    side = a.get('side')
    size = float(a.get('usdcSize', 0) or 0)

    # Categorize
    title_lower = title.lower()
    if 'temperature' in title_lower:
        cat = 'WEATHER'
    elif 'tesla' in title_lower or 'fsd' in title_lower:
        cat = 'TESLA'
    elif 'trump' in title_lower or 'biden' in title_lower or 'president' in title_lower:
        cat = 'POLITICS'
    elif 'bitcoin' in title_lower or 'crypto' in title_lower or 'eth' in title_lower:
        cat = 'CRYPTO'
    else:
        cat = 'OTHER'

    market_stats[cat]['trades'] += 1
    if t == 'TRADE':
        if side == 'BUY':
            market_stats[cat]['buy_vol'] += size
        elif side == 'SELL':
            market_stats[cat]['sell_vol'] += size
    elif t == 'REDEEM':
        market_stats[cat]['redeem_vol'] += size

print('\n--- VOLUME BY CATEGORY ---')
for cat, stats in sorted(market_stats.items(), key=lambda x: x[1]['buy_vol'] + x[1]['sell_vol'], reverse=True):
    total_trade = stats['buy_vol'] + stats['sell_vol']
    print(f'\n{cat}:')
    print(f'  Activity count: {stats["trades"]}')
    print(f'  BUY volume:    ${stats["buy_vol"]:,.2f}')
    print(f'  SELL volume:   ${stats["sell_vol"]:,.2f}')
    print(f'  REDEEM volume: ${stats["redeem_vol"]:,.2f}')

    # Simple P&L (redeems - buys, ignoring sells since they return money)
    # For SELL: you receive USDC
    # For BUY: you spend USDC
    # For REDEEM: you receive USDC
    net = stats['redeem_vol'] + stats['sell_vol'] - stats['buy_vol']
    print(f'  Net (redeem+sell-buy): ${net:+,.2f}')

# Show sample trades for each category
print('\n' + '='*70)
print('SAMPLE TRADES BY CATEGORY')
print('='*70)

trades_only = [a for a in all_activity if a.get('type') == 'TRADE']

# Weather samples
print('\n--- WEATHER SAMPLES ---')
weather = [t for t in trades_only if 'temperature' in str(t.get('title','')).lower()]
for t in weather[:5]:
    title = t.get('title', '')[:50]
    side = t.get('side')
    outcome = t.get('outcome')
    price = float(t.get('price', 0) or 0)
    size = float(t.get('usdcSize', 0) or 0)
    print(f'  {side} {outcome} @ {price:.3f} | ${size:.2f} | {title}')

# Tesla samples
print('\n--- TESLA SAMPLES ---')
tesla = [t for t in trades_only if 'tesla' in str(t.get('title','')).lower() or 'fsd' in str(t.get('title','')).lower()]
for t in tesla[:10]:
    title = t.get('title', '')[:50]
    side = t.get('side')
    outcome = t.get('outcome')
    price = float(t.get('price', 0) or 0)
    size = float(t.get('usdcSize', 0) or 0)
    print(f'  {side} {outcome} @ {price:.3f} | ${size:.2f} | {title}')

# Analyze Tesla strategy
print('\n' + '='*70)
print('TESLA STRATEGY ANALYSIS')
print('='*70)

buy_yes = [t for t in tesla if t.get('side') == 'BUY' and t.get('outcome') == 'Yes']
buy_no = [t for t in tesla if t.get('side') == 'BUY' and t.get('outcome') == 'No']
sell_yes = [t for t in tesla if t.get('side') == 'SELL' and t.get('outcome') == 'Yes']
sell_no = [t for t in tesla if t.get('side') == 'SELL' and t.get('outcome') == 'No']

print(f'\nBUY Yes: {len(buy_yes)} trades, ${sum(float(t.get("usdcSize",0) or 0) for t in buy_yes):,.2f}')
print(f'BUY No: {len(buy_no)} trades, ${sum(float(t.get("usdcSize",0) or 0) for t in buy_no):,.2f}')
print(f'SELL Yes: {len(sell_yes)} trades, ${sum(float(t.get("usdcSize",0) or 0) for t in sell_yes):,.2f}')
print(f'SELL No: {len(sell_no)} trades, ${sum(float(t.get("usdcSize",0) or 0) for t in sell_no):,.2f}')

if sell_no:
    sell_no_prices = [float(t.get('price',0) or 0) for t in sell_no]
    print(f'\nSELL No price range: {min(sell_no_prices):.3f} - {max(sell_no_prices):.3f}')
    print(f'SELL No avg price: {sum(sell_no_prices)/len(sell_no_prices):.3f}')

# Check what other non-categorized markets
print('\n' + '='*70)
print('OTHER MARKETS (top by volume)')
print('='*70)

other = [a for a in all_activity if a.get('type') == 'TRADE']
market_vols = defaultdict(float)
for a in other:
    title = a.get('title', 'Unknown')
    title_lower = title.lower()
    if 'temperature' not in title_lower and 'tesla' not in title_lower and 'fsd' not in title_lower:
        market_vols[title] += float(a.get('usdcSize', 0) or 0)

sorted_markets = sorted(market_vols.items(), key=lambda x: x[1], reverse=True)
for title, vol in sorted_markets[:15]:
    print(f'  ${vol:>10,.2f} | {title[:60]}')
