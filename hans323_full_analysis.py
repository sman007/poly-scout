#!/usr/bin/env python3
"""Full analysis of Hans323 - all markets, not just weather."""
import requests
import json

WALLET = '0x0f37cb80dee49d55b5f6d9e595d52591d6371410'

print('='*70)
print('HANS323 FULL PROFILE ANALYSIS')
print('='*70)

# Get leaderboard data
print('\n--- LEADERBOARD DATA ---')
try:
    r = requests.get('https://data-api.polymarket.com/leaderboard?limit=100', timeout=30)
    leaderboard = r.json()
    for i, entry in enumerate(leaderboard):
        addr = entry.get('address', '').lower()
        if WALLET.lower() in addr or addr in WALLET.lower():
            print(f"Found Hans323 at rank #{i+1}")
            print(json.dumps(entry, indent=2))
            break
    else:
        print("Hans323 not in top 100 leaderboard")
except Exception as e:
    print(f"Leaderboard error: {e}")

# Get all positions with P&L
print('\n--- ALL POSITIONS ---')
r = requests.get(f'https://data-api.polymarket.com/positions?user={WALLET}', timeout=30)
positions = r.json()
print(f'Total positions: {len(positions)}')

# Categorize and sum P&L
total_pnl = 0
weather_pnl = 0
non_weather_pnl = 0
weather_count = 0
non_weather_count = 0

for p in positions:
    pnl = float(p.get('cashPnl', 0) or 0)
    title = str(p.get('title', '')).lower()
    total_pnl += pnl
    if 'temperature' in title:
        weather_pnl += pnl
        weather_count += 1
    else:
        non_weather_pnl += pnl
        non_weather_count += 1

print(f'\nP&L BREAKDOWN:')
print(f'  Total P&L:       ${total_pnl:+,.2f}')
print(f'  Weather P&L:     ${weather_pnl:+,.2f} ({weather_count} positions)')
print(f'  Non-Weather P&L: ${non_weather_pnl:+,.2f} ({non_weather_count} positions)')

# Show top positions by P&L
print('\n--- TOP 15 PROFITABLE POSITIONS ---')
sorted_positions = sorted(positions, key=lambda x: float(x.get('cashPnl', 0) or 0), reverse=True)
for p in sorted_positions[:15]:
    title = p.get('title', '')[:55]
    pnl = float(p.get('cashPnl', 0) or 0)
    outcome = p.get('outcome', '?')
    is_weather = 'temperature' in title.lower()
    marker = '[W]' if is_weather else '   '
    print(f'  {marker} ${pnl:+8,.2f} | {outcome}: {title}')

print('\n--- TOP 15 LOSING POSITIONS ---')
for p in sorted_positions[-15:]:
    title = p.get('title', '')[:55]
    pnl = float(p.get('cashPnl', 0) or 0)
    outcome = p.get('outcome', '?')
    is_weather = 'temperature' in title.lower()
    marker = '[W]' if is_weather else '   '
    print(f'  {marker} ${pnl:+8,.2f} | {outcome}: {title}')

# Get activity breakdown by type
print('\n--- ACTIVITY BY TYPE (last 500) ---')
r = requests.get(f'https://data-api.polymarket.com/activity?user={WALLET}&limit=500', timeout=30)
activity = r.json()

type_counts = {}
type_amounts = {}
for a in activity:
    t = a.get('type', 'unknown')
    amt = float(a.get('usdcSize', 0) or 0)
    type_counts[t] = type_counts.get(t, 0) + 1
    type_amounts[t] = type_amounts.get(t, 0) + amt

for t in type_counts:
    print(f'  {t}: {type_counts[t]} events, ${type_amounts[t]:,.2f}')

# Check for recent SELL trades
print('\n--- SELL TRADES (if any) ---')
sells = [a for a in activity if a.get('side') == 'SELL']
print(f'Total SELL trades in last 500: {len(sells)}')
for s in sells[:10]:
    title = s.get('title', '')[:50]
    price = s.get('price', 0)
    size = s.get('usdcSize', 0)
    outcome = s.get('outcome')
    print(f'  SELL {outcome} @ {price} | ${size} | {title}')

# Check current unrealized value
print('\n--- CURRENT HOLDINGS VALUE ---')
total_value = 0
for p in positions:
    size = float(p.get('size', 0) or 0)
    cur_price = float(p.get('curPrice', 0) or 0)
    value = size * cur_price
    total_value += value

print(f'Total current value: ${total_value:,.2f}')
print(f'Total realized P&L: ${total_pnl:,.2f}')

# Is weather actually profitable?
print('\n' + '='*70)
print('WEATHER ANALYSIS DETAIL')
print('='*70)

weather_positions = [p for p in positions if 'temperature' in str(p.get('title','')).lower()]
print(f'\nWeather positions: {len(weather_positions)}')

winning = [p for p in weather_positions if float(p.get('cashPnl', 0) or 0) > 0]
losing = [p for p in weather_positions if float(p.get('cashPnl', 0) or 0) < 0]
neutral = [p for p in weather_positions if float(p.get('cashPnl', 0) or 0) == 0]

print(f'Winning: {len(winning)}')
print(f'Losing: {len(losing)}')
print(f'Neutral (open/break-even): {len(neutral)}')

if winning:
    win_pnl = sum(float(p.get('cashPnl', 0) or 0) for p in winning)
    print(f'Total winnings: ${win_pnl:+,.2f}')
if losing:
    loss_pnl = sum(float(p.get('cashPnl', 0) or 0) for p in losing)
    print(f'Total losses: ${loss_pnl:+,.2f}')
