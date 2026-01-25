#!/usr/bin/env python3
"""
Near-Resolution Scalp Scanner - Forward Testing.

Scans for markets at 95%+ price that will resolve within 2-6 hours.
Tracks outcomes to validate the scalp strategy in real-time.

Usage:
    python -m src.scalp_scanner
"""

import requests
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import time

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SCALP_FILE = os.path.join(DATA_DIR, "scalp_opportunities.json")


def log(msg: str):
    print(f"[SCALP] {datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)


@dataclass
class ScalpOpportunity:
    """A potential scalp trade."""
    market_id: str
    question: str
    outcome: str
    price: float
    end_date: str
    detected_at: str
    token_id: str
    resolved: bool = False
    won: Optional[bool] = None
    resolved_at: Optional[str] = None


def load_opportunities() -> List[Dict]:
    """Load tracked opportunities from file."""
    if os.path.exists(SCALP_FILE):
        try:
            with open(SCALP_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []


def save_opportunities(opps: List[Dict]):
    """Save opportunities to file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCALP_FILE, 'w') as f:
        json.dump(opps, f, indent=2)


def get_active_markets() -> List[Dict]:
    """Fetch active markets from Polymarket."""
    markets = []

    try:
        # Get active events
        url = "https://gamma-api.polymarket.com/events?active=true&limit=100"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            log(f"API error: {r.status_code}")
            return []

        events = r.json()

        for event in events:
            for market in event.get("markets", []):
                if market.get("closed"):
                    continue
                markets.append(market)

        log(f"Fetched {len(markets)} active markets")

    except Exception as e:
        log(f"Error fetching markets: {e}")

    return markets


def find_scalp_opportunities(markets: List[Dict], min_price: float = 0.95, max_hours: float = 6.0) -> List[ScalpOpportunity]:
    """Find markets at 95%+ price resolving within specified hours."""
    opportunities = []
    now = datetime.now(timezone.utc)

    for market in markets:
        end_date = market.get("endDate", "")
        if not end_date:
            continue

        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except:
            continue

        # Check if resolving within timeframe
        hours_until = (end_dt - now).total_seconds() / 3600
        if hours_until < 0.5 or hours_until > max_hours:
            continue

        # Parse outcome prices
        prices_str = market.get("outcomePrices", "[]")
        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
        except:
            continue

        outcomes_str = market.get("outcomes", "[]")
        try:
            outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
        except:
            continue

        clob_ids_str = market.get("clobTokenIds", "[]")
        try:
            clob_ids = json.loads(clob_ids_str) if isinstance(clob_ids_str, str) else clob_ids_str
        except:
            continue

        if not prices or not outcomes or len(prices) != len(outcomes):
            continue

        # Look for outcomes at 95%+
        for i, (outcome, price_str) in enumerate(zip(outcomes, prices)):
            try:
                price = float(price_str)
            except:
                continue

            if price >= min_price:
                token_id = clob_ids[i] if i < len(clob_ids) else ""

                opp = ScalpOpportunity(
                    market_id=market.get("id", ""),
                    question=market.get("question", "Unknown")[:80],
                    outcome=outcome,
                    price=price,
                    end_date=end_date,
                    detected_at=now.isoformat(),
                    token_id=token_id
                )
                opportunities.append(opp)

    return opportunities


def check_resolutions(opportunities: List[Dict]) -> Tuple[List[Dict], int, int]:
    """Check if any tracked opportunities have resolved."""
    updated = []
    wins = 0
    losses = 0

    for opp in opportunities:
        if opp.get("resolved"):
            updated.append(opp)
            if opp.get("won"):
                wins += 1
            else:
                losses += 1
            continue

        # Check if market has resolved
        market_id = opp.get("market_id", "")
        if not market_id:
            updated.append(opp)
            continue

        try:
            url = f"https://gamma-api.polymarket.com/markets/{market_id}"
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                updated.append(opp)
                continue

            market = r.json()

            if not market.get("closed"):
                updated.append(opp)
                continue

            # Market is closed - check outcome
            prices_str = market.get("outcomePrices", "[]")
            try:
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            except:
                updated.append(opp)
                continue

            outcomes_str = market.get("outcomes", "[]")
            try:
                outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
            except:
                updated.append(opp)
                continue

            # Find winning outcome
            winning_outcome = None
            for outcome, price_str in zip(outcomes, prices):
                try:
                    if float(price_str) >= 0.99:
                        winning_outcome = outcome
                        break
                except:
                    pass

            # Did our tracked outcome win?
            tracked_outcome = opp.get("outcome", "")
            won = (tracked_outcome == winning_outcome)

            opp["resolved"] = True
            opp["won"] = won
            opp["resolved_at"] = datetime.now(timezone.utc).isoformat()
            opp["winning_outcome"] = winning_outcome

            if won:
                wins += 1
                log(f"WIN: {opp['question'][:40]}... ({tracked_outcome} @ {opp['price']:.1%})")
            else:
                losses += 1
                log(f"LOSS: {opp['question'][:40]}... ({tracked_outcome} @ {opp['price']:.1%}, winner={winning_outcome})")

            updated.append(opp)
            time.sleep(0.2)  # Rate limit

        except Exception as e:
            log(f"Error checking {market_id}: {e}")
            updated.append(opp)

    return updated, wins, losses


def calculate_stats(opportunities: List[Dict]) -> Dict:
    """Calculate win rate and other stats."""
    resolved = [o for o in opportunities if o.get("resolved")]
    wins = sum(1 for o in resolved if o.get("won"))
    losses = len(resolved) - wins

    # Stats by price tier
    tiers = {
        "95-96%": {"min": 0.95, "max": 0.96, "wins": 0, "losses": 0},
        "96-97%": {"min": 0.96, "max": 0.97, "wins": 0, "losses": 0},
        "97-98%": {"min": 0.97, "max": 0.98, "wins": 0, "losses": 0},
        "98-99%": {"min": 0.98, "max": 0.99, "wins": 0, "losses": 0},
        "99%+": {"min": 0.99, "max": 1.01, "wins": 0, "losses": 0},
    }

    for opp in resolved:
        price = opp.get("price", 0)
        for tier in tiers.values():
            if tier["min"] <= price < tier["max"]:
                if opp.get("won"):
                    tier["wins"] += 1
                else:
                    tier["losses"] += 1
                break

    return {
        "total_tracked": len(opportunities),
        "resolved": len(resolved),
        "pending": len(opportunities) - len(resolved),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(resolved) if resolved else 0,
        "tiers": {name: {
            "count": t["wins"] + t["losses"],
            "wins": t["wins"],
            "win_rate": t["wins"] / (t["wins"] + t["losses"]) if (t["wins"] + t["losses"]) > 0 else 0
        } for name, t in tiers.items()}
    }


def scan_once():
    """Run a single scan cycle."""
    log("=" * 60)
    log("SCALP SCANNER - Forward Testing")
    log("=" * 60)

    # Load existing opportunities
    opportunities = load_opportunities()
    log(f"Loaded {len(opportunities)} tracked opportunities")

    # Check for resolutions
    opportunities, new_wins, new_losses = check_resolutions(opportunities)
    if new_wins or new_losses:
        log(f"New resolutions: {new_wins} wins, {new_losses} losses")

    # Find new opportunities
    markets = get_active_markets()
    new_opps = find_scalp_opportunities(markets)

    # Add new ones (avoid duplicates)
    existing_ids = {(o.get("market_id"), o.get("outcome")) for o in opportunities}
    added = 0
    for opp in new_opps:
        key = (opp.market_id, opp.outcome)
        if key not in existing_ids:
            opportunities.append(asdict(opp))
            existing_ids.add(key)
            added += 1
            log(f"NEW: {opp.question[:50]}... {opp.outcome} @ {opp.price:.1%}")

    if added:
        log(f"Added {added} new opportunities")

    # Calculate and display stats
    stats = calculate_stats(opportunities)

    log("")
    log("=" * 60)
    log("FORWARD TEST STATS")
    log("=" * 60)
    log(f"Total tracked: {stats['total_tracked']}")
    log(f"Resolved: {stats['resolved']} | Pending: {stats['pending']}")
    log(f"Wins: {stats['wins']} | Losses: {stats['losses']}")
    log(f"Win Rate: {stats['win_rate']:.1%}")
    log("")
    log("By Price Tier:")
    for name, tier in stats["tiers"].items():
        if tier["count"] > 0:
            log(f"  {name}: {tier['count']} trades, {tier['win_rate']:.1%} win rate")

    # Save
    save_opportunities(opportunities)
    log(f"\nSaved {len(opportunities)} opportunities to {SCALP_FILE}")

    return stats


def main():
    """Main entry point."""
    scan_once()


if __name__ == "__main__":
    main()
