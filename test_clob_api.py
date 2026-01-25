#!/usr/bin/env python3
"""Test the CLOB price history API to debug the scalp backtest."""

import requests
from datetime import datetime, timedelta, timezone
import json

def test_clob_api():
    print("Testing CLOB Price History API...")
    print("Looking for markets that resolved in the last 48 hours...")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    # Paginate through events to find recent ones
    offset = 0
    tested = 0
    while tested < 5:
        events_url = f'https://gamma-api.polymarket.com/events?closed=true&limit=100&offset={offset}'
        resp = requests.get(events_url, timeout=30)
        events = resp.json()

        if not events:
            print("No more events")
            break

        for event in events:
            markets = event.get('markets', [])
            for market in markets:
                if not market.get('closed'):
                    continue
                end_date = market.get('endDate') or event.get('endDate', '')
                if not end_date:
                    continue

                # Parse end date
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                except:
                    continue

                # Skip if too old
                if end_dt < cutoff:
                    continue

                clob_ids_str = market.get('clobTokenIds', '[]')
                clob_ids = json.loads(clob_ids_str) if isinstance(clob_ids_str, str) else clob_ids_str

                if not clob_ids:
                    continue

                token_id = clob_ids[0]
                question = market.get('question', 'Unknown')[:60]
                print(f'\n=== Market {tested + 1} ===')
                print(f'Question: {question}')
                print(f'End Date: {end_date}')
                print(f'Token ID: {token_id[:20]}...')

                # Try to get price history
                start_dt = end_dt - timedelta(hours=48)

                url = f'https://clob.polymarket.com/prices-history?market={token_id}&startTs={int(start_dt.timestamp())}&endTs={int(end_dt.timestamp())}&fidelity=60'

                r = requests.get(url, timeout=15)
                print(f'CLOB API Status: {r.status_code}')

                if r.status_code == 200:
                    data = r.json()
                    history = data.get('history', [])
                    print(f'History points: {len(history)}')
                    if history:
                        first = history[0]
                        last = history[-1]
                        print(f'First: t={first.get("t")} ({datetime.fromtimestamp(first.get("t"), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")}), p={first.get("p"):.4f}')
                        print(f'Last: t={last.get("t")} ({datetime.fromtimestamp(last.get("t"), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")}), p={last.get("p"):.4f}')

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
                        print(f'Price 2h before resolution: {best_price:.4f}')
                        print(f'CLOB HAS DATA - Strategy is testable!')
                    else:
                        print('No history data - CLOB does not retain history for this market')
                else:
                    print(f'Error: {r.text[:200]}')

                tested += 1
                if tested >= 5:
                    break

        offset += 100

    print(f'\n\nTested {tested} recent markets')

if __name__ == '__main__':
    test_clob_api()
