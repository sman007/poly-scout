#!/usr/bin/env python3
"""Test the CLOB price history API to debug the scalp backtest."""

import requests
from datetime import datetime, timedelta
import json

def test_clob_api():
    print("Testing CLOB Price History API...")

    # Get a recently resolved market from PM
    events_url = 'https://gamma-api.polymarket.com/events?closed=true&limit=3'
    resp = requests.get(events_url, timeout=30)
    events = resp.json()

    for event in events:
        markets = event.get('markets', [])
        for market in markets:
            if not market.get('closed'):
                continue
            end_date = market.get('endDate') or event.get('endDate', '')
            if not end_date:
                continue

            clob_ids_str = market.get('clobTokenIds', '[]')
            clob_ids = json.loads(clob_ids_str) if isinstance(clob_ids_str, str) else clob_ids_str

            if not clob_ids:
                continue

            token_id = clob_ids[0]
            question = market.get('question', 'Unknown')[:60]
            print(f'Market: {question}')
            print(f'End Date: {end_date}')
            print(f'Token ID: {token_id}')

            # Try to get price history
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            start_dt = end_dt - timedelta(hours=48)

            url = f'https://clob.polymarket.com/prices-history?market={token_id}&startTs={int(start_dt.timestamp())}&endTs={int(end_dt.timestamp())}&fidelity=60'
            print(f'Requesting price history...')

            r = requests.get(url, timeout=15)
            print(f'Status: {r.status_code}')

            if r.status_code == 200:
                data = r.json()
                history = data.get('history', [])
                print(f'History points: {len(history)}')
                if history:
                    first = history[0]
                    last = history[-1]
                    print(f'First: t={first.get("t")}, p={first.get("p")}')
                    print(f'Last: t={last.get("t")}, p={last.get("p")}')

                    # Look for 2 hours before resolution
                    target_time = end_dt - timedelta(hours=2)
                    best_price = None
                    best_diff = float('inf')
                    for point in history:
                        t = point.get('t', 0)
                        p = point.get('p', 0)
                        point_dt = datetime.fromtimestamp(t, tz=end_dt.tzinfo)
                        diff = abs((point_dt - target_time).total_seconds())
                        if diff < best_diff:
                            best_diff = diff
                            best_price = float(p)
                    print(f'Price 2h before resolution: {best_price}')
                else:
                    print('No history data!')
            else:
                print(f'Error: {r.text[:200]}')
            print('---')
            return  # Just test one market

if __name__ == '__main__':
    test_clob_api()
