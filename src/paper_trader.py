"""
Standalone Paper Trading CLI for poly-scout.

Uses Kelly Criterion for position sizing based on estimated edge.
Monitors new markets and simulates trades without real money.

Usage:
    python -m src.paper_trader              # Run interactive mode
    python -m src.paper_trader --status     # Show portfolio status
    python -m src.paper_trader --reset      # Reset portfolio to starting balance
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import httpx

from src.config import GAMMA_API_BASE
from src.new_market_monitor import NewMarketMonitor


PAPER_PORTFOLIO_FILE = "./data/paper_portfolio.json"

# Kelly Criterion settings
KELLY_FRACTION = 0.5  # Half-Kelly for safety
MAX_POSITION_PCT = 0.05  # Never risk more than 5% per trade
MIN_POSITION_PCT = 0.01  # Minimum 1% to make trade worthwhile

# Profit-taking thresholds (like reference wallet)
TAKE_PARTIAL_PROFIT_MULT = 2.0  # Sell half at 2x
TAKE_FULL_PROFIT_MULT = 5.0     # Sell all at 5x


def log(msg: str):
    print(f"[PAPER] {msg}", flush=True)


def estimate_win_probability(market_price: float) -> float:
    """
    Estimate win probability from market price.

    Conservative approach:
    - If buying at $0.08, assume true value is ~2x market price = 16%
    - This is conservative because markets are mostly efficient
    - We assume our edge is finding the rare mispricing

    Returns estimated probability (0-1)
    """
    # Conservative: true value = market price * 2
    # This assumes we only bet when we think it's worth 2x what we're paying
    estimated_true_prob = min(market_price * 2.0, 0.95)

    # Floor at 5% to avoid divide-by-zero issues
    return max(estimated_true_prob, 0.05)


def kelly_criterion(win_prob: float, entry_price: float) -> float:
    """
    Calculate optimal Kelly fraction for a Polymarket position.

    For binary outcome markets:
    - Win: $1.00 payout per share (bought at entry_price)
    - Loss: $0 payout

    Kelly formula: f* = (p * b - q) / b
    where:
        p = probability of winning
        q = probability of losing (1-p)
        b = net odds (payout / stake - 1)

    For Polymarket:
        b = (1.0 - entry_price) / entry_price
        f* = (p * (1-entry) - q * entry) / (1 - entry)

    Returns fraction of bankroll to bet (0-1)
    """
    if entry_price <= 0 or entry_price >= 1:
        return 0.0

    p = win_prob
    q = 1 - p

    # Net odds: profit per share / cost per share
    b = (1.0 - entry_price) / entry_price

    # Kelly formula
    kelly = (p * b - q) / b

    # Apply half-Kelly for safety
    kelly = kelly * KELLY_FRACTION

    # Clamp to reasonable bounds
    kelly = max(0, min(kelly, MAX_POSITION_PCT))

    return kelly


@dataclass
class PaperPosition:
    slug: str
    title: str
    outcome: str
    entry_price: float
    shares: float
    amount_invested: float
    entry_time: str
    estimated_win_prob: float
    kelly_fraction: float
    status: str = "open"
    exit_price: Optional[float] = None
    pnl: Optional[float] = None


class PaperTrader:
    """Standalone paper trading simulator with Kelly position sizing."""

    def __init__(self, starting_balance: float = 10000.0):
        self.starting_balance = starting_balance
        self.portfolio = self._load_portfolio()
        self.client = httpx.AsyncClient(timeout=30)
        log(f"Portfolio: ${self.portfolio['current_balance']:,.2f} balance, "
            f"{len(self.portfolio['positions'])} open positions")

    def _load_portfolio(self) -> dict:
        """Load portfolio from disk."""
        try:
            path = Path(PAPER_PORTFOLIO_FILE)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        except Exception:
            pass
        return {
            "starting_balance": self.starting_balance,
            "current_balance": self.starting_balance,
            "positions": [],
            "closed_positions": [],
            "total_pnl": 0.0,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
        }

    def _save_portfolio(self):
        """Save portfolio to disk."""
        try:
            path = Path(PAPER_PORTFOLIO_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(self.portfolio, f, indent=2)
        except Exception as e:
            log(f"Error saving portfolio: {e}")

    def reset_portfolio(self):
        """Reset portfolio to starting balance."""
        self.portfolio = {
            "starting_balance": self.starting_balance,
            "current_balance": self.starting_balance,
            "positions": [],
            "closed_positions": [],
            "total_pnl": 0.0,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
        }
        self._save_portfolio()
        log(f"Portfolio reset to ${self.starting_balance:,.2f}")

    def calculate_position_size(self, entry_price: float, mispricing_score: float = 0.5) -> tuple[float, float, float]:
        """
        Calculate position size using Kelly Criterion.

        Args:
            entry_price: Price we're buying at (0-1)
            mispricing_score: Confidence in mispricing (0-1)

        Returns:
            (amount_to_invest, kelly_fraction, estimated_win_prob)
        """
        # Estimate win probability
        win_prob = estimate_win_probability(entry_price)

        # Adjust for mispricing confidence
        # Higher mispricing score = more confident in our edge
        adjusted_win_prob = win_prob * (0.8 + mispricing_score * 0.4)  # 0.8 to 1.2x
        adjusted_win_prob = min(adjusted_win_prob, 0.95)

        # Calculate Kelly fraction
        kelly = kelly_criterion(adjusted_win_prob, entry_price)

        # Skip if Kelly suggests no bet
        if kelly < MIN_POSITION_PCT:
            return 0, kelly, adjusted_win_prob

        # Calculate dollar amount
        amount = self.portfolio["current_balance"] * kelly

        return amount, kelly, adjusted_win_prob

    def open_position(self, slug: str, title: str, outcome: str, price: float,
                      mispricing_score: float = 0.5) -> Optional[PaperPosition]:
        """Open a new paper position using Kelly sizing."""

        amount, kelly, win_prob = self.calculate_position_size(price, mispricing_score)

        if amount < 1.0:  # Minimum $1 trade
            log(f"SKIP: Kelly fraction too low ({kelly:.1%})")
            return None

        if amount > self.portfolio["current_balance"]:
            amount = self.portfolio["current_balance"]

        shares = amount / price

        position = PaperPosition(
            slug=slug,
            title=title[:100],
            outcome=outcome,
            entry_price=price,
            shares=shares,
            amount_invested=amount,
            entry_time=datetime.now().isoformat(),
            estimated_win_prob=win_prob,
            kelly_fraction=kelly,
        )

        self.portfolio["positions"].append(asdict(position))
        self.portfolio["current_balance"] -= amount
        self.portfolio["total_trades"] += 1
        self._save_portfolio()

        log(f"OPENED: {shares:.1f} {outcome} @ ${price:.3f} = ${amount:.2f}")
        log(f"  Kelly: {kelly:.1%} | Est. win prob: {win_prob:.1%}")
        return position

    async def check_resolutions(self) -> list:
        """Check if any open positions have resolved."""
        resolved = []

        positions_copy = self.portfolio["positions"][:]

        for pos in positions_copy:
            try:
                url = f"{GAMMA_API_BASE}/events?slug={pos['slug']}"
                resp = await self.client.get(url)
                if resp.status_code != 200:
                    continue

                events = resp.json()
                if not events:
                    continue

                event = events[0]
                if not event.get("closed"):
                    continue

                # Market closed - determine winner
                for market in event.get("markets", []):
                    winner = market.get("winner")
                    if winner:
                        won = (pos["outcome"].upper() == winner.upper())

                        if won:
                            payout = pos["shares"] * 1.0
                            pnl = payout - pos["amount_invested"]
                            self.portfolio["wins"] += 1
                            log(f"WON: {pos['title'][:30]}... P&L: +${pnl:.2f}")
                        else:
                            payout = 0
                            pnl = -pos["amount_invested"]
                            self.portfolio["losses"] += 1
                            log(f"LOST: {pos['title'][:30]}... P&L: -${pos['amount_invested']:.2f}")

                        pos["status"] = "won" if won else "lost"
                        pos["exit_price"] = 1.0 if won else 0.0
                        pos["pnl"] = pnl

                        self.portfolio["current_balance"] += payout
                        self.portfolio["total_pnl"] += pnl
                        self.portfolio["closed_positions"].append(pos)
                        self.portfolio["positions"].remove(pos)

                        resolved.append(pos)
                        break

            except Exception as e:
                log(f"Error checking {pos['slug']}: {e}")
                continue

        if resolved:
            self._save_portfolio()

        return resolved

    async def check_profit_taking(self) -> list:
        """
        Check open positions for profit-taking opportunities.
        Like reference wallet: sell half at 2x, all at 5x.
        """
        profit_taken = []

        positions_copy = self.portfolio["positions"][:]

        for pos in positions_copy:
            try:
                # Get current market prices
                url = f"{GAMMA_API_BASE}/events?slug={pos['slug']}"
                resp = await self.client.get(url)
                if resp.status_code != 200:
                    continue

                events = resp.json()
                if not events:
                    continue

                event = events[0]
                if event.get("closed"):
                    continue  # Will be handled by check_resolutions

                # Find current price for our outcome
                current_price = None
                for market in event.get("markets", []):
                    outcomes = market.get("outcomes", [])
                    prices_str = market.get("outcomePrices", "[]")
                    try:
                        prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                        prices = [float(p) for p in prices]
                    except Exception:
                        continue

                    # Find price for our outcome
                    for i, outcome in enumerate(outcomes):
                        if outcome.upper() == pos["outcome"].upper() and i < len(prices):
                            current_price = prices[i]
                            break
                    if current_price:
                        break

                if current_price is None:
                    continue

                entry_price = pos["entry_price"]
                price_mult = current_price / entry_price if entry_price > 0 else 0

                # Check for full profit (5x)
                if price_mult >= TAKE_FULL_PROFIT_MULT:
                    payout = pos["shares"] * current_price
                    pnl = payout - pos["amount_invested"]

                    log(f"PROFIT 5x+: {pos['title'][:30]}... @ ${current_price:.3f} ({price_mult:.1f}x)")
                    log(f"  P&L: +${pnl:.2f}")

                    pos["status"] = "profit_5x"
                    pos["exit_price"] = current_price
                    pos["pnl"] = pnl

                    self.portfolio["current_balance"] += payout
                    self.portfolio["total_pnl"] += pnl
                    self.portfolio["wins"] += 1
                    self.portfolio["closed_positions"].append(pos)
                    self.portfolio["positions"].remove(pos)

                    profit_taken.append({"pos": pos, "type": "full", "mult": price_mult})

                # Check for partial profit (2x) - only if not already taken
                elif price_mult >= TAKE_PARTIAL_PROFIT_MULT and not pos.get("partial_profit_taken"):
                    # Sell half the position
                    half_shares = pos["shares"] / 2
                    half_invested = pos["amount_invested"] / 2
                    payout = half_shares * current_price
                    pnl = payout - half_invested

                    log(f"PROFIT 2x: {pos['title'][:30]}... @ ${current_price:.3f} ({price_mult:.1f}x)")
                    log(f"  Sold half: +${pnl:.2f} | Remaining: {half_shares:.1f} shares")

                    # Update position to reflect half sold
                    pos["shares"] = half_shares
                    pos["amount_invested"] = half_invested
                    pos["partial_profit_taken"] = True

                    self.portfolio["current_balance"] += payout
                    self.portfolio["total_pnl"] += pnl

                    profit_taken.append({"pos": pos, "type": "partial", "mult": price_mult, "pnl": pnl})

            except Exception as e:
                continue

        if profit_taken:
            self._save_portfolio()

        return profit_taken

    def get_summary(self) -> str:
        """Get portfolio summary."""
        p = self.portfolio
        open_value = sum(pos["amount_invested"] for pos in p["positions"])
        win_rate = (p["wins"] / max(1, p["wins"] + p["losses"]) * 100)
        total_return = (p['total_pnl'] / p['starting_balance'] * 100) if p['starting_balance'] > 0 else 0

        return f"""PAPER TRADING (Kelly)

Balance: ${p['current_balance']:,.2f}
Open: {len(p['positions'])} (${open_value:,.2f})
P&L: ${p['total_pnl']:+,.2f} ({total_return:+.1f}%)
Record: {p['wins']}W / {p['losses']}L ({win_rate:.0f}%)"""

    def get_detailed_status(self) -> str:
        """Get detailed portfolio status."""
        p = self.portfolio

        lines = [
            "=" * 50,
            "  PAPER TRADING PORTFOLIO (Kelly Criterion)",
            "=" * 50,
            "",
            f"Starting Balance:  ${p['starting_balance']:>12,.2f}",
            f"Current Balance:   ${p['current_balance']:>12,.2f}",
            f"Total P&L:         ${p['total_pnl']:>+12,.2f}",
            f"Return:            {p['total_pnl']/p['starting_balance']*100:>+11.1f}%",
            "",
            f"Total Trades: {p['total_trades']}",
            f"Wins: {p['wins']} | Losses: {p['losses']} | Win Rate: {p['wins']/max(1, p['wins']+p['losses'])*100:.0f}%",
            "",
        ]

        if p["positions"]:
            lines.append("OPEN POSITIONS:")
            lines.append("-" * 50)
            for pos in p["positions"]:
                lines.append(f"  {pos['title'][:40]}...")
                lines.append(f"    {pos['outcome']} @ ${pos['entry_price']:.3f} x {pos['shares']:.1f} = ${pos['amount_invested']:.2f}")
                lines.append(f"    Kelly: {pos.get('kelly_fraction', 0)*100:.1f}% | Est. win: {pos.get('estimated_win_prob', 0)*100:.0f}%")
            lines.append("")

        if p["closed_positions"]:
            recent = p["closed_positions"][-5:]  # Last 5
            lines.append("RECENT TRADES:")
            lines.append("-" * 50)
            for pos in reversed(recent):
                status = "WIN" if pos["status"] == "won" else "LOSS"
                lines.append(f"  [{status}] {pos['title'][:35]}... P&L: ${pos['pnl']:+,.2f}")

        return "\n".join(lines)

    async def close(self):
        """Cleanup."""
        self._save_portfolio()
        await self.client.aclose()


async def run_paper_trading():
    """Run paper trading on new market opportunities."""
    log("=" * 50)
    log("  PAPER TRADING - New Market Monitor")
    log("  Using Kelly Criterion for position sizing")
    log("=" * 50)

    trader = PaperTrader(starting_balance=10000.0)
    monitor = NewMarketMonitor()

    log(f"\n{trader.get_detailed_status()}\n")
    log("Scanning for opportunities every 60 seconds...")
    log("Press Ctrl+C to stop\n")

    try:
        while True:
            # Check for new market opportunities
            opportunities = await monitor.scan_for_new_markets()

            for opp in opportunities:
                if opp.mispricing_score >= 0.3:
                    # Determine which outcome to buy
                    if opp.recommendation.startswith("BUY"):
                        parts = opp.recommendation.split()
                        outcome = parts[1] if len(parts) > 1 else "YES"
                    else:
                        outcome = "YES" if opp.prices[0] < opp.prices[1] else "NO"

                    cheap_price = min(opp.prices)

                    log(f"\nOPPORTUNITY: {opp.title[:50]}...")
                    log(f"  Prices: {opp.prices} | Score: {opp.mispricing_score:.0%}")

                    # Open paper position with Kelly sizing
                    position = trader.open_position(
                        slug=opp.slug,
                        title=opp.title,
                        outcome=outcome,
                        price=cheap_price,
                        mispricing_score=opp.mispricing_score,
                    )

                    if position:
                        log(f"\n{trader.get_summary()}\n")

            # Check for profit-taking opportunities (2x partial, 5x full)
            profit_taken = await trader.check_profit_taking()
            for pt in profit_taken:
                pos = pt["pos"]
                if pt["type"] == "full":
                    log(f"\nPROFIT TAKEN (5x): {pos['title'][:40]}...")
                    log(f"  Sold all @ {pt['mult']:.1f}x | P&L: ${pos['pnl']:+,.2f}")
                else:
                    log(f"\nPARTIAL PROFIT (2x): {pos['title'][:40]}...")
                    log(f"  Sold half @ {pt['mult']:.1f}x | P&L: ${pt['pnl']:+,.2f}")
                log(f"\n{trader.get_summary()}\n")

            # Check for resolved positions
            resolved = await trader.check_resolutions()
            for pos in resolved:
                status = "WON" if pos["status"] == "won" else "LOST"
                log(f"\nRESOLVED: {pos['title'][:40]}...")
                log(f"  {status} | P&L: ${pos['pnl']:+,.2f}")
                log(f"\n{trader.get_summary()}\n")

            await asyncio.sleep(60)  # Scan every minute

    except KeyboardInterrupt:
        log("\nStopping...")
    finally:
        log(f"\n{trader.get_detailed_status()}")
        await trader.close()
        await monitor.close()


def main():
    parser = argparse.ArgumentParser(
        description="Paper Trading CLI with Kelly Criterion sizing"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show portfolio status and exit"
    )
    parser.add_argument(
        "--reset", "-r",
        action="store_true",
        help="Reset portfolio to starting balance"
    )
    parser.add_argument(
        "--balance", "-b",
        type=float,
        default=10000.0,
        help="Starting balance (default: $10,000)"
    )

    args = parser.parse_args()

    if args.status:
        trader = PaperTrader(starting_balance=args.balance)
        print(trader.get_detailed_status())
        return

    if args.reset:
        trader = PaperTrader(starting_balance=args.balance)
        trader.reset_portfolio()
        print(trader.get_detailed_status())
        return

    # Run interactive paper trading
    asyncio.run(run_paper_trading())


if __name__ == "__main__":
    main()
