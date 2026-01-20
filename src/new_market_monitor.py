"""
New Market Monitor for poly-scout.
Detects newly created markets and identifies mispricing opportunities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import httpx

from src.config import GAMMA_API_BASE


SEEN_MARKETS_FILE = "./data/seen_markets.json"


def log(msg: str):
    print(f"[NEW MARKETS] {msg}", flush=True)


@dataclass
class NewMarketOpportunity:
    """A newly detected market with potential mispricing."""
    slug: str
    title: str
    outcomes: list
    prices: list
    detected_at: datetime
    mispricing_score: float  # 0-1, higher = more mispriced
    recommendation: str  # "BUY YES", "BUY NO", "SKIP"
    # New fields for realistic trading
    cheap_outcome_idx: int = 0  # Index of the cheap outcome
    cheap_outcome_name: str = ""  # Actual name like "Yes" or "No"
    token_id: str = ""  # CLOB token ID for order book queries


class NewMarketMonitor:
    """Monitor for newly created Polymarket markets."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        self.seen_markets = self._load_seen_markets()
        log(f"Loaded {len(self.seen_markets)} seen markets")

    def _load_seen_markets(self) -> set:
        """Load previously seen market slugs."""
        try:
            path = Path(SEEN_MARKETS_FILE)
            if path.exists():
                with open(path) as f:
                    return set(json.load(f))
        except Exception:
            pass
        return set()

    def _save_seen_markets(self):
        """Save seen market slugs."""
        try:
            path = Path(SEEN_MARKETS_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(list(self.seen_markets), f)
        except Exception as e:
            log(f"Error saving seen markets: {e}")

    async def fetch_active_markets(self) -> list:
        """Fetch all active markets from Gamma API."""
        url = f"{GAMMA_API_BASE}/events?active=true&closed=false&limit=500"
        resp = await self.client.get(url)
        if resp.status_code == 200:
            return resp.json()
        return []

    def analyze_mispricing(self, event: dict) -> Optional[NewMarketOpportunity]:
        """
        Check if a market has mispriced options.

        Mispricing signals:
        - YES + NO prices don't sum to ~$1.00 (arbitrage)
        - One side extremely cheap (<$0.10) on obvious outcome
        - Wide spread between bid/ask
        """
        markets = event.get("markets", [])
        if not markets:
            return None

        for market in markets:
            outcomes_raw = market.get("outcomes", [])
            prices_str = market.get("outcomePrices", "[]")
            clob_token_ids_raw = market.get("clobTokenIds", [])

            try:
                # Parse outcomes - can be a JSON string or already a list
                if isinstance(outcomes_raw, str):
                    outcomes = json.loads(outcomes_raw)
                else:
                    outcomes = outcomes_raw

                # Parse prices
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                prices = [float(p) for p in prices]

                # Parse token IDs - can be a JSON string or already a list
                if isinstance(clob_token_ids_raw, str):
                    clob_token_ids = json.loads(clob_token_ids_raw)
                else:
                    clob_token_ids = clob_token_ids_raw
            except Exception:
                continue

            if len(prices) < 2:
                continue

            # Check for mispricing
            total = sum(prices)
            mispricing_score = 0.0
            recommendation = "SKIP"
            cheap_idx = 0
            cheap_outcome_name = outcomes[0] if outcomes else "Unknown"
            token_id = clob_token_ids[0] if clob_token_ids else ""

            # Signal 1: Prices don't sum to ~1.0 (arbitrage opportunity)
            if total < 0.95:
                mispricing_score += 0.5
                recommendation = "ARB: Buy both sides"

            # Signal 2: Extreme prices (<10 cents or >90 cents)
            min_price = min(prices)
            max_price = max(prices)

            if min_price < 0.10:
                mispricing_score += 0.3
                cheap_idx = prices.index(min_price)
                cheap_outcome_name = outcomes[cheap_idx] if cheap_idx < len(outcomes) else "Unknown"
                token_id = clob_token_ids[cheap_idx] if cheap_idx < len(clob_token_ids) else ""
                recommendation = f"BUY {cheap_outcome_name} at ${min_price:.2f}"

            if max_price > 0.90:
                mispricing_score += 0.2

            if mispricing_score >= 0.3:
                return NewMarketOpportunity(
                    slug=event.get("slug", ""),
                    title=event.get("title", ""),
                    outcomes=outcomes,
                    prices=prices,
                    detected_at=datetime.now(),
                    mispricing_score=mispricing_score,
                    recommendation=recommendation,
                    cheap_outcome_idx=cheap_idx,
                    cheap_outcome_name=cheap_outcome_name,
                    token_id=token_id,
                )

        return None

    async def scan_for_new_markets(self) -> list:
        """
        Scan for newly created markets and check for mispricing.

        Returns list of opportunities.
        """
        opportunities = []
        new_count = 0

        events = await self.fetch_active_markets()

        for event in events:
            slug = event.get("slug", "")
            if not slug:
                continue

            # Check if this is a NEW market (not seen before)
            if slug in self.seen_markets:
                continue

            # New market detected!
            new_count += 1
            self.seen_markets.add(slug)

            # Check for mispricing
            opp = self.analyze_mispricing(event)
            if opp:
                opportunities.append(opp)
                log(f"OPPORTUNITY: {opp.title[:50]}... score={opp.mispricing_score:.0%}")

        if new_count > 0:
            log(f"Found {new_count} new markets, {len(opportunities)} with mispricing")

        self._save_seen_markets()
        return opportunities

    async def close(self):
        self._save_seen_markets()
        await self.client.aclose()


async def main():
    """Test the new market monitor."""
    monitor = NewMarketMonitor()

    try:
        opps = await monitor.scan_for_new_markets()
        print(f"\nFound {len(opps)} opportunities")
        for opp in opps[:5]:
            print(f"\n{opp.title}")
            print(f"  Prices: {opp.prices}")
            print(f"  Score: {opp.mispricing_score:.0%}")
            print(f"  {opp.recommendation}")
    finally:
        await monitor.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
