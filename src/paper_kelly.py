"""
Paper Trading with Kelly Criterion Position Sizing

Simulates trading all opportunities with optimal position sizing.
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

PORTFOLIO_FILE = "./data/kelly_portfolio.json"


@dataclass
class Position:
    """A paper trading position."""
    market_slug: str
    outcome: str
    entry_price: float  # 0.855 = 85.5%
    shares: float
    cost_basis: float  # Total USD spent
    entry_time: str
    edge_pct: float
    kelly_fraction: float
    category: str  # "sports", "longshot", "strategy"
    fair_value: float  # Our estimated true probability
    potential_payout: float  # If wins
    status: str = "open"  # "open", "won", "lost"
    resolution_value: Optional[float] = None
    pnl: Optional[float] = None


@dataclass
class Portfolio:
    """Paper trading portfolio."""
    initial_capital: float = 10000.0
    cash: float = 10000.0
    positions: list = field(default_factory=list)
    closed_positions: list = field(default_factory=list)
    total_pnl: float = 0.0
    win_count: int = 0
    loss_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions": [asdict(p) if isinstance(p, Position) else p for p in self.positions],
            "closed_positions": [asdict(p) if isinstance(p, Position) else p for p in self.closed_positions],
            "total_pnl": self.total_pnl,
            "win_count": self.win_count,
            "loss_count": self.loss_count,
            "created_at": self.created_at
        }


def load_portfolio() -> Portfolio:
    """Load portfolio from disk."""
    try:
        path = Path(PORTFOLIO_FILE)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                portfolio = Portfolio(
                    initial_capital=data.get("initial_capital", 10000),
                    cash=data.get("cash", 10000),
                    total_pnl=data.get("total_pnl", 0),
                    win_count=data.get("win_count", 0),
                    loss_count=data.get("loss_count", 0),
                    created_at=data.get("created_at", datetime.now().isoformat())
                )
                portfolio.positions = data.get("positions", [])
                portfolio.closed_positions = data.get("closed_positions", [])
                return portfolio
    except Exception as e:
        print(f"Error loading portfolio: {e}")
    return Portfolio()


def save_portfolio(portfolio: Portfolio):
    """Save portfolio to disk."""
    path = Path(PORTFOLIO_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(portfolio.to_dict(), f, indent=2)


def kelly_fraction(win_prob: float, odds: float, half_kelly: bool = True) -> float:
    """
    Calculate Kelly criterion bet fraction.

    Args:
        win_prob: Estimated probability of winning (0-1)
        odds: Net odds (e.g., 0.17 for 85.5c -> $1 bet)
        half_kelly: Use half-Kelly for safety (recommended)

    Returns:
        Fraction of bankroll to bet (0-1)
    """
    if odds <= 0 or win_prob <= 0 or win_prob >= 1:
        return 0.0

    # Kelly formula: f* = (bp - q) / b
    # Where b = odds, p = win prob, q = loss prob
    b = odds
    p = win_prob
    q = 1 - p

    kelly = (b * p - q) / b

    # Never bet negative (no edge)
    if kelly <= 0:
        return 0.0

    # Cap at 25% max
    kelly = min(kelly, 0.25)

    # Half-Kelly for safety
    if half_kelly:
        kelly *= 0.5

    return kelly


def calculate_position_size(
    entry_price: float,
    fair_value: float,
    bankroll: float,
    half_kelly: bool = True,
    max_position_pct: float = 0.10  # 10% max per position
) -> tuple[float, float, float]:
    """
    Calculate position size using Kelly criterion.

    Args:
        entry_price: Current market price (0.855 = 85.5%)
        fair_value: Our estimated true probability
        bankroll: Total available capital
        half_kelly: Use half-Kelly
        max_position_pct: Maximum position as % of bankroll

    Returns:
        (bet_size_usd, kelly_fraction, edge_pct)
    """
    # Edge = fair value - entry price
    edge = fair_value - entry_price
    edge_pct = edge * 100

    if edge <= 0:
        return 0.0, 0.0, edge_pct

    # Calculate odds (what we get if we win)
    # Buying at entry_price, payout is $1 per share
    # Net profit per dollar risked = (1 - entry_price) / entry_price
    odds = (1 - entry_price) / entry_price

    # Kelly fraction
    kf = kelly_fraction(fair_value, odds, half_kelly)

    # Calculate bet size
    bet_size = bankroll * kf

    # Apply max position cap
    max_bet = bankroll * max_position_pct
    bet_size = min(bet_size, max_bet)

    return bet_size, kf, edge_pct


def paper_trade_sports_edge(
    portfolio: Portfolio,
    market_slug: str,
    team: str,
    pm_price: float,
    vegas_prob: float
) -> Optional[Position]:
    """
    Paper trade a sports edge opportunity.

    Args:
        pm_price: Polymarket price (0.855 = 85.5%)
        vegas_prob: Vegas implied probability (our fair value estimate)
    """
    bet_size, kf, edge_pct = calculate_position_size(
        entry_price=pm_price,
        fair_value=vegas_prob,
        bankroll=portfolio.cash
    )

    if bet_size < 1:  # Min $1 bet
        print(f"[KELLY] Skip {team}: no edge or too small (Kelly={kf:.2%}, edge={edge_pct:+.1f}%)")
        return None

    # Calculate shares
    shares = bet_size / pm_price
    potential_payout = shares * 1.0  # $1 per share if wins

    position = Position(
        market_slug=market_slug,
        outcome=team,
        entry_price=pm_price,
        shares=shares,
        cost_basis=bet_size,
        entry_time=datetime.now().isoformat(),
        edge_pct=edge_pct,
        kelly_fraction=kf,
        category="sports",
        fair_value=vegas_prob,
        potential_payout=potential_payout
    )

    # Deduct from cash
    portfolio.cash -= bet_size
    portfolio.positions.append(asdict(position))

    print(f"[KELLY] BUY {team}")
    print(f"        Entry: {pm_price:.1%} | Fair: {vegas_prob:.1%} | Edge: {edge_pct:+.1f}%")
    print(f"        Kelly: {kf:.2%} | Size: ${bet_size:.2f} | Shares: {shares:.1f}")
    print(f"        Potential: ${potential_payout:.2f} (+${potential_payout - bet_size:.2f})")

    return position


def paper_trade_longshot(
    portfolio: Portfolio,
    market_slug: str,
    question: str,
    entry_price: float,  # 0.002 = 0.2 cents
    est_true_prob: float = None,  # Our estimate of true probability
    category: str = "crypto"
) -> Optional[Position]:
    """
    Paper trade a longshot opportunity.

    For longshots, we assume a small edge (e.g., 50% more likely than market implies).
    """
    # If no estimate provided, assume 50% edge over market
    if est_true_prob is None:
        est_true_prob = entry_price * 1.5  # 50% edge assumption

    bet_size, kf, edge_pct = calculate_position_size(
        entry_price=entry_price,
        fair_value=est_true_prob,
        bankroll=portfolio.cash,
        max_position_pct=0.02  # Max 2% per longshot (they're risky!)
    )

    if bet_size < 1:
        print(f"[KELLY] Skip longshot: Kelly too small ({kf:.4%})")
        return None

    # Calculate shares
    shares = bet_size / entry_price
    potential_payout = shares * 1.0
    multiplier = (1 / entry_price) - 1

    position = Position(
        market_slug=market_slug,
        outcome="Yes",
        entry_price=entry_price,
        shares=shares,
        cost_basis=bet_size,
        entry_time=datetime.now().isoformat(),
        edge_pct=edge_pct,
        kelly_fraction=kf,
        category=f"longshot-{category}",
        fair_value=est_true_prob,
        potential_payout=potential_payout
    )

    portfolio.cash -= bet_size
    portfolio.positions.append(asdict(position))

    print(f"[KELLY] BUY LONGSHOT ({category})")
    print(f"        {question[:60]}...")
    print(f"        Entry: {entry_price:.3%} ({entry_price*100:.2f}c) | {multiplier:.0f}x potential")
    print(f"        Kelly: {kf:.3%} | Size: ${bet_size:.2f} | Shares: {shares:,.0f}")
    print(f"        Potential: ${potential_payout:,.2f}")

    return position


def print_portfolio_summary(portfolio: Portfolio):
    """Print portfolio summary."""
    total_invested = sum(p["cost_basis"] for p in portfolio.positions)
    total_potential = sum(p["potential_payout"] for p in portfolio.positions)

    print("\n" + "="*60)
    print("KELLY PAPER PORTFOLIO")
    print("="*60)
    print(f"Initial Capital:  ${portfolio.initial_capital:,.2f}")
    print(f"Cash:             ${portfolio.cash:,.2f}")
    print(f"Invested:         ${total_invested:,.2f}")
    print(f"Potential Value:  ${total_potential:,.2f}")
    print(f"Open Positions:   {len(portfolio.positions)}")
    print(f"Closed:           {len(portfolio.closed_positions)}")
    print(f"Win/Loss:         {portfolio.win_count}/{portfolio.loss_count}")
    print(f"Total P&L:        ${portfolio.total_pnl:+,.2f}")
    print("="*60)

    if portfolio.positions:
        print("\nOPEN POSITIONS:")
        print("-"*60)
        for p in portfolio.positions:
            mult = (1 / p["entry_price"]) - 1 if p["entry_price"] > 0 else 0
            print(f"  {p['category']:12} | {p['outcome'][:20]:20} | ${p['cost_basis']:>8.2f} | {mult:>6.0f}x")


async def run_paper_trades():
    """Run paper trades on current opportunities."""
    import httpx
    from src.config import GAMMA_API_BASE, ODDS_API_KEY

    print("\n" + "="*60)
    print("KELLY CRITERION PAPER TRADING")
    print("="*60)

    # Load or create portfolio
    portfolio = load_portfolio()
    print(f"\nStarting cash: ${portfolio.cash:,.2f}")

    # =========================================
    # 1. SPORTS EDGES
    # =========================================
    print("\n--- SPORTS EDGES ---")

    # Pistons: PM 85.5% vs Vegas 89.6%
    paper_trade_sports_edge(
        portfolio,
        market_slug="nba-det-xxx-2026-01-25",  # Placeholder
        team="Pistons",
        pm_price=0.855,
        vegas_prob=0.896
    )

    # Canucks: PM 41.5% vs Vegas 44.9%
    paper_trade_sports_edge(
        portfolio,
        market_slug="nhl-van-xxx-2026-01-25",
        team="Canucks",
        pm_price=0.415,
        vegas_prob=0.449
    )

    # =========================================
    # 2. LONGSHOTS (from scanner)
    # =========================================
    print("\n--- LONGSHOTS ---")

    # Fetch actual longshot opportunities
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"{GAMMA_API_BASE}/markets?active=true&closed=false&limit=500"
        resp = await client.get(url)
        markets = resp.json() if resp.status_code == 200 else []

        longshot_count = 0
        for market in markets:
            try:
                prices_str = market.get("outcomePrices", "[]")
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                prices = [float(p) for p in prices]

                if not prices:
                    continue

                # Find ultra-cheap outcomes (< 0.5 cents = 0.005)
                for i, price in enumerate(prices):
                    if 0.001 < price < 0.005:  # 0.1c to 0.5c
                        liquidity = float(market.get("liquidity", 0))
                        if liquidity < 500:
                            continue

                        question = market.get("question", "")
                        slug = market.get("slug", "")

                        # Categorize
                        q_lower = question.lower()
                        if any(k in q_lower for k in ["btc", "bitcoin", "eth", "crypto", "price"]):
                            cat = "crypto"
                        elif any(k in q_lower for k in ["war", "strike", "military"]):
                            cat = "geopolitics"
                        else:
                            cat = "other"

                        paper_trade_longshot(
                            portfolio,
                            market_slug=slug,
                            question=question,
                            entry_price=price,
                            category=cat
                        )
                        longshot_count += 1

                        if longshot_count >= 10:  # Max 10 longshots
                            break

                if longshot_count >= 10:
                    break

            except Exception as e:
                continue

    # =========================================
    # SAVE AND PRINT SUMMARY
    # =========================================
    save_portfolio(portfolio)
    print_portfolio_summary(portfolio)

    return portfolio


async def main():
    """Main entry point."""
    portfolio = await run_paper_trades()
    return portfolio


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
