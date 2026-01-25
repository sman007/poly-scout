#!/usr/bin/env python3
"""
Near-Resolution Scalp Strategy Backtest.

Tests the strategy of buying outcomes priced at 95%+ shortly before resolution.
The premise: if something is 95%+ likely, it usually wins.

Uses Polymarket's resolved events to calculate actual win rates.

Usage:
    python -m src.scalp_backtest --days 30
"""

import argparse
import requests
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
import time


def log(msg: str):
    print(f"[SCALP] {msg}", flush=True)


class ScalpBacktest:
    """Backtest near-resolution scalp strategy using resolved PM events."""

    def __init__(self, starting_balance: float = 1000.0):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.trades = []

    def fetch_resolved_events(self, days_back: int = 30, limit: int = 500) -> List[Dict]:
        """Fetch recently resolved events from Polymarket."""
        events = []
        offset = 0

        log(f"Fetching resolved events from past {days_back} days...")

        while len(events) < limit:
            url = f"https://gamma-api.polymarket.com/events?closed=true&limit=100&offset={offset}"

            try:
                r = requests.get(url, timeout=30)
                if r.status_code != 200:
                    log(f"API error: {r.status_code}")
                    break

                data = r.json()
                if not data:
                    break

                # Filter by date
                cutoff = datetime.now() - timedelta(days=days_back)
                for event in data:
                    end_date = event.get("endDate", "")
                    if end_date:
                        try:
                            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                            if end_dt.replace(tzinfo=None) >= cutoff:
                                events.append(event)
                        except:
                            pass

                log(f"  Fetched {len(data)} events (total qualifying: {len(events)})")

                if len(data) < 100:
                    break

                offset += 100
                time.sleep(0.3)

            except Exception as e:
                log(f"Error fetching events: {e}")
                break

        return events[:limit]

    def analyze_event(self, event: Dict) -> List[Dict]:
        """Analyze a resolved event for scalp opportunities."""
        opportunities = []

        markets = event.get("markets", [])
        for market in markets:
            if not market.get("closed"):
                continue

            # Get outcome prices at close
            outcome_prices_str = market.get("outcomePrices", "[]")
            try:
                outcome_prices = json.loads(outcome_prices_str) if isinstance(outcome_prices_str, str) else outcome_prices_str
            except:
                continue

            outcomes_str = market.get("outcomes", "[]")
            try:
                outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
            except:
                continue

            # Get winning outcome
            winning_outcome = market.get("winningOutcome")

            if not outcome_prices or not outcomes:
                continue

            # Check each outcome
            for i, (outcome, price_str) in enumerate(zip(outcomes, outcome_prices)):
                try:
                    price = float(price_str)
                except:
                    continue

                # Only interested in high-probability outcomes (95%+)
                if price >= 0.95:
                    won = (outcome == winning_outcome)
                    opportunities.append({
                        "event_title": event.get("title", "Unknown"),
                        "market_question": market.get("question", "Unknown"),
                        "outcome": outcome,
                        "price": price,
                        "won": won,
                        "winning_outcome": winning_outcome,
                        "market_slug": market.get("slug", "")
                    })

        return opportunities

    def run_backtest(self, days_back: int = 30) -> Dict:
        """Run the scalp backtest."""
        log("=" * 70)
        log("NEAR-RESOLUTION SCALP BACKTEST")
        log("=" * 70)
        log(f"Strategy: Buy outcomes priced at 95%+ before resolution")
        log(f"Days back: {days_back}")
        log(f"Starting balance: ${self.starting_balance:,.2f}")
        log("=" * 70)

        # Fetch resolved events
        events = self.fetch_resolved_events(days_back=days_back)
        log(f"\nAnalyzing {len(events)} resolved events...")

        # Analyze each event
        all_opportunities = []
        for event in events:
            opps = self.analyze_event(event)
            all_opportunities.extend(opps)

        log(f"Found {len(all_opportunities)} outcomes that were priced 95%+")

        if not all_opportunities:
            log("No qualifying opportunities found!")
            return {}

        # Calculate statistics by price tier
        tiers = {
            "95-96%": {"min": 0.95, "max": 0.96, "trades": []},
            "96-97%": {"min": 0.96, "max": 0.97, "trades": []},
            "97-98%": {"min": 0.97, "max": 0.98, "trades": []},
            "98-99%": {"min": 0.98, "max": 0.99, "trades": []},
            "99%+": {"min": 0.99, "max": 1.01, "trades": []},
        }

        for opp in all_opportunities:
            price = opp["price"]
            for tier_name, tier in tiers.items():
                if tier["min"] <= price < tier["max"]:
                    tier["trades"].append(opp)
                    break

        # Report by tier
        log("\n" + "=" * 70)
        log("RESULTS BY PRICE TIER")
        log("=" * 70)

        total_wins = 0
        total_trades = 0

        for tier_name, tier in tiers.items():
            trades = tier["trades"]
            if not trades:
                continue

            wins = sum(1 for t in trades if t["won"])
            losses = len(trades) - wins
            win_rate = wins / len(trades) if trades else 0

            total_wins += wins
            total_trades += len(trades)

            # Calculate expected value
            avg_price = sum(t["price"] for t in trades) / len(trades)
            # If we buy at avg_price and win, we get $1. If we lose, we get $0.
            ev_per_trade = (win_rate * 1.0) - avg_price
            ev_pct = ev_per_trade / avg_price * 100

            log(f"\n{tier_name}:")
            log(f"  Trades: {len(trades)}")
            log(f"  Wins: {wins} | Losses: {losses}")
            log(f"  Win Rate: {win_rate:.1%}")
            log(f"  Avg Entry Price: ${avg_price:.4f}")
            log(f"  EV per Trade: ${ev_per_trade:.4f} ({ev_pct:+.2f}%)")

            # Show some losing trades for this tier
            losers = [t for t in trades if not t["won"]]
            if losers:
                log(f"  Sample losses:")
                for l in losers[:3]:
                    log(f"    - {l['outcome']} @ {l['price']:.1%} (winner: {l['winning_outcome']})")

        # Overall summary
        overall_win_rate = total_wins / total_trades if total_trades > 0 else 0

        log("\n" + "=" * 70)
        log("OVERALL SUMMARY")
        log("=" * 70)
        log(f"Total trades analyzed: {total_trades}")
        log(f"Total wins: {total_wins}")
        log(f"Total losses: {total_trades - total_wins}")
        log(f"Overall Win Rate: {overall_win_rate:.1%}")

        # Simulate P&L with $100 per trade
        bet_size = 100
        simulated_pnl = 0
        for opp in all_opportunities:
            shares = bet_size / opp["price"]
            if opp["won"]:
                payout = shares * 1.0
                pnl = payout - bet_size
            else:
                pnl = -bet_size
            simulated_pnl += pnl

        roi = simulated_pnl / (bet_size * total_trades) * 100 if total_trades > 0 else 0

        log(f"\nSimulated P&L (${bet_size}/trade):")
        log(f"  Total invested: ${bet_size * total_trades:,.2f}")
        log(f"  Total P&L: ${simulated_pnl:,.2f}")
        log(f"  ROI: {roi:+.2f}%")

        # Conclusion
        log("\n" + "=" * 70)
        log("CONCLUSION")
        log("=" * 70)

        if overall_win_rate >= 0.95:
            log("WIN RATE 95%+ - Strategy is VIABLE for small bankroll")
            log("Recommend: Focus on 98%+ tier for safest returns")
        elif overall_win_rate >= 0.90:
            log("WIN RATE 90-95% - Strategy is MODERATELY VIABLE")
            log("Recommend: Use strict position sizing, focus on higher tiers")
        else:
            log(f"WIN RATE {overall_win_rate:.1%} - BELOW expectations")
            log("The 95%+ favorites don't win as often as priced!")

        return {
            "total_trades": total_trades,
            "total_wins": total_wins,
            "overall_win_rate": overall_win_rate,
            "simulated_pnl": simulated_pnl,
            "roi": roi,
            "tiers": {name: {"count": len(t["trades"]), "win_rate": sum(1 for x in t["trades"] if x["won"])/len(t["trades"]) if t["trades"] else 0} for name, t in tiers.items()}
        }


def main():
    parser = argparse.ArgumentParser(description="Scalp Strategy Backtest")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    parser.add_argument("--balance", type=float, default=1000.0, help="Starting balance")
    args = parser.parse_args()

    backtest = ScalpBacktest(starting_balance=args.balance)
    results = backtest.run_backtest(days_back=args.days)

    return results


if __name__ == "__main__":
    main()
