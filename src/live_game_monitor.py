#!/usr/bin/env python3
"""
Live Game Monitor - Peter 77777 Style Scalp Alerts

Monitors specific markets during live games for 95%+ price spikes.
Run during game time for real-time alerts.

Usage:
    python -m src.live_game_monitor
"""

import requests
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import sys

# Market IDs to monitor (found via gamma API)
MONITORED_MARKETS = {
    "540256": {
        "name": "Patriots AFC Championship",
        "team": "Patriots",
        "outcome": "Yes"
    },
    "540266": {
        "name": "Broncos AFC Championship",
        "team": "Broncos",
        "outcome": "Yes"
    }
}

# Alert threshold
ALERT_THRESHOLD = 0.95

def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime('%H:%M:%S')
    prefix = "🚨" if level == "ALERT" else "📊"
    print(f"[{timestamp}] {prefix} {msg}", flush=True)

def get_market_prices(market_id: str) -> Optional[Dict]:
    """Fetch current prices for a market."""
    try:
        url = f"https://gamma-api.polymarket.com/markets/{market_id}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        log(f"Error fetching {market_id}: {e}", "ERROR")
        return None

def check_markets() -> List[Dict]:
    """Check all monitored markets for scalp opportunities."""
    alerts = []

    for market_id, info in MONITORED_MARKETS.items():
        market = get_market_prices(market_id)
        if not market:
            continue

        prices_str = market.get("outcomePrices", "[]")
        outcomes_str = market.get("outcomes", "[]")

        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
        except:
            continue

        for outcome, price_str in zip(outcomes, prices):
            try:
                price = float(price_str)
            except:
                continue

            # Check if this outcome is above threshold
            if price >= ALERT_THRESHOLD:
                alerts.append({
                    "market": info["name"],
                    "outcome": outcome,
                    "price": price,
                    "market_id": market_id
                })

            # Log current prices
            log(f"{info['name']}: {outcome} @ {price:.1%}")

    return alerts

def run_monitor(interval_seconds: int = 30):
    """Run continuous monitoring loop."""
    log("=" * 60)
    log("LIVE GAME MONITOR - Peter 77777 Style")
    log(f"Threshold: {ALERT_THRESHOLD:.0%} | Interval: {interval_seconds}s")
    log("=" * 60)
    log("")
    log("Monitoring markets:")
    for mid, info in MONITORED_MARKETS.items():
        log(f"  - {info['name']} (ID: {mid})")
    log("")
    log("Waiting for prices to hit threshold...")
    log("")

    alert_history = set()  # Track alerts we've already sent

    while True:
        try:
            alerts = check_markets()

            for alert in alerts:
                key = f"{alert['market_id']}_{alert['outcome']}"
                if key not in alert_history:
                    log("=" * 40, "ALERT")
                    log(f"🚨 SCALP OPPORTUNITY DETECTED! 🚨", "ALERT")
                    log(f"Market: {alert['market']}", "ALERT")
                    log(f"Outcome: {alert['outcome']} @ {alert['price']:.1%}", "ALERT")
                    log(f"Expected profit: {(1 - alert['price']) * 100:.1f}%", "ALERT")
                    log("=" * 40, "ALERT")
                    alert_history.add(key)

            log("")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            log("Monitor stopped by user")
            break
        except Exception as e:
            log(f"Error in monitor loop: {e}")
            time.sleep(interval_seconds)

def find_championship_markets():
    """Find current NFL Championship market IDs."""
    log("Searching for NFL Championship markets...")

    try:
        url = "https://gamma-api.polymarket.com/markets?closed=false&limit=500"
        r = requests.get(url, timeout=30)
        data = r.json()

        championship_markets = []
        for m in data:
            q = m.get("question", "").lower()
            if "championship" in q and ("nfc" in q or "afc" in q):
                prices = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
                outcomes = json.loads(m.get("outcomes", "[]")) if isinstance(m.get("outcomes"), str) else m.get("outcomes", [])

                championship_markets.append({
                    "id": m.get("id"),
                    "question": m.get("question", "?")[:60],
                    "outcomes": list(zip(outcomes, [float(p) for p in prices]))
                })

        log(f"Found {len(championship_markets)} championship markets:")
        for m in championship_markets[:10]:
            log(f"  ID: {m['id']}")
            log(f"  Q: {m['question']}")
            for o, p in m['outcomes']:
                log(f"    {o}: {p:.1%}")
            log("")

    except Exception as e:
        log(f"Error: {e}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--find":
        find_championship_markets()
    else:
        run_monitor(interval_seconds=30)

if __name__ == "__main__":
    main()
