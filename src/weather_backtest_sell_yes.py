#!/usr/bin/env python3
"""
Weather Market Backtest - SELL YES Strategy.

Tests the strategy of SELLING Yes on exact temperature brackets.
Since exact temps almost never hit, Yes is almost always worthless,
so SELL Yes should have near-100% win rate with small per-trade profit.

Usage:
    python -m src.weather_backtest_sell_yes --days 30 --balance 1000
"""

import argparse
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
import random

from src.weather_scanner import WEATHER_CITIES


def log(msg: str):
    print(f"[BACKTEST] {msg}", flush=True)


# Position sizing for SELL Yes
SHARES_PER_TRADE = 100  # Sell 100 shares per trade
COLLATERAL_PER_SHARE = 1.0  # $1 collateral per share (max loss)


@dataclass
class SellYesTrade:
    """A SELL Yes trade."""
    city: str
    date: str
    bracket_temp: int
    yes_price: float  # Price we sell Yes at (premium received)
    shares: int
    collateral: float  # Total collateral posted
    premium_received: float  # Total premium received
    actual_temp: Optional[float] = None
    won: Optional[bool] = None
    pnl: Optional[float] = None


class WeatherSellYesBacktest:
    """Backtest for SELL Yes on exact temperature brackets."""

    def __init__(self, starting_balance: float = 1000.0):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.trades: List[SellYesTrade] = []

    def run_backtest(self, days_back: int = 30):
        """Run backtest over past N days."""
        cities = ["seoul", "london", "wellington"]

        log("=" * 60)
        log("SELL YES ON EXACT BRACKETS BACKTEST")
        log("=" * 60)
        log(f"Strategy: SELL Yes on exact temperature brackets")
        log(f"Rationale: Exact temps almost never hit, so Yes → $0")
        log(f"Starting Balance: ${self.starting_balance:,.2f}")
        log(f"Days: {days_back}")
        log("=" * 60)

        for day_offset in range(days_back, 0, -1):
            test_date = datetime.now() - timedelta(days=day_offset)
            date_str = test_date.strftime("%Y-%m-%d")

            for city in cities:
                # Get actual high temp for this day
                actual_temp = self._get_actual_temperature(city, date_str)
                if actual_temp is None:
                    continue

                # Simulate the forecast from that morning (add noise)
                forecast_temp = actual_temp + random.gauss(0, 2.5)

                # Generate exact bracket prices based on forecast
                # The market would price exact brackets at 1-5% based on uncertainty
                bracket_temp = int(round(forecast_temp))

                # Simulate Yes price for exact bracket (typically 1-5%)
                # Use distance from forecast to estimate market price
                distance = abs(actual_temp - bracket_temp)
                if distance < 0.5:
                    yes_price = 0.15  # High probability (close to forecast)
                elif distance < 1.5:
                    yes_price = 0.08
                elif distance < 2.5:
                    yes_price = 0.03
                else:
                    yes_price = 0.01  # Very unlikely

                # Add market noise
                yes_price = max(0.01, min(0.30, yes_price + random.gauss(0, 0.02)))

                # Check if we can afford this trade
                collateral_needed = SHARES_PER_TRADE * COLLATERAL_PER_SHARE
                premium_received = SHARES_PER_TRADE * yes_price

                if collateral_needed > self.balance:
                    continue  # Can't afford

                # Execute SELL Yes trade
                self.balance -= collateral_needed
                self.balance += premium_received  # Receive premium upfront

                trade = SellYesTrade(
                    city=city,
                    date=date_str,
                    bracket_temp=bracket_temp,
                    yes_price=yes_price,
                    shares=SHARES_PER_TRADE,
                    collateral=collateral_needed,
                    premium_received=premium_received,
                    actual_temp=actual_temp
                )

                # Resolve immediately
                self._resolve_trade(trade)
                self.trades.append(trade)

        return self._generate_report()

    def _get_actual_temperature(self, city: str, date_str: str) -> Optional[float]:
        """Get actual recorded temperature from Open-Meteo archive."""
        if city not in WEATHER_CITIES:
            return None

        coords = WEATHER_CITIES[city]

        try:
            url = (
                f"https://archive-api.open-meteo.com/v1/archive?"
                f"latitude={coords['lat']}&longitude={coords['lon']}"
                f"&start_date={date_str}&end_date={date_str}"
                f"&daily=temperature_2m_max"
                f"&timezone={coords['tz']}"
            )

            r = requests.get(url, timeout=10)
            data = r.json()

            if "daily" in data and data["daily"].get("temperature_2m_max"):
                temp = data["daily"]["temperature_2m_max"][0]
                if temp is not None:
                    return float(temp)

        except Exception as e:
            log(f"Error fetching archive for {city}: {e}")

        return None

    def _resolve_trade(self, trade: SellYesTrade):
        """Resolve a SELL Yes trade based on actual temperature."""
        # Did the exact bracket hit?
        bracket_hit = (round(trade.actual_temp) == trade.bracket_temp)

        if bracket_hit:
            # Yes wins - we owe $1/share to Yes holders
            # We lose: collateral - premium_received
            trade.won = False
            payout = trade.shares * 1.0
            trade.pnl = trade.premium_received - payout  # Negative
            # We already received premium, now pay out collateral
            # Balance adjustment: we get back nothing (collateral pays out)
        else:
            # No wins - Yes is worthless, we keep premium
            trade.won = True
            trade.pnl = trade.premium_received
            # We get our collateral back
            self.balance += trade.collateral

    def _generate_report(self) -> Dict:
        """Generate backtest report."""
        log("\n" + "=" * 60)
        log("BACKTEST RESULTS")
        log("=" * 60)

        total_trades = len(self.trades)
        if total_trades == 0:
            log("No trades executed!")
            return {}

        wins = sum(1 for t in self.trades if t.won)
        losses = total_trades - wins
        win_rate = wins / total_trades

        total_pnl = sum(t.pnl for t in self.trades)
        avg_win = sum(t.pnl for t in self.trades if t.won) / max(wins, 1)
        avg_loss = sum(t.pnl for t in self.trades if not t.won) / max(losses, 1)

        return_pct = (total_pnl / self.starting_balance) * 100

        # Profit factor
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        log(f"Total Trades: {total_trades}")
        log(f"Win Rate: {win_rate:.1%} ({wins}/{total_trades})")
        log(f"")
        log(f"Total P&L: ${total_pnl:+.2f} ({return_pct:+.1f}%)")
        log(f"Avg Win: ${avg_win:.2f}")
        log(f"Avg Loss: ${avg_loss:.2f}")
        log(f"Profit Factor: {profit_factor:.2f}")
        log(f"")
        log(f"Starting Balance: ${self.starting_balance:,.2f}")
        log(f"Final Balance: ${self.balance:,.2f}")
        log("=" * 60)

        # Sample of losing trades (when exact bracket hit)
        losers = [t for t in self.trades if not t.won]
        if losers:
            log(f"\nLOSING TRADES ({len(losers)} total):")
            for t in losers[:10]:
                log(f"  {t.city.upper()} {t.date}: Bracket {t.bracket_temp}C, "
                    f"Actual {t.actual_temp:.1f}C (rounded={round(t.actual_temp)}C), "
                    f"P&L: ${t.pnl:.2f}")

        # Win rate by city
        log("\nBy City:")
        for city in ["seoul", "london", "wellington"]:
            city_trades = [t for t in self.trades if t.city == city]
            city_wins = sum(1 for t in city_trades if t.won)
            city_pnl = sum(t.pnl for t in city_trades)
            if city_trades:
                wr = city_wins / len(city_trades)
                log(f"  {city.upper()}: {len(city_trades)} trades, "
                    f"WR: {wr:.1%}, P&L: ${city_pnl:+.2f}")

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "final_balance": self.balance
        }


def main():
    parser = argparse.ArgumentParser(description="Weather SELL Yes Backtest")
    parser.add_argument("--days", type=int, default=30, help="Days to backtest")
    parser.add_argument("--balance", type=float, default=1000.0, help="Starting balance")
    args = parser.parse_args()

    backtest = WeatherSellYesBacktest(starting_balance=args.balance)
    report = backtest.run_backtest(days_back=args.days)

    return report


if __name__ == "__main__":
    main()
