#!/usr/bin/env python3
"""
Weather Market Backtest - ALL BRACKETS Analysis.

Tests EVERY temperature bracket to understand:
1. What % of exact brackets get hit?
2. What's the ACTUAL win rate for SELL Yes across ALL brackets?
3. What's the expected value of each strategy?

This is the ground truth for weather market profitability.

Usage:
    python -m src.weather_backtest_all_brackets --days 90
"""

import argparse
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

from src.weather_scanner import WEATHER_CITIES


def log(msg: str):
    print(f"[BACKTEST] {msg}", flush=True)


class WeatherBracketAnalysis:
    """Analyze hit rates for ALL temperature brackets."""

    def __init__(self):
        self.results = defaultdict(list)  # city -> list of {date, actual_temp, brackets_hit}

    def analyze(self, days_back: int = 90):
        """Analyze bracket hit rates over past N days."""
        cities = ["seoul", "london", "wellington"]

        log("=" * 70)
        log("WEATHER BRACKET HIT RATE ANALYSIS")
        log("=" * 70)
        log(f"Analyzing {days_back} days of historical data")
        log("Testing which exact brackets would have been hit")
        log("=" * 70)

        for city in cities:
            log(f"\nFetching {city.upper()} data...")
            temps = self._get_temperature_history(city, days_back)
            if temps:
                self.results[city] = temps
                log(f"  Got {len(temps)} days of data")

        return self._generate_analysis()

    def _get_temperature_history(self, city: str, days_back: int) -> List[Dict]:
        """Get historical temperatures for analysis."""
        if city not in WEATHER_CITIES:
            return []

        coords = WEATHER_CITIES[city]
        temps = []

        # Open-Meteo archive allows fetching range
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=days_back)

        try:
            url = (
                f"https://archive-api.open-meteo.com/v1/archive?"
                f"latitude={coords['lat']}&longitude={coords['lon']}"
                f"&start_date={start_date.strftime('%Y-%m-%d')}"
                f"&end_date={end_date.strftime('%Y-%m-%d')}"
                f"&daily=temperature_2m_max"
                f"&timezone={coords['tz']}"
            )

            r = requests.get(url, timeout=30)
            data = r.json()

            if "daily" in data:
                dates = data["daily"].get("time", [])
                max_temps = data["daily"].get("temperature_2m_max", [])

                for date, temp in zip(dates, max_temps):
                    if temp is not None:
                        temps.append({
                            "date": date,
                            "actual_temp": float(temp),
                            "rounded_temp": int(round(float(temp)))
                        })

        except Exception as e:
            log(f"  Error: {e}")

        return temps

    def _generate_analysis(self) -> Dict:
        """Generate comprehensive bracket analysis."""
        log("\n" + "=" * 70)
        log("RESULTS")
        log("=" * 70)

        all_temps = []
        bracket_hits = defaultdict(int)  # bracket_temp -> count of hits
        total_days_by_city = {}

        for city, temps in self.results.items():
            total_days_by_city[city] = len(temps)
            for t in temps:
                all_temps.append(t)
                bracket_hits[t["rounded_temp"]] += 1

        total_days = len(all_temps)
        if total_days == 0:
            log("No data available!")
            return {}

        # Calculate statistics
        log(f"\nTotal data points: {total_days}")
        log(f"  Seoul: {total_days_by_city.get('seoul', 0)} days")
        log(f"  London: {total_days_by_city.get('london', 0)} days")
        log(f"  Wellington: {total_days_by_city.get('wellington', 0)} days")

        # Temperature distribution
        log("\n" + "-" * 50)
        log("TEMPERATURE DISTRIBUTION")
        log("-" * 50)

        temp_values = [t["actual_temp"] for t in all_temps]
        log(f"Min temp: {min(temp_values):.1f}°C")
        log(f"Max temp: {max(temp_values):.1f}°C")
        log(f"Mean temp: {sum(temp_values)/len(temp_values):.1f}°C")

        # Bracket hit rate analysis
        log("\n" + "-" * 50)
        log("EXACT BRACKET HIT RATE")
        log("-" * 50)

        # What % of time does EACH bracket get hit?
        unique_brackets = len(bracket_hits)
        log(f"Unique brackets seen: {unique_brackets}")
        log(f"Total observations: {total_days}")

        # If we had 1 market per bracket per day, how many would hit?
        # Example: If Seoul has brackets 0C, 1C, 2C... 15C (16 brackets)
        # And we have 90 days, that's 90 x 16 = 1440 bracket-days
        # Only ~90 of those would hit (one per day)

        # Simplified: For each day, only ONE bracket hits
        # So hit rate per bracket = 1 / num_brackets_in_range

        # Estimate typical range per city
        city_ranges = {}
        for city, temps in self.results.items():
            if temps:
                city_temps = [t["rounded_temp"] for t in temps]
                city_ranges[city] = (min(city_temps), max(city_temps))
                bracket_range = max(city_temps) - min(city_temps) + 1
                log(f"\n{city.upper()}:")
                log(f"  Range: {min(city_temps)}°C to {max(city_temps)}°C ({bracket_range} brackets)")
                log(f"  Per-bracket hit rate: {100/bracket_range:.1f}%")

        # Key metric: If we SELL Yes on a RANDOM bracket, what's our win rate?
        # Win = bracket does NOT hit = (brackets - 1) / brackets
        log("\n" + "-" * 50)
        log("STRATEGY ANALYSIS")
        log("-" * 50)

        # Calculate per-city metrics
        all_trades = 0
        all_wins = 0

        for city, temps in self.results.items():
            if not temps:
                continue

            rounded_temps = [t["rounded_temp"] for t in temps]
            min_t, max_t = min(rounded_temps), max(rounded_temps)
            bracket_count = max_t - min_t + 1

            # Simulate: Each day, we SELL Yes on EVERY bracket
            # We WIN on brackets that don't hit, LOSE on the one that does
            city_trades = len(temps) * bracket_count
            city_losses = len(temps)  # One bracket hits per day
            city_wins = city_trades - city_losses

            all_trades += city_trades
            all_wins += city_wins

            win_rate = city_wins / city_trades if city_trades > 0 else 0
            log(f"\n{city.upper()} - SELL Yes on ALL brackets:")
            log(f"  Total bracket-days: {city_trades}")
            log(f"  Wins (bracket doesn't hit): {city_wins}")
            log(f"  Losses (bracket hits): {city_losses}")
            log(f"  Win Rate: {win_rate:.1%}")

        overall_win_rate = all_wins / all_trades if all_trades > 0 else 0
        log(f"\nOVERALL SELL Yes Win Rate: {overall_win_rate:.1%}")

        # Expected value calculation
        log("\n" + "-" * 50)
        log("EXPECTED VALUE CALCULATION")
        log("-" * 50)

        # Assumptions for SELL Yes:
        # - Yes price on exact bracket: ~3% (receive $0.03 per share)
        # - Collateral: $1.00 per share
        # - Win: Keep $0.03 premium
        # - Lose: Pay out $1.00 - $0.03 = $0.97

        yes_prices = [0.01, 0.03, 0.05, 0.10]  # Test various premium levels

        for yes_price in yes_prices:
            premium = yes_price
            loss_if_yes_wins = 1.0 - yes_price

            ev_sell_yes = (overall_win_rate * premium) - ((1 - overall_win_rate) * loss_if_yes_wins)

            log(f"\nSELL Yes @ {yes_price*100:.0f}% premium:")
            log(f"  Win Rate: {overall_win_rate:.1%}")
            log(f"  Win profit: ${premium:.2f}")
            log(f"  Loss cost: ${loss_if_yes_wins:.2f}")
            log(f"  Expected Value: ${ev_sell_yes:.4f} per trade")
            log(f"  EV as % of collateral: {ev_sell_yes*100:.2f}%")

            # Annual ROI if we do 3 trades per day
            daily_trades = 3 * 3  # 3 cities, 3 brackets per city
            annual_ev = ev_sell_yes * daily_trades * 365
            log(f"  Est. Annual EV ({daily_trades} trades/day): ${annual_ev:.2f}")

        # SELL No analysis (opposite)
        log("\n" + "-" * 50)
        log("SELL No ANALYSIS")
        log("-" * 50)

        # SELL No: Win when Yes wins (bracket hits), Lose when No wins (bracket doesn't hit)
        sell_no_win_rate = 1 - overall_win_rate

        no_prices = [0.97, 0.95, 0.90]

        for no_price in no_prices:
            premium = no_price
            loss_if_no_wins = 1.0 - no_price

            ev_sell_no = (sell_no_win_rate * premium) - ((1 - sell_no_win_rate) * loss_if_no_wins)

            log(f"\nSELL No @ {no_price*100:.0f}% premium:")
            log(f"  Win Rate (bracket hits): {sell_no_win_rate:.1%}")
            log(f"  Win profit: ${premium:.2f}")
            log(f"  Loss cost: ${loss_if_no_wins:.2f}")
            log(f"  Expected Value: ${ev_sell_no:.4f} per trade")

        log("\n" + "=" * 70)
        log("CONCLUSION")
        log("=" * 70)

        if overall_win_rate > 0.95:
            log("SELL Yes has 95%+ win rate - check if EV is positive at market prices")
        elif overall_win_rate > 0.90:
            log("SELL Yes has 90-95% win rate - may be viable with right pricing")
        else:
            log(f"SELL Yes win rate ({overall_win_rate:.1%}) too low for safe strategy")

        return {
            "total_days": total_days,
            "sell_yes_win_rate": overall_win_rate,
            "sell_no_win_rate": sell_no_win_rate,
            "city_ranges": city_ranges
        }


def main():
    parser = argparse.ArgumentParser(description="Weather Bracket Analysis")
    parser.add_argument("--days", type=int, default=90, help="Days to analyze")
    args = parser.parse_args()

    analysis = WeatherBracketAnalysis()
    results = analysis.analyze(days_back=args.days)

    return results


if __name__ == "__main__":
    main()
