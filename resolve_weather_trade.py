#!/usr/bin/env python3
"""Resolve expired weather paper trades."""
import json
from datetime import datetime

# Load portfolio
with open('data/weather_seller_portfolio.json') as f:
    pf = json.load(f)

# Find positions to resolve
to_remove = []
for i, p in enumerate(pf['positions']):
    # Check if this is the London 7C Jan 24 position
    if 'london' in p['opportunity']['city'].lower() and '7' in p['opportunity']['bracket']:
        # Actual temp was 9.6C - No won (bracket did not hit)
        cost = p['cost']  # $100
        shares = p['shares']  # 100.65

        # SELL No: We receive premium (cost), owe $1/share if No wins
        # Loss = shares * $1 - cost = 100.65 - 100 = $0.65
        pnl = cost - shares  # Negative when No wins

        p['status'] = 'lost'
        p['pnl'] = pnl
        p['closed_at'] = datetime.now().isoformat()

        print(f"Resolved: {p['opportunity']['city'].upper()} {p['opportunity']['bracket']}")
        print(f"  Actual London temp: 9.6C (not 7C)")
        print(f"  Result: No wins - bracket did not hit")
        print(f"  P&L: ${pnl:.2f}")

        pf['closed_trades'].append(p)
        to_remove.append(i)

        # Update balance - return cost and deduct actual payout
        pf['balance'] = pf['balance'] + cost - shares

# Remove resolved positions
for i in reversed(to_remove):
    del pf['positions'][i]

# Save
pf['updated_at'] = datetime.now().isoformat()
with open('data/weather_seller_portfolio.json', 'w') as f:
    json.dump(pf, f, indent=2)

print(f"\nNew balance: ${pf['balance']:.2f}")
print(f"Open positions: {len(pf['positions'])}")
print(f"Total trades: {len(pf['closed_trades'])}")
