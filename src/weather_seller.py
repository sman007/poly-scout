#!/usr/bin/env python3
"""
Weather Market Seller - Hans323 Strategy Implementation.

This implements the proven profitable strategy from Hans323:
- SELL No on exact temperature brackets when No price >85%
- Exact brackets rarely hit, so selling No is profitable

Reference: docs/HANS323_WEATHER_STRATEGY.md

Usage:
    python -m src.weather_seller --scan        # Scan for opportunities
    python -m src.weather_seller --paper       # Run paper trading
"""

import argparse
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[WEATHER-SELLER {ts}] {msg}", flush=True)


# Cities from Hans323's trading patterns
CITIES = ["seoul", "london", "wellington"]

# Strategy parameters from Hans323's documented approach
# Hans323: 86% of trades enter at prices >90%
MIN_NO_PRICE = 0.90      # Only sell No when price >= 90% (Hans323's threshold)
MAX_YES_PRICE = 0.10     # Equivalent: Yes <= 10%
MIN_VOLUME = 500         # Minimum volume for liquidity
POSITION_SIZE_USD = 1000 # Hans323 uses $1,000-$7,800 per position


@dataclass
class SellOpportunity:
    """A SELL No opportunity in weather markets."""
    city: str
    date: str
    bracket: str
    bracket_type: str  # 'exact', 'or_higher', 'or_lower'
    yes_price: float
    no_price: float
    volume: float
    condition_id: str
    token_id: str
    slug: str

    @property
    def edge_pct(self) -> float:
        """Estimated edge: No price - true probability of not hitting."""
        # For exact brackets, true probability of NOT hitting is ~85-90%
        # If we sell No at 93%, edge is 93% - 87% = 6%
        # Conservative estimate: No rarely hits, so our true prob is ~85%
        true_no_prob = 0.87 if self.bracket_type == "exact" else 0.80
        return (self.no_price - true_no_prob) * 100


@dataclass
class PaperPosition:
    """A paper trading position."""
    id: str
    opportunity: SellOpportunity
    side: str  # Always "SELL_NO"
    shares: float
    entry_price: float
    cost: float
    opened_at: str
    status: str  # 'open', 'won', 'lost'
    pnl: Optional[float] = None
    closed_at: Optional[str] = None


def fetch_weather_markets(days_ahead: int = 2) -> List[Dict]:
    """Fetch all weather market brackets from Polymarket."""
    markets = []

    for city in CITIES:
        for day_offset in range(days_ahead + 1):
            date = datetime.now() + timedelta(days=day_offset)
            month = date.strftime("%B").lower()
            day = date.day
            date_str = date.strftime("%Y-%m-%d")

            slug = f"highest-temperature-in-{city}-on-{month}-{day}"

            try:
                r = requests.get(
                    f"https://gamma-api.polymarket.com/events/slug/{slug}",
                    timeout=15
                )

                if r.status_code != 200:
                    continue

                event = r.json()

                for m in event.get("markets", []):
                    title = m.get("groupItemTitle", "")
                    if not title:
                        continue

                    # Parse bracket type
                    if "or below" in title.lower():
                        bracket_type = "or_lower"
                    elif "or higher" in title.lower():
                        bracket_type = "or_higher"
                    else:
                        bracket_type = "exact"

                    # Parse prices
                    try:
                        prices = json.loads(m.get("outcomePrices", "[0.5,0.5]"))
                        yes_price = float(prices[0])
                        no_price = 1 - yes_price
                    except:
                        continue

                    volume = float(m.get("volume", 0) or 0)

                    # Get token IDs for trading
                    tokens = m.get("clobTokenIds", "")
                    if isinstance(tokens, str):
                        try:
                            tokens = json.loads(tokens)
                        except:
                            tokens = []

                    no_token = tokens[1] if len(tokens) > 1 else ""

                    markets.append({
                        "city": city,
                        "date": date_str,
                        "bracket": title,
                        "bracket_type": bracket_type,
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "volume": volume,
                        "condition_id": m.get("conditionId", ""),
                        "token_id": no_token,
                        "slug": slug
                    })

            except Exception as e:
                log(f"Error fetching {slug}: {e}")

    return markets


def find_sell_opportunities(min_no_price: float = MIN_NO_PRICE) -> List[SellOpportunity]:
    """
    Find SELL No opportunities matching Hans323's criteria.

    Target: Exact brackets with No price >85%
    """
    markets = fetch_weather_markets()
    opportunities = []

    for m in markets:
        # Hans323 criteria:
        # 1. Prefer exact brackets (79% of his trades)
        # 2. No price >= 85%
        # 3. Some volume/liquidity

        if m["no_price"] < min_no_price:
            continue

        if m["yes_price"] <= 0.005:  # Already settled or no market
            continue

        if m["volume"] < MIN_VOLUME:
            continue

        # Prefer exact brackets like Hans323 (79% of trades)
        if m["bracket_type"] != "exact":
            continue

        opp = SellOpportunity(
            city=m["city"],
            date=m["date"],
            bracket=m["bracket"],
            bracket_type=m["bracket_type"],
            yes_price=m["yes_price"],
            no_price=m["no_price"],
            volume=m["volume"],
            condition_id=m["condition_id"],
            token_id=m["token_id"],
            slug=m["slug"]
        )
        opportunities.append(opp)

    # Sort by No price descending (highest premium first)
    opportunities.sort(key=lambda x: x.no_price, reverse=True)

    return opportunities


class WeatherSellerPaperTrader:
    """Paper trading implementation for weather seller strategy."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.portfolio_file = self.data_dir / "weather_seller_portfolio.json"
        self.positions: List[PaperPosition] = []
        self.closed_trades: List[PaperPosition] = []
        self.balance = 1000.0  # Starting paper balance
        self._load_portfolio()

    def _load_portfolio(self):
        """Load existing portfolio from disk."""
        if self.portfolio_file.exists():
            try:
                with open(self.portfolio_file) as f:
                    data = json.load(f)
                    self.balance = data.get("balance", 1000.0)
                    self.positions = [
                        PaperPosition(**p) if isinstance(p.get("opportunity"), dict)
                        else p
                        for p in data.get("positions", [])
                    ]
                    # Convert opportunity dicts back to dataclass
                    for i, p in enumerate(self.positions):
                        if isinstance(p, dict):
                            opp_dict = p["opportunity"]
                            p["opportunity"] = SellOpportunity(**opp_dict)
                            self.positions[i] = PaperPosition(**p)
                        elif isinstance(p.opportunity, dict):
                            p.opportunity = SellOpportunity(**p.opportunity)

                    self.closed_trades = data.get("closed_trades", [])
            except Exception as e:
                log(f"Error loading portfolio: {e}")

    def _save_portfolio(self):
        """Save portfolio to disk."""
        data = {
            "balance": self.balance,
            "positions": [
                {**asdict(p), "opportunity": asdict(p.opportunity)}
                for p in self.positions
            ],
            "closed_trades": self.closed_trades,
            "updated_at": datetime.now().isoformat()
        }
        with open(self.portfolio_file, "w") as f:
            json.dump(data, f, indent=2)

    def open_position(self, opp: SellOpportunity, size_usd: float = POSITION_SIZE_USD) -> Optional[PaperPosition]:
        """
        Open a SELL No position (paper trade).

        SELL No means:
        - We receive premium upfront (No price * shares)
        - If bracket DOESN'T hit: We keep the premium (profit)
        - If bracket HITS: We lose (pay out $1 per share)
        """
        if size_usd > self.balance:
            log(f"Insufficient balance: ${self.balance:.2f} < ${size_usd:.2f}")
            return None

        # When selling No:
        # - We sell shares at No price
        # - Shares = size / no_price
        # - If we win (No wins), we profit the premium
        # - If we lose (Yes wins), we lose the position

        shares = size_usd / opp.no_price

        position = PaperPosition(
            id=f"{opp.city}_{opp.date}_{opp.bracket}_{datetime.now().strftime('%H%M%S')}",
            opportunity=opp,
            side="SELL_NO",
            shares=shares,
            entry_price=opp.no_price,
            cost=size_usd,
            opened_at=datetime.now().isoformat(),
            status="open"
        )

        self.balance -= size_usd
        self.positions.append(position)
        self._save_portfolio()

        log(f"OPENED: SELL {shares:.1f} No @ {opp.no_price*100:.1f}% on {opp.city.upper()} {opp.bracket}")
        log(f"  Cost: ${size_usd:.2f} | Balance: ${self.balance:.2f}")

        return position

    def resolve_position(self, position: PaperPosition, bracket_hit: bool):
        """
        Resolve a position based on whether the bracket hit.

        SELL No strategy:
        - If bracket DOESN'T hit (No wins): We profit
        - If bracket HITS (Yes wins): We lose
        """
        if bracket_hit:
            # Yes won - we lose our position
            position.status = "lost"
            position.pnl = -position.cost
            log(f"LOST: {position.opportunity.bracket} hit! Lost ${position.cost:.2f}")
        else:
            # No won - we keep the premium
            payout = position.shares * 1.0  # $1 per share
            position.pnl = payout - position.cost
            position.status = "won"
            self.balance += payout
            log(f"WON: {position.opportunity.bracket} didn't hit! Profit ${position.pnl:.2f}")

        position.closed_at = datetime.now().isoformat()
        self.positions.remove(position)
        self.closed_trades.append(asdict(position))
        self._save_portfolio()

    def get_stats(self) -> Dict:
        """Get trading statistics."""
        total_trades = len(self.closed_trades)
        wins = sum(1 for t in self.closed_trades if t.get("status") == "won")
        losses = total_trades - wins

        total_pnl = sum(t.get("pnl", 0) for t in self.closed_trades)

        open_value = sum(p.cost for p in self.positions)

        return {
            "balance": self.balance,
            "open_positions": len(self.positions),
            "open_value": open_value,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / total_trades if total_trades > 0 else 0,
            "total_pnl": total_pnl
        }

    def print_status(self):
        """Print current trading status."""
        stats = self.get_stats()

        log("=" * 60)
        log("WEATHER SELLER - Hans323 Strategy Paper Trading")
        log("=" * 60)
        log(f"Balance: ${stats['balance']:.2f}")
        log(f"Open Positions: {stats['open_positions']} (${stats['open_value']:.2f})")
        log(f"Total Trades: {stats['total_trades']}")
        log(f"Win Rate: {stats['win_rate']:.1%} ({stats['wins']}/{stats['total_trades']})")
        log(f"Total P&L: ${stats['total_pnl']:+.2f}")
        log("=" * 60)

        if self.positions:
            log("\nOpen Positions:")
            for p in self.positions:
                log(f"  {p.opportunity.city.upper()} {p.opportunity.bracket}")
                log(f"    SELL No @ {p.entry_price*100:.1f}% | Cost: ${p.cost:.2f}")


def scan_and_display():
    """Scan for opportunities and display them."""
    log("Scanning for SELL No opportunities...")
    log(f"Criteria: No price >= {MIN_NO_PRICE*100:.0f}%, exact brackets, volume >= ${MIN_VOLUME}")
    log("")

    opportunities = find_sell_opportunities()

    if not opportunities:
        log("No opportunities found matching criteria")
        return

    log(f"Found {len(opportunities)} opportunities:\n")

    for opp in opportunities:
        log(f"  {opp.city.upper()} {opp.date}")
        log(f"    Bracket: {opp.bracket}")
        log(f"    Prices: Yes={opp.yes_price*100:.1f}% No={opp.no_price*100:.1f}%")
        log(f"    Volume: ${opp.volume:,.0f}")
        log(f"    Edge (est): {opp.edge_pct:+.1f}%")
        log("")


def run_paper_trading():
    """Run paper trading session."""
    trader = WeatherSellerPaperTrader()
    trader.print_status()

    log("\nScanning for new opportunities...")
    opportunities = find_sell_opportunities()

    if opportunities:
        log(f"Found {len(opportunities)} opportunities")

        # Only open positions if we have balance and not too many open
        max_positions = 5
        if len(trader.positions) >= max_positions:
            log(f"Already have {len(trader.positions)} open positions (max {max_positions})")
            return

        # Check if we already have a position in this market
        existing_markets = {
            f"{p.opportunity.city}_{p.opportunity.date}_{p.opportunity.bracket}"
            for p in trader.positions
        }

        for opp in opportunities:
            market_key = f"{opp.city}_{opp.date}_{opp.bracket}"
            if market_key in existing_markets:
                continue

            if trader.balance < POSITION_SIZE_USD:
                log("Insufficient balance for new positions")
                break

            trader.open_position(opp)
            break  # Only one new position per scan
    else:
        log("No new opportunities found")

    trader.print_status()


def main():
    parser = argparse.ArgumentParser(description="Weather Market Seller - Hans323 Strategy")
    parser.add_argument("--scan", action="store_true", help="Scan and display opportunities")
    parser.add_argument("--paper", action="store_true", help="Run paper trading")
    parser.add_argument("--status", action="store_true", help="Show current status")

    args = parser.parse_args()

    if args.scan:
        scan_and_display()
    elif args.paper:
        run_paper_trading()
    elif args.status:
        trader = WeatherSellerPaperTrader()
        trader.print_status()
    else:
        # Default: scan
        scan_and_display()


if __name__ == "__main__":
    main()
