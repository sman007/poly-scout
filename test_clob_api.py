#!/usr/bin/env python3
"""Test the CLOB price history API to debug the scalp backtest."""

import requests
from datetime import datetime, timedelta, timezone
import json

def test_clob_api():
    print("Testing CLOB Price History API...")
    print("Looking for RESOLVED markets (winner determined)...")

    now = datetime.now(timezone.utc)
    cutoff_old = now - timedelta(days=7)  # Not older than 7 days
    cutoff_new = now - timedelta(hours=4)  # At least 4 hours old (to be resolved)

    # Paginate through events to find resolved ones
    offset = 0
    tested = 0
    while tested < 5:
        # Use different query - look for events with resolved outcomes
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

                # Check if outcome is resolved (price is 0 or 1)
                outcome_prices_str = market.get('outcomePrices', '[]')
                try:
                    outcome_prices = json.loads(outcome_prices_str) if isinstance(outcome_prices_str, str) else outcome_prices_str
                except:
                    continue

                if not outcome_prices:
                    continue

                # Check if truly resolved (one outcome at 1.0, others at 0.0)
                parsed = [float(p) for p in outcome_prices]
                if not any(p >= 0.99 for p in parsed):
                    continue  # Not resolved yet

                end_date = market.get('endDate') or event.get('endDate', '')
                if not end_date:
                    continue

                # Parse end date
                try:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                except:
                    continue

                # Skip if too old or too new
                if end_dt < cutoff_old or end_dt > cutoff_new:
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
                print(f'Resolved Prices: {parsed}')
                print(f'Token ID: {token_id[:20]}...')

                # Try to get price history from 24 hours before end
                start_dt = end_dt - timedelta(hours=24)

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
        if offset > 500:
            print("Paginated through 500 events without finding recent resolved markets")
            break

    print(f'\n\nTested {tested} recent resolved markets')

if __name__ == '__main__':
    test_clob_api()
