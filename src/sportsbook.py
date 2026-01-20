"""
Sportsbook comparator for poly-scout.

Continuously compares Polymarket prices to sportsbook odds (The Odds API).
Finds mispricings where PM differs from sportsbook consensus.
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import httpx

from src.config import (
    ODDS_API_KEY, GAMMA_API_BASE, MIN_EDGE_PCT,
    MONITORED_SPORTS, NBA_TEAM_CODES, american_to_prob
)


def log(msg: str):
    print(f"[SPORTSBOOK] {msg}", flush=True)


@dataclass
class SportsbookOpportunity:
    """A detected mispricing between PM and sportsbooks."""
    market_slug: str
    event_title: str
    outcome: str
    pm_price: float
    sb_price: float
    edge_pct: float
    action: str
    liquidity_usd: float
    resolution_time: datetime
    sport: str
    books_count: int


class SportsbookComparator:
    """Compare Polymarket prices to sportsbook consensus."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def get_sportsbook_odds(self, sport_key: str) -> list[dict]:
        """Get odds from The Odds API for a sport."""
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "american"
        }
        try:
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            log(f"Odds API error {resp.status_code} for {sport_key}")
            return []
        except Exception as e:
            log(f"Odds API error: {e}")
            return []

    async def get_pm_game(self, slug: str) -> Optional[dict]:
        """Get Polymarket event by slug."""
        url = f"{GAMMA_API_BASE}/events?slug={slug}"
        try:
            resp = await self.client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    return data[0]
        except Exception as e:
            log(f"PM API error: {e}")
        return None

    def build_slug(self, prefix: str, home_code: str, away_code: str, date: str) -> str:
        """Build PM slug from components."""
        return f"{prefix}-{away_code}-{home_code}-{date}"

    def get_team_code(self, team_name: str, sport: str) -> str:
        """Get PM team code from full team name."""
        if sport == "NBA":
            return NBA_TEAM_CODES.get(team_name, team_name[:3].lower())
        return team_name[:3].lower()

    async def find_pm_match(self, home: str, away: str, date: str, prefix: str, sport: str) -> Optional[dict]:
        """Find matching PM market for a sportsbook game."""
        home_code = self.get_team_code(home, sport)
        away_code = self.get_team_code(away, sport)

        for slug in [
            self.build_slug(prefix, home_code, away_code, date),
            self.build_slug(prefix, away_code, home_code, date),
        ]:
            pm = await self.get_pm_game(slug)
            if pm and not pm.get("closed"):
                return {"slug": slug, "event": pm}
        return None

    def extract_moneyline(self, event: dict) -> dict[str, float]:
        """Extract moneyline prices from PM event."""
        prices = {}
        for m in event.get("markets", []):
            if not m.get("active") or m.get("closed"):
                continue
            q = m.get("question", "").lower()
            if "o/u" not in q and "spread" not in q and "1h" not in q:
                if " vs. " in q or " vs " in q:
                    outcomes = m.get("outcomes", "[]")
                    if isinstance(outcomes, str):
                        outcomes = json.loads(outcomes)
                    outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                    for i, outcome in enumerate(outcomes):
                        if i < len(outcome_prices):
                            prices[outcome] = float(outcome_prices[i])
                    return prices
        return prices

    def calc_sb_consensus(self, game: dict) -> dict[str, float]:
        """Calculate average sportsbook probability for each outcome."""
        probs = {}
        for bm in game.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    for o in mkt.get("outcomes", []):
                        name = o.get("name")
                        price = o.get("price", 0)
                        prob = american_to_prob(price)
                        if name not in probs:
                            probs[name] = []
                        probs[name].append(prob)
        return {name: sum(odds) / len(odds) for name, odds in probs.items() if odds}

    async def scan_sport(self, sport_key: str, pm_prefix: str, sport_name: str) -> list[SportsbookOpportunity]:
        """Scan a sport for PM vs sportsbook mispricings."""
        opportunities = []
        sb_games = await self.get_sportsbook_odds(sport_key)
        if not sb_games:
            return opportunities

        log(f"Found {len(sb_games)} {sport_name} games on sportsbooks")

        for game in sb_games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            commence = game.get("commence_time", "")[:10]

            pm_match = await self.find_pm_match(home, away, commence, pm_prefix, sport_name)
            if not pm_match:
                continue

            slug = pm_match["slug"]
            event = pm_match["event"]

            pm_prices = self.extract_moneyline(event)
            if not pm_prices:
                continue

            sb_prices = self.calc_sb_consensus(game)
            if not sb_prices:
                continue

            for outcome, pm_prob in pm_prices.items():
                sb_prob = None
                for sb_name, sb_p in sb_prices.items():
                    if outcome.lower() in sb_name.lower() or sb_name.split()[-1].lower() in outcome.lower():
                        sb_prob = sb_p
                        break

                if sb_prob is None:
                    continue

                edge_pct = (sb_prob - pm_prob) * 100

                if abs(edge_pct) >= MIN_EDGE_PCT:
                    action = "BUY" if edge_pct > 0 else "SELL"
                    log(f"  EDGE: {outcome} PM={pm_prob:.1%} vs SB={sb_prob:.1%} = {edge_pct:+.1f}% [{action}]")

                    commence_time = game.get("commence_time", "")
                    if commence_time:
                        resolution = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                    else:
                        resolution = datetime.now()

                    opportunities.append(SportsbookOpportunity(
                        market_slug=slug,
                        event_title=event.get("title", ""),
                        outcome=outcome,
                        pm_price=pm_prob,
                        sb_price=sb_prob,
                        edge_pct=edge_pct,
                        action=action,
                        liquidity_usd=0,
                        resolution_time=resolution,
                        sport=sport_name,
                        books_count=len(game.get("bookmakers", [])),
                    ))

        return opportunities

    async def scan_all(self) -> list[SportsbookOpportunity]:
        """Scan all monitored sports for opportunities."""
        all_opportunities = []

        for sport_key, pm_prefix, sport_name in MONITORED_SPORTS:
            log(f"Scanning {sport_name}...")
            opps = await self.scan_sport(sport_key, pm_prefix, sport_name)
            all_opportunities.extend(opps)

        all_opportunities.sort(key=lambda x: abs(x.edge_pct), reverse=True)
        return all_opportunities


async def main():
    """Test the sportsbook scanner."""
    async with SportsbookComparator() as scanner:
        opportunities = await scanner.scan_all()
        print(f"\nFound {len(opportunities)} opportunities")
        for opp in opportunities[:10]:
            print(f"\n{opp.action} {opp.outcome} @ {opp.pm_price:.1%}")
            print(f"  Market: {opp.market_slug}")
            print(f"  SB consensus: {opp.sb_price:.1%} ({opp.books_count} books)")
            print(f"  Edge: {opp.edge_pct:+.1f}%")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
