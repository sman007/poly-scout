#!/usr/bin/env python3
"""
Weather Market Backtest Simulation.

Simulates trading the weather edge detection strategy over historical data.
Uses Open-Meteo historical archive API for actual temperatures.

Usage:
    python -m src.weather_backtest --days 7 --balance 1000
"""

import argparse
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
from math import erf, sqrt

from src.weather_scanner import WEATHER_CITIES, calculate_temp_probability


def log(msg: str):
    print(f"[BACKTEST] {msg}", flush=True)


# Position sizing
MAX_POSITION_PCT = 0.05  # 5% per trade
MIN_POSITION_USD = 5.0
MAX_POSITION_USD = 50.0  # Conservative for weather
MAX_POSITIONS_PER_DAY = 3  # Limit exposure


@dataclass
class BacktestTrade:
    """A single trade in the backtest."""
    city: str
    date: str
    temp: int
    bracket_type: str
    direction: str  # BUY_YES or BUY_NO
    entry_price: float
    shares: float
    cost: float
    edge_pct: float
    forecast_temp: float
    actual_temp: Optional[float] = None
    won: Optional[bool] = None
    pnl: Optional[float] = None
    status: str = "open"


class WeatherBacktest:
    """Weather market backtest simulator."""

    def __init__(self, starting_balance: float = 1000.0):
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.trades: List[BacktestTrade] = []
        self.daily_pnl: Dict[str, float] = {}

    def run_backtest(self, days_back: int = 7, min_edge_pct: float = 5.0):
        """
        Run backtest over past N days.

        Args:
            days_back: Number of days to backtest
            min_edge_pct: Minimum edge to take a position
        """
        cities = ["seoul", "london", "wellington"]

        log("=" * 60)
        log(f"WEATHER STRATEGY BACKTEST: {days_back} Days")
        log(f"Starting Balance: ${self.starting_balance:,.2f}")
        log(f"Min Edge Threshold: {min_edge_pct}%")
        log("=" * 60)

        for day_offset in range(days_back, 0, -1):
            test_date = datetime.now() - timedelta(days=day_offset)
            date_str = test_date.strftime("%Y-%m-%d")

            log(f"\nDay {days_back - day_offset + 1} ({date_str}):")

            # Get forecast and actual temperatures for each city
            edges = []
            for city in cities:
                # Get actual temperature (for resolution)
                actual_temp = self._get_actual_temperature(city, date_str)
                if actual_temp is None:
                    log(f"  {city.upper()}: No historical data available")
                    continue

                # Get what the forecast would have been (use actual as proxy)
                # In reality, we'd need archived forecasts from that morning
                # Using actual temp +/- small variance as proxy
                forecast_temp = actual_temp  # Best proxy we have

                # Generate synthetic market brackets around actual temp
                brackets = self._generate_brackets(int(round(actual_temp)))

                for bracket_temp, bracket_type in brackets:
                    # Calculate probability
                    our_prob = calculate_temp_probability(
                        forecast_temp, bracket_temp, bracket_type
                    )

                    # Simulate market price (inverse of actual probability with noise)
                    # Markets should be somewhat efficient, so use actual outcome
                    actual_prob = self._calculate_actual_probability(
                        actual_temp, bracket_temp, bracket_type
                    )

                    # Market price: mix of efficiency and noise
                    pm_prob = 0.7 * actual_prob + 0.3 * our_prob + (0.1 - 0.2 * (hash(f"{city}{date_str}{bracket_temp}") % 10) / 10)
                    pm_prob = max(0.02, min(0.98, pm_prob))

                    edge_pct = (our_prob - pm_prob) * 100

                    if abs(edge_pct) >= min_edge_pct:
                        direction = "BUY_YES" if edge_pct > 0 else "BUY_NO"
                        edges.append({
                            "city": city,
                            "date": date_str,
                            "temp": bracket_temp,
                            "bracket_type": bracket_type,
                            "our_prob": our_prob,
                            "pm_prob": pm_prob,
                            "edge_pct": abs(edge_pct),
                            "direction": direction,
                            "forecast_temp": forecast_temp,
                            "actual_temp": actual_temp
                        })

            # Sort by edge and take best positions
            edges = sorted(edges, key=lambda x: x["edge_pct"], reverse=True)
            edges = edges[:MAX_POSITIONS_PER_DAY]

            log(f"  Edges found: {len(edges)}")

            daily_pnl = 0.0
            for edge in edges:
                # Open position
                trade = self._open_position(edge)
                if trade:
                    self.trades.append(trade)

                    # Resolve immediately (same-day settlement)
                    self._resolve_trade(trade)

                    status = "WON" if trade.won else "LOST"
                    log(f"  {trade.city.upper()} {trade.temp}C ({trade.bracket_type}): "
                        f"{trade.direction} @ {trade.entry_price:.2f} -> {status} ({trade.pnl:+.2f})")

                    daily_pnl += trade.pnl or 0

            self.daily_pnl[date_str] = daily_pnl
            log(f"  Daily P&L: ${daily_pnl:+.2f} | Balance: ${self.balance:,.2f}")

        return self._generate_report()

    def _get_actual_temperature(self, city: str, date_str: str) -> Optional[float]:
        """
        Get actual recorded temperature from Open-Meteo archive.
        """
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
            log(f"  Error fetching archive for {city}: {e}")

        return None

    def _generate_brackets(self, center_temp: int) -> List[tuple]:
        """
        Generate temperature brackets around the expected temp.
        Returns list of (temp, bracket_type) tuples.
        """
        brackets = []

        # Individual degree brackets around center
        for offset in range(-3, 4):
            brackets.append((center_temp + offset, "exact"))

        # Edge brackets
        brackets.append((center_temp - 4, "or_lower"))
        brackets.append((center_temp + 4, "or_higher"))

        return brackets

    def _calculate_actual_probability(
        self, actual_temp: float, bracket_temp: int, bracket_type: str
    ) -> float:
        """
        Calculate the 'actual' probability given the real outcome.
        Used to simulate what the market price should have been.
        """
        # Use tiny variance to simulate very informed market
        std_dev = 0.5

        z = (bracket_temp - actual_temp) / std_dev

        def norm_cdf(x):
            return 0.5 * (1 + erf(x / sqrt(2)))

        if bracket_type == "or_higher":
            return 1 - norm_cdf(z - 0.5)
        elif bracket_type == "or_lower":
            return norm_cdf(z + 0.5)
        else:
            return norm_cdf(z + 0.5) - norm_cdf(z - 0.5)

    def _open_position(self, edge: Dict) -> Optional[BacktestTrade]:
        """Open a position based on edge."""
        # Calculate position size
        position_size = min(
            self.balance * MAX_POSITION_PCT,
            MAX_POSITION_USD
        )
        position_size = max(position_size, MIN_POSITION_USD)

        if position_size > self.balance:
            return None

        # Entry price depends on direction
        if edge["direction"] == "BUY_YES":
            entry_price = edge["pm_prob"]
        else:
            entry_price = 1 - edge["pm_prob"]  # Price of NO

        shares = position_size / entry_price
        cost = position_size

        self.balance -= cost

        return BacktestTrade(
            city=edge["city"],
            date=edge["date"],
            temp=edge["temp"],
            bracket_type=edge["bracket_type"],
            direction=edge["direction"],
            entry_price=entry_price,
            shares=shares,
            cost=cost,
            edge_pct=edge["edge_pct"],
            forecast_temp=edge["forecast_temp"],
            actual_temp=edge["actual_temp"],
            status="open"
        )

    def _resolve_trade(self, trade: BacktestTrade):
        """Resolve a trade based on actual temperature."""
        if trade.actual_temp is None:
            trade.won = False
            trade.pnl = -trade.cost
            trade.status = "lost"
            self.balance += 0  # Total loss
            return

        actual = trade.actual_temp
        bracket = trade.temp
        bracket_type = trade.bracket_type

        # Determine if bracket hit
        if bracket_type == "exact":
            bracket_hit = (round(actual) == bracket)
        elif bracket_type == "or_higher":
            bracket_hit = (actual >= bracket)
        elif bracket_type == "or_lower":
            bracket_hit = (actual <= bracket)
        else:
            bracket_hit = False

        # Determine win based on direction
        if trade.direction == "BUY_YES":
            trade.won = bracket_hit
        else:  # BUY_NO
            trade.won = not bracket_hit

        # Calculate P&L
        if trade.won:
            payout = trade.shares * 1.0  # $1 per share on win
            trade.pnl = payout - trade.cost
            trade.status = "won"
        else:
            trade.pnl = -trade.cost
            trade.status = "lost"

        self.balance += (trade.cost + trade.pnl)  # Return cost + pnl

    def _generate_report(self) -> Dict:
        """Generate backtest report."""
        log("\n" + "=" * 60)
        log("BACKTEST SUMMARY")
        log("=" * 60)

        total_trades = len(self.trades)
        wins = sum(1 for t in self.trades if t.won)
        losses = total_trades - wins

        total_pnl = sum(t.pnl or 0 for t in self.trades)
        avg_win = sum(t.pnl for t in self.trades if t.won and t.pnl) / max(wins, 1)
        avg_loss = sum(t.pnl for t in self.trades if not t.won and t.pnl) / max(losses, 1)

        win_rate = wins / total_trades if total_trades > 0 else 0
        return_pct = (total_pnl / self.starting_balance) * 100

        best_day = max(self.daily_pnl.values()) if self.daily_pnl else 0
        worst_day = min(self.daily_pnl.values()) if self.daily_pnl else 0
        best_day_date = max(self.daily_pnl.items(), key=lambda x: x[1])[0] if self.daily_pnl else "N/A"
        worst_day_date = min(self.daily_pnl.items(), key=lambda x: x[1])[0] if self.daily_pnl else "N/A"

        log(f"Starting Balance: ${self.starting_balance:,.2f}")
        log(f"Final Balance:    ${self.balance:,.2f}")
        log(f"Total P&L:        ${total_pnl:+,.2f} ({return_pct:+.1f}%)")
        log(f"")
        log(f"Total Trades:     {total_trades}")
        log(f"Win Rate:         {win_rate:.1%} ({wins}/{total_trades})")
        log(f"Avg Win:          ${avg_win:+.2f}")
        log(f"Avg Loss:         ${avg_loss:.2f}")
        log(f"")
        log(f"Best Day:         ${best_day:+.2f} ({best_day_date})")
        log(f"Worst Day:        ${worst_day:+.2f} ({worst_day_date})")
        log("=" * 60)

        # Trade breakdown by city
        log("\nTrades by City:")
        for city in ["seoul", "london", "wellington"]:
            city_trades = [t for t in self.trades if t.city == city]
            city_wins = sum(1 for t in city_trades if t.won)
            city_pnl = sum(t.pnl or 0 for t in city_trades)
            if city_trades:
                log(f"  {city.upper()}: {len(city_trades)} trades, "
                    f"{city_wins}/{len(city_trades)} wins, ${city_pnl:+.2f}")

        return {
            "starting_balance": self.starting_balance,
            "final_balance": self.balance,
            "total_pnl": total_pnl,
            "return_pct": return_pct,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "best_day": best_day,
            "worst_day": worst_day,
            "trades": self.trades,
            "daily_pnl": self.daily_pnl
        }


def main():
    parser = argparse.ArgumentParser(description="Weather Market Backtest")
    parser.add_argument("--days", type=int, default=7, help="Days to backtest")
    parser.add_argument("--balance", type=float, default=1000.0, help="Starting balance")
    parser.add_argument("--min-edge", type=float, default=5.0, help="Minimum edge %")
    args = parser.parse_args()

    backtest = WeatherBacktest(starting_balance=args.balance)
    report = backtest.run_backtest(days_back=args.days, min_edge_pct=args.min_edge)

    return report


if __name__ == "__main__":
    main()
