"""
Weather Bucket Arbitrage Scanner

Based on 0xf2e346ab strategy: $204 → $24K, 73% win rate, 1300+ trades

Finds arbitrage opportunities in temperature bracket markets where:
1. Sum of all bracket YES prices < $1.00 (guaranteed profit)
2. Adjacent brackets are mispriced relative to each other
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.config import GAMMA_API_BASE


def log(msg: str):
    print(f"[WEATHER-BUCKET] {msg}", flush=True)


@dataclass
class Bracket:
    """A single temperature bracket within an event."""
    question: str
    market_id: str
    token_id: str
    yes_price: float
    no_price: float
    liquidity: float
    range_low: Optional[float] = None  # e.g., 5 for "5-10°C"
    range_high: Optional[float] = None  # e.g., 10 for "5-10°C"


@dataclass
class WeatherEvent:
    """A weather event with multiple temperature brackets."""
    slug: str
    title: str
    city: str
    date: str
    end_date: str
    brackets: list[Bracket] = field(default_factory=list)

    @property
    def total_yes_price(self) -> float:
        return sum(b.yes_price for b in self.brackets)

    @property
    def arbitrage_edge(self) -> float:
        """Positive = buy all YES, negative = buy all NO."""
        return 1.0 - self.total_yes_price


@dataclass
class BucketArbitrageOpportunity:
    """An identified arbitrage opportunity."""
    event: WeatherEvent
    arb_type: str  # "SUM_UNDER" or "SUM_OVER" or "ADJACENT"
    edge: float  # Percentage edge
    total_cost: float  # Cost to execute
    expected_profit: float
    brackets_to_buy: list[Bracket]
    recommended_size: float = 20.0  # $ per bracket


class WeatherBucketScanner:
    """Scanner for weather bucket arbitrage opportunities."""

    # Cities we track
    CITIES = ["london", "seoul", "wellington", "new york", "nyc", "miami"]

    # Keywords for weather/temperature markets
    WEATHER_KEYWORDS = [
        "temperature", "high temp", "low temp", "celsius", "fahrenheit",
        "degrees", "°c", "°f", "weather"
    ]

    # Min edge to consider (after fees)
    MIN_EDGE = 0.015  # 1.5%

    # Min liquidity per bracket
    MIN_LIQUIDITY = 200

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def fetch_weather_events(self) -> list[dict]:
        """Fetch active weather events from Gamma API."""
        all_events = []
        offset = 0
        limit = 100

        while True:
            url = f"{GAMMA_API_BASE}/events?active=true&closed=false&limit={limit}&offset={offset}"
            try:
                resp = await self.client.get(url)
                if resp.status_code != 200:
                    break
                events = resp.json()
                if not events:
                    break

                # Filter for weather events
                for event in events:
                    title = event.get("title", "").lower()
                    slug = event.get("slug", "").lower()

                    # Check if it's a weather/temperature event
                    is_weather = any(kw in title for kw in self.WEATHER_KEYWORDS)
                    is_target_city = any(city in title or city in slug for city in self.CITIES)

                    if is_weather and is_target_city:
                        all_events.append(event)

                if len(events) < limit:
                    break
                offset += limit
            except Exception as e:
                log(f"Error fetching events: {e}")
                break

        log(f"Found {len(all_events)} weather events")
        return all_events

    def parse_temperature_range(self, question: str) -> tuple[Optional[float], Optional[float]]:
        """Extract temperature range from question text."""
        # Patterns like "5°C to 10°C", "5-10°C", "between 5 and 10"
        patterns = [
            r"(\d+(?:\.\d+)?)\s*°?[CF]?\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*°?[CF]?",
            r"between\s+(\d+(?:\.\d+)?)\s*(?:and|&)\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*(?:and|&)\s*(\d+(?:\.\d+)?)\s*°?[CF]?",
        ]

        q_lower = question.lower()
        for pattern in patterns:
            match = re.search(pattern, q_lower)
            if match:
                return float(match.group(1)), float(match.group(2))

        # Check for "above X" or "below X"
        above = re.search(r"above\s+(\d+(?:\.\d+)?)", q_lower)
        if above:
            return float(above.group(1)), None

        below = re.search(r"below\s+(\d+(?:\.\d+)?)", q_lower)
        if below:
            return None, float(below.group(1))

        return None, None

    def extract_city(self, text: str) -> str:
        """Extract city name from event title."""
        text_lower = text.lower()
        for city in self.CITIES:
            if city in text_lower:
                return city.title()
        return "Unknown"

    def build_weather_event(self, event_data: dict) -> Optional[WeatherEvent]:
        """Build a WeatherEvent from API data."""
        markets = event_data.get("markets", [])
        if len(markets) < 2:  # Need at least 2 brackets
            return None

        title = event_data.get("title", "")
        city = self.extract_city(title)

        weather_event = WeatherEvent(
            slug=event_data.get("slug", ""),
            title=title,
            city=city,
            date=event_data.get("startDate", ""),
            end_date=event_data.get("endDate", ""),
        )

        for market in markets:
            prices_str = market.get("outcomePrices", "[]")
            try:
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                prices = [float(p) for p in prices]
            except:
                continue

            if len(prices) < 2:
                continue

            question = market.get("question", "")
            range_low, range_high = self.parse_temperature_range(question)

            # Get token IDs
            token_ids_raw = market.get("clobTokenIds", [])
            if isinstance(token_ids_raw, str):
                try:
                    token_ids = json.loads(token_ids_raw)
                except:
                    token_ids = []
            else:
                token_ids = token_ids_raw

            bracket = Bracket(
                question=question,
                market_id=market.get("id", ""),
                token_id=token_ids[0] if token_ids else "",
                yes_price=prices[0],
                no_price=prices[1] if len(prices) > 1 else 1 - prices[0],
                liquidity=float(market.get("liquidity", 0)),
                range_low=range_low,
                range_high=range_high,
            )

            weather_event.brackets.append(bracket)

        # Sort brackets by range if available
        weather_event.brackets.sort(
            key=lambda b: (b.range_low or 0, b.range_high or 0)
        )

        return weather_event if len(weather_event.brackets) >= 2 else None

    def find_sum_arbitrage(self, event: WeatherEvent) -> Optional[BucketArbitrageOpportunity]:
        """Find arbitrage where sum of YES prices ≠ $1.00."""
        total = event.total_yes_price
        edge = event.arbitrage_edge

        # Check minimum liquidity
        min_liq = min(b.liquidity for b in event.brackets)
        if min_liq < self.MIN_LIQUIDITY:
            return None

        if edge > self.MIN_EDGE:
            # Sum < $1.00: Buy YES on all brackets
            return BucketArbitrageOpportunity(
                event=event,
                arb_type="SUM_UNDER",
                edge=edge,
                total_cost=total,
                expected_profit=edge,
                brackets_to_buy=event.brackets,
            )
        elif edge < -self.MIN_EDGE:
            # Sum > $1.00: Buy NO on all brackets
            return BucketArbitrageOpportunity(
                event=event,
                arb_type="SUM_OVER",
                edge=abs(edge),
                total_cost=sum(b.no_price for b in event.brackets),
                expected_profit=abs(edge),
                brackets_to_buy=event.brackets,
            )

        return None

    def find_adjacent_mispricing(self, event: WeatherEvent) -> Optional[BucketArbitrageOpportunity]:
        """Find mispricing between adjacent brackets."""
        # This is more complex - look for brackets where prices don't make sense
        # e.g., if 5-10°C is 15¢ but 10-15°C is 55¢, and they should be closer
        # For now, we focus on sum arbitrage which is simpler and proven

        # TODO: Implement more sophisticated adjacent bracket analysis
        return None

    async def scan(self) -> list[BucketArbitrageOpportunity]:
        """Scan all weather events for arbitrage opportunities."""
        log("Scanning for weather bucket arbitrage...")

        events_data = await self.fetch_weather_events()
        opportunities = []

        for event_data in events_data:
            event = self.build_weather_event(event_data)
            if not event:
                continue

            # Check for sum arbitrage
            sum_arb = self.find_sum_arbitrage(event)
            if sum_arb:
                opportunities.append(sum_arb)
                continue

            # Check for adjacent mispricing
            adj_arb = self.find_adjacent_mispricing(event)
            if adj_arb:
                opportunities.append(adj_arb)

        # Sort by edge (highest first)
        opportunities.sort(key=lambda x: x.edge, reverse=True)

        log(f"Found {len(opportunities)} bucket arbitrage opportunities")
        return opportunities

    async def close(self):
        await self.client.aclose()


async def main():
    """Test the weather bucket scanner."""
    scanner = WeatherBucketScanner()

    try:
        opps = await scanner.scan()

        print("\n=== WEATHER BUCKET ARBITRAGE OPPORTUNITIES ===\n")

        if not opps:
            print("No opportunities found at current prices.")
            print("\nThis is normal - arbitrage opportunities are competitive.")
            print("The scanner will alert when edges appear.\n")
        else:
            for opp in opps:
                print(f"📊 {opp.event.city}: {opp.event.title[:50]}")
                print(f"   Type: {opp.arb_type}")
                print(f"   Edge: {opp.edge*100:.2f}%")
                print(f"   Total Cost: ${opp.total_cost:.3f}")
                print(f"   Brackets: {len(opp.brackets_to_buy)}")
                print(f"   Prices: {[f'${b.yes_price:.2f}' for b in opp.brackets_to_buy]}")
                print()

    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(main())
