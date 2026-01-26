"""
Long-shot Scanner - planktonXD Strategy Implementation

Finds markets with ultra-low prices (<5 cents) that could return 20-200x.
Based on analysis of @planktonXD's $87k profit strategy.

Strategy:
- Entry price: 0.5c - 5c per share
- Position size: $15-$50 per bet
- Target: 20-200x returns on improbable outcomes
- Categories: Crypto volatility, geopolitics, esports, natural events
"""

import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional

import httpx

from src.config import GAMMA_API_BASE, CLOB_API_BASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def log(msg: str):
    print(f"[LONGSHOT] {msg}", flush=True)


@dataclass
class LongshotOpportunity:
    """A low-price, high-potential opportunity."""
    question: str
    slug: str
    outcome: str  # "Yes" or "No"
    price: float  # Entry price (0.005 = 0.5 cents)
    potential_return: float  # Multiplier if wins (e.g., 200 = 200x)
    liquidity: float
    days_until_resolution: int
    category: str  # crypto, geopolitics, sports, esports, other
    token_id: str


class LongshotScanner:
    """Scanner for planktonXD-style long-shot opportunities."""

    # Price thresholds
    MIN_PRICE = 0.001  # 0.1 cents (avoid dead markets)
    MAX_PRICE = 0.05   # 5 cents
    MIN_LIQUIDITY = 500  # $500 minimum
    MAX_DAYS = 3  # 72h max for capital efficiency

    # Category keywords
    CRYPTO_KEYWORDS = ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 'xrp', 'doge', 'crypto', 'price']
    GEOPOLITICS_KEYWORDS = ['strike', 'war', 'ceasefire', 'invasion', 'troops', 'military', 'russia', 'ukraine', 'israel', 'iran']
    ESPORTS_KEYWORDS = ['dota', 'csgo', 'valorant', 'league of legends', 'esports', 'bo3', 'bo5']
    SPORTS_KEYWORDS = ['nba', 'nfl', 'nhl', 'mlb', 'tennis', 'golf', 'soccer', 'football']

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def fetch_gamma_markets(self) -> list:
        """Fetch all active markets from Gamma API."""
        all_markets = []
        offset = 0
        limit = 500

        while True:
            url = f"{GAMMA_API_BASE}/markets?active=true&closed=false&limit={limit}&offset={offset}"
            try:
                resp = await self.client.get(url)
                if resp.status_code != 200:
                    break
                markets = resp.json()
                if not markets:
                    break
                all_markets.extend(markets)
                if len(markets) < limit:
                    break
                offset += limit
            except Exception as e:
                log(f"Error fetching Gamma markets: {e}")
                break

        return all_markets

    async def fetch_clob_markets(self) -> list:
        """Fetch all active markets from CLOB API (real-time order book prices)."""
        all_markets = []
        try:
            # CLOB API returns markets with next_cursor pagination
            cursor = None
            while True:
                url = f"{CLOB_API_BASE}/markets"
                if cursor:
                    url += f"?next_cursor={cursor}"
                resp = await self.client.get(url)
                if resp.status_code != 200:
                    log(f"CLOB API error: {resp.status_code}")
                    break
                data = resp.json()
                markets = data if isinstance(data, list) else data.get("data", data.get("markets", []))
                if not markets:
                    break
                all_markets.extend(markets)
                # Check for pagination
                cursor = data.get("next_cursor") if isinstance(data, dict) else None
                if not cursor or len(markets) < 100:
                    break
        except Exception as e:
            log(f"Error fetching CLOB markets: {e}")

        return all_markets

    async def fetch_all_markets(self) -> list:
        """Fetch markets from both Gamma and CLOB APIs, merge by condition_id."""
        # Fetch from both APIs
        gamma_markets = await self.fetch_gamma_markets()
        clob_markets = await self.fetch_clob_markets()

        log(f"Fetched {len(gamma_markets)} from Gamma, {len(clob_markets)} from CLOB")

        # Index CLOB markets by condition_id for price updates
        clob_by_condition = {}
        for m in clob_markets:
            cond_id = m.get("condition_id")
            if cond_id:
                clob_by_condition[cond_id] = m

        # Merge: use Gamma data but update prices from CLOB if available
        for market in gamma_markets:
            cond_id = market.get("conditionId")
            if cond_id and cond_id in clob_by_condition:
                clob = clob_by_condition[cond_id]
                # CLOB has tokens array with price info
                tokens = clob.get("tokens", [])
                if tokens:
                    # Update outcomePrices from CLOB's more recent data
                    clob_prices = []
                    for token in tokens:
                        price = token.get("price", 0)
                        clob_prices.append(str(price))
                    if clob_prices:
                        market["outcomePrices"] = json.dumps(clob_prices)
                        market["_source"] = "clob"  # Mark as CLOB-updated

        return gamma_markets

    def categorize_market(self, question: str) -> str:
        """Categorize market by content."""
        q_lower = question.lower()

        if any(kw in q_lower for kw in self.CRYPTO_KEYWORDS):
            return "crypto"
        if any(kw in q_lower for kw in self.GEOPOLITICS_KEYWORDS):
            return "geopolitics"
        if any(kw in q_lower for kw in self.ESPORTS_KEYWORDS):
            return "esports"
        if any(kw in q_lower for kw in self.SPORTS_KEYWORDS):
            return "sports"
        return "other"

    def analyze_market(self, market: dict) -> Optional[LongshotOpportunity]:
        """Check if market has a long-shot opportunity."""
        prices_str = market.get("outcomePrices", "[]")
        end_date_str = market.get("endDate", "")

        # Parse end date
        days_left = 999
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                days_left = (end_date - now).days
                if days_left < 0 or days_left > self.MAX_DAYS:
                    return None
            except:
                pass
        else:
            return None  # Skip markets without end date

        # Parse prices
        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            prices = [float(p) for p in prices]
        except:
            return None

        if not prices:
            return None

        liquidity = float(market.get("liquidity", 0))
        if liquidity < self.MIN_LIQUIDITY:
            return None

        question = market.get("question", "")
        slug = market.get("slug", "")

        # Parse token IDs
        clob_token_ids_raw = market.get("clobTokenIds", [])
        if isinstance(clob_token_ids_raw, str):
            try:
                clob_token_ids = json.loads(clob_token_ids_raw)
            except:
                clob_token_ids = []
        else:
            clob_token_ids = clob_token_ids_raw

        # Check each outcome for long-shot potential
        for i, price in enumerate(prices):
            if self.MIN_PRICE < price < self.MAX_PRICE:
                outcome = "Yes" if i == 0 else "No"
                potential = (1 / price) - 1  # Return multiplier
                token_id = clob_token_ids[i] if i < len(clob_token_ids) else ""

                return LongshotOpportunity(
                    question=question[:100],
                    slug=slug,
                    outcome=outcome,
                    price=price,
                    potential_return=potential,
                    liquidity=liquidity,
                    days_until_resolution=days_left,
                    category=self.categorize_market(question),
                    token_id=token_id
                )

        return None

    async def scan(self) -> list[LongshotOpportunity]:
        """Scan all markets for long-shot opportunities."""
        log("Scanning for long-shot opportunities...")

        markets = await self.fetch_all_markets()
        log(f"Fetched {len(markets)} markets")

        opportunities = []
        for market in markets:
            opp = self.analyze_market(market)
            if opp:
                opportunities.append(opp)

        # Sort by potential return (highest first)
        opportunities.sort(key=lambda x: x.potential_return, reverse=True)

        log(f"Found {len(opportunities)} long-shot opportunities")
        return opportunities

    async def get_top_opportunities(self, limit: int = 20, category: str = None) -> list[LongshotOpportunity]:
        """Get top opportunities, optionally filtered by category."""
        all_opps = await self.scan()

        if category:
            all_opps = [o for o in all_opps if o.category == category]

        # Prioritize near-term (resolving soon)
        all_opps.sort(key=lambda x: (x.days_until_resolution, -x.potential_return))

        return all_opps[:limit]

    async def close(self):
        await self.client.aclose()


async def send_longshot_alert(opportunities: list[LongshotOpportunity]):
    """Send Telegram alert for top long-shot opportunities."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    if not opportunities:
        return

    # Group by category
    by_category = {}
    for opp in opportunities[:15]:
        cat = opp.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(opp)

    msg = "🎰 *LONG-SHOT OPPORTUNITIES*\n"
    msg += "_planktonXD Strategy_\n\n"

    for category, opps in by_category.items():
        emoji = {"crypto": "💰", "geopolitics": "🌍", "esports": "🎮", "sports": "⚽"}.get(category, "📊")
        msg += f"{emoji} *{category.upper()}*\n"

        for opp in opps[:5]:
            cents = opp.price * 100
            msg += f"• {cents:.1f}¢ → {opp.potential_return:.0f}x | {opp.days_until_resolution}d\n"
            msg += f"  _{opp.question[:45]}_\n"
        msg += "\n"

    msg += "💡 Small bets, big upside!"

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": msg,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                }
            )
            log("Sent Telegram alert")
        except Exception as e:
            log(f"Error sending Telegram: {e}")


async def main():
    """Test the long-shot scanner."""
    scanner = LongshotScanner()

    try:
        # Get top near-term opportunities
        opps = await scanner.get_top_opportunities(limit=30)

        print("\n=== TOP LONG-SHOT OPPORTUNITIES ===\n")

        for opp in opps:
            cents = opp.price * 100
            print(f"{cents:.1f}¢ → {opp.potential_return:.0f}x | {opp.outcome} | {opp.days_until_resolution}d | ${opp.liquidity:,.0f}")
            print(f"  [{opp.category}] {opp.question}")
            print()

        # Send alert
        await send_longshot_alert(opps)

    finally:
        await scanner.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
