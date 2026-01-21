"""
Realistic Paper Trading CLI for poly-scout.

Uses CLOB API for order book depth and calculates realistic fills.
No more fantasy 100x returns - this simulates actual market conditions.

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
from typing import Optional, Tuple

import httpx

from src.config import GAMMA_API_BASE, CLOB_API_BASE
from src.new_market_monitor import NewMarketMonitor

# Try to import SDK client (optional, falls back to httpx)
try:
    from src.polymarket_client import AsyncPolymarketClient
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

USE_SDK = True  # Set to True to use SDK, False for raw httpx


PAPER_PORTFOLIO_FILE = "./data/paper_portfolio.json"

# Position sizing
MAX_POSITION_PCT = 0.05  # Never risk more than 5% per trade
MIN_POSITION_USD = 5.0   # Minimum $5 trade
MAX_POSITION_USD = 500.0 # Maximum $500 per trade

# Liquidity constraints
MAX_BOOK_DEPTH_PCT = 0.10  # Only use 10% of available book depth
MIN_LIQUIDITY_USD = 50.0   # Skip if less than $50 liquidity

# Profit-taking thresholds (Hybrid Sniper Strategy)
TAKE_PROFIT_MULT = 1.5          # Sell all at 1.5x (50% gain) - quick flip
TAKE_PARTIAL_PROFIT_MULT = 2.0  # Sell half at 2x
TAKE_FULL_PROFIT_MULT = 3.0     # Sell all at 3x (was 5x, now more aggressive)

# Hybrid time-based exit thresholds
FLIP_WINDOW_HOURS = 48          # Try to flip in first 48h
CUT_LOSS_HOURS = 24             # Cut losses after 24h if down significantly
CUT_LOSS_THRESHOLD = -0.50      # Cut if down 50%+

# Exit liquidity minimum
MIN_EXIT_LIQUIDITY_USD = 100.0  # Need at least $100 in bids to enter


def log(msg: str):
    print(f"[PAPER] {msg}", flush=True)


@dataclass
class OrderBookLevel:
    """A single level in the order book."""
    price: float
    size: float  # Number of shares at this price


@dataclass
class FillResult:
    """Result of simulating a fill against the order book."""
    shares_filled: float
    avg_price: float
    total_cost: float
    slippage_pct: float
    book_depth_used_pct: float


class PaperTrader:
    """Realistic paper trading simulator with order book depth checking."""

    def __init__(self, starting_balance: float = 10000.0):
        self.starting_balance = starting_balance
        self.portfolio = self._load_portfolio()
        self.client = httpx.AsyncClient(timeout=30)
        
        # Initialize SDK client if available
        self.sdk_client = None
        if USE_SDK and SDK_AVAILABLE:
            try:
                self.sdk_client = AsyncPolymarketClient()
                log("SDK client initialized")
            except Exception as e:
                log(f"SDK init failed, using httpx: {e}")
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
        return self._create_empty_portfolio()

    def _create_empty_portfolio(self) -> dict:
        return {
            "starting_balance": self.starting_balance,
            "current_balance": self.starting_balance,
            "positions": [],
            "closed_positions": [],
            "total_pnl": 0.0,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "skipped_low_liquidity": 0,
            # Hybrid sniper tracking
            "flips": 0,                      # Successful price correction exits (1.5x-3x)
            "flip_pnl": 0.0,                 # P&L from flips
            "cuts": 0,                       # Loss cuts (-50% after 24h)
            "cut_pnl": 0.0,                  # P&L from cuts (negative)
            "resolutions": 0,                # Positions held to resolution (win/loss)
            "resolution_pnl": 0.0,           # P&L from resolutions
            "skipped_no_exit_liquidity": 0,  # Skipped due to no bid liquidity
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
        self.portfolio = self._create_empty_portfolio()
        self._save_portfolio()
        log(f"Portfolio reset to ${self.starting_balance:,.2f}")

    async def fetch_order_book(self, token_id: str) -> Tuple[list, list]:
        """
        Fetch order book from CLOB API (or SDK if available).

        Returns (bids, asks) where each is a list of OrderBookLevel.
        To BUY, we need to walk the ASKS (people selling to us).
        """
        if not token_id:
            return [], []

        # Try SDK first if available
        if self.sdk_client:
            try:
                book = await self.sdk_client.get_order_book(token_id)
                if book:
                    bids = [OrderBookLevel(price=l.price, size=l.size) for l in book.bids]
                    asks = [OrderBookLevel(price=l.price, size=l.size) for l in book.asks]
                    asks.sort(key=lambda x: x.price)
                    bids.sort(key=lambda x: x.price, reverse=True)
                    return bids, asks
            except Exception as e:
                log(f"SDK order book failed, falling back to httpx: {e}")

        # Fallback to raw httpx
        try:
            url = f"{CLOB_API_BASE}/book?token_id={token_id}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return [], []

            data = resp.json()

            bids = []
            for level in data.get("bids", []):
                bids.append(OrderBookLevel(
                    price=float(level.get("price", 0)),
                    size=float(level.get("size", 0))
                ))

            asks = []
            for level in data.get("asks", []):
                asks.append(OrderBookLevel(
                    price=float(level.get("price", 0)),
                    size=float(level.get("size", 0))
                ))

            # Sort asks by price ascending (cheapest first)
            asks.sort(key=lambda x: x.price)
            # Sort bids by price descending (highest first)
            bids.sort(key=lambda x: x.price, reverse=True)

            return bids, asks

        except Exception as e:
            log(f"Error fetching order book: {e}")
            return [], []

    def simulate_buy(self, asks: list, max_spend: float) -> Optional[FillResult]:
        """
        Simulate buying by walking the ask side of the book.

        Args:
            asks: List of OrderBookLevel, sorted by price ascending
            max_spend: Maximum USD to spend

        Returns:
            FillResult with actual fill details, or None if can't fill
        """
        if not asks:
            return None

        # Calculate total available liquidity
        total_liquidity = sum(level.price * level.size for level in asks)

        if total_liquidity < MIN_LIQUIDITY_USD:
            return None

        # Limit to 10% of book depth
        max_spend = min(max_spend, total_liquidity * MAX_BOOK_DEPTH_PCT)

        if max_spend < MIN_POSITION_USD:
            return None

        # Walk the book
        total_cost = 0.0
        total_shares = 0.0
        best_price = asks[0].price if asks else 0

        remaining_spend = max_spend

        for level in asks:
            if remaining_spend <= 0:
                break

            level_cost = level.price * level.size

            if level_cost <= remaining_spend:
                # Take entire level
                total_cost += level_cost
                total_shares += level.size
                remaining_spend -= level_cost
            else:
                # Partial fill at this level
                shares_at_level = remaining_spend / level.price
                total_cost += remaining_spend
                total_shares += shares_at_level
                remaining_spend = 0

        if total_shares <= 0:
            return None

        avg_price = total_cost / total_shares
        slippage_pct = ((avg_price - best_price) / best_price * 100) if best_price > 0 else 0
        book_depth_used = total_cost / total_liquidity * 100 if total_liquidity > 0 else 0

        return FillResult(
            shares_filled=total_shares,
            avg_price=avg_price,
            total_cost=total_cost,
            slippage_pct=slippage_pct,
            book_depth_used_pct=book_depth_used,
        )

    def simulate_sell(self, bids: list, shares_to_sell: float) -> Optional[FillResult]:
        """
        Simulate selling by walking the bid side of the book.

        Args:
            bids: List of OrderBookLevel, sorted by price descending
            shares_to_sell: Number of shares to sell

        Returns:
            FillResult with actual fill details, or None if can't fill
        """
        if not bids or shares_to_sell <= 0:
            return None

        # Walk the book
        total_proceeds = 0.0
        total_shares_sold = 0.0
        best_price = bids[0].price if bids else 0

        remaining_shares = shares_to_sell

        for level in bids:
            if remaining_shares <= 0:
                break

            if level.size <= remaining_shares:
                # Take entire level
                total_proceeds += level.price * level.size
                total_shares_sold += level.size
                remaining_shares -= level.size
            else:
                # Partial fill at this level
                total_proceeds += level.price * remaining_shares
                total_shares_sold += remaining_shares
                remaining_shares = 0

        if total_shares_sold <= 0:
            return None

        avg_price = total_proceeds / total_shares_sold
        slippage_pct = ((best_price - avg_price) / best_price * 100) if best_price > 0 else 0

        return FillResult(
            shares_filled=total_shares_sold,
            avg_price=avg_price,
            total_cost=total_proceeds,  # Actually proceeds for sells
            slippage_pct=slippage_pct,
            book_depth_used_pct=0,  # Not relevant for sells
        )

    async def check_exit_liquidity(self, token_id: str) -> Tuple[bool, float, float]:
        """
        Check if there's enough bid liquidity to exit a position.

        For snipers, exit liquidity is CRITICAL - need bids to sell into
        when price corrects.

        Returns (can_exit, best_bid_price, total_bid_liquidity_usd)
        """
        bids, _ = await self.fetch_order_book(token_id)

        if not bids:
            return False, 0.0, 0.0

        # Calculate total bid liquidity (what we could sell into)
        total_bid_liquidity = sum(level.price * level.size for level in bids)
        best_bid = bids[0].price if bids else 0.0

        # Need at least MIN_EXIT_LIQUIDITY_USD in bids to consider exiting later
        can_exit = total_bid_liquidity >= MIN_EXIT_LIQUIDITY_USD

        return can_exit, best_bid, total_bid_liquidity

    async def open_position(self, slug: str, title: str, outcome: str,
                           token_id: str, target_price: float) -> bool:
        """
        Open a new paper position with realistic order book simulation.

        HYBRID SNIPER: Checks exit liquidity (bids) before entering.
        Snipers need to be able to SELL when price corrects.

        Returns True if position was opened, False if skipped.
        """
        # Calculate position size (max 5% of portfolio, capped at $500)
        max_spend = min(
            self.portfolio["current_balance"] * MAX_POSITION_PCT,
            MAX_POSITION_USD
        )

        if max_spend < MIN_POSITION_USD:
            log(f"SKIP: Insufficient balance for minimum position")
            return False

        # Fetch order book
        bids, asks = await self.fetch_order_book(token_id)

        if not asks:
            log(f"SKIP: No order book for {outcome}")
            self.portfolio["skipped_low_liquidity"] += 1
            return False

        # HYBRID SNIPER: Check exit liquidity (bids) BEFORE entering
        # Need bids to sell into when price corrects
        total_bid_liquidity = sum(level.price * level.size for level in bids) if bids else 0.0
        best_bid = bids[0].price if bids else 0.0

        if total_bid_liquidity < MIN_EXIT_LIQUIDITY_USD:
            log(f"SKIP: No exit liquidity (${total_bid_liquidity:.0f} < ${MIN_EXIT_LIQUIDITY_USD:.0f}) for {title[:30]}...")
            self.portfolio["skipped_no_exit_liquidity"] = self.portfolio.get("skipped_no_exit_liquidity", 0) + 1
            return False

        # Simulate the buy
        fill = self.simulate_buy(asks, max_spend)

        if not fill:
            log(f"SKIP: Low liquidity for {title[:30]}...")
            self.portfolio["skipped_low_liquidity"] += 1
            return False

        # Open the position with hybrid sniper tracking
        position = {
            "slug": slug,
            "title": title[:100],
            "outcome": outcome,
            "token_id": token_id,
            "entry_price": fill.avg_price,
            "shares": fill.shares_filled,
            "amount_invested": fill.total_cost,
            "entry_time": datetime.now().isoformat(),
            "slippage_pct": fill.slippage_pct,
            "status": "open",
            "exit_price": None,
            "pnl": None,
            # Hybrid sniper fields
            "entry_best_bid": best_bid,  # Best bid at entry time
            "entry_bid_liquidity": total_bid_liquidity,  # Total bid $ at entry
        }

        self.portfolio["positions"].append(position)
        self.portfolio["current_balance"] -= fill.total_cost
        self.portfolio["total_trades"] += 1
        self._save_portfolio()

        log(f"OPENED: {fill.shares_filled:.1f} {outcome} @ ${fill.avg_price:.4f}")
        log(f"  Cost: ${fill.total_cost:.2f} | Slippage: {fill.slippage_pct:.2f}% | Exit liq: ${total_bid_liquidity:.0f}")
        return True

    async def check_profit_taking(self) -> list:
        """
        HYBRID SNIPER: Check open positions for profit-taking opportunities.

        More aggressive thresholds:
        - 1.5x: Quick flip - sell all (50% gain)
        - 2x: Partial profit - sell half
        - 3x: Full profit - sell all remaining

        All profit-taking exits are tracked as "flips" (not resolutions).
        """
        profit_taken = []
        positions_copy = self.portfolio["positions"][:]

        for pos in positions_copy:
            try:
                token_id = pos.get("token_id", "")
                if not token_id:
                    continue

                # Get current order book
                bids, asks = await self.fetch_order_book(token_id)

                if not bids:
                    continue

                # Current best bid is what we could sell at
                current_bid = bids[0].price if bids else 0
                entry_price = pos["entry_price"]

                if entry_price <= 0 or current_bid <= 0:
                    continue

                price_mult = current_bid / entry_price

                # Check for full profit (3x) - sell all remaining
                if price_mult >= TAKE_FULL_PROFIT_MULT:
                    fill = self.simulate_sell(bids, pos["shares"])

                    if not fill:
                        continue

                    pnl = fill.total_cost - pos["amount_invested"]

                    log(f"FLIP 3x+: {pos['title'][:30]}...")
                    log(f"  Sold {fill.shares_filled:.1f} @ ${fill.avg_price:.4f} | P&L: ${pnl:+.2f}")

                    pos["status"] = "flip_3x"
                    pos["exit_price"] = fill.avg_price
                    pos["pnl"] = pnl

                    self.portfolio["current_balance"] += fill.total_cost
                    self.portfolio["total_pnl"] += pnl
                    self.portfolio["flips"] = self.portfolio.get("flips", 0) + 1
                    self.portfolio["flip_pnl"] = self.portfolio.get("flip_pnl", 0.0) + pnl
                    self.portfolio["closed_positions"].append(pos)
                    self.portfolio["positions"].remove(pos)

                    profit_taken.append({"pos": pos, "type": "flip_3x", "mult": price_mult})

                # Check for partial profit (2x) - sell half
                elif price_mult >= TAKE_PARTIAL_PROFIT_MULT and not pos.get("partial_profit_taken"):
                    half_shares = pos["shares"] / 2
                    fill = self.simulate_sell(bids, half_shares)

                    if not fill:
                        continue

                    half_invested = pos["amount_invested"] / 2
                    pnl = fill.total_cost - half_invested

                    log(f"FLIP 2x (partial): {pos['title'][:30]}...")
                    log(f"  Sold {fill.shares_filled:.1f} @ ${fill.avg_price:.4f} | P&L: ${pnl:+.2f}")

                    # Update position to reflect half sold
                    pos["shares"] -= fill.shares_filled
                    pos["amount_invested"] = half_invested
                    pos["partial_profit_taken"] = True

                    self.portfolio["current_balance"] += fill.total_cost
                    self.portfolio["total_pnl"] += pnl
                    self.portfolio["flip_pnl"] = self.portfolio.get("flip_pnl", 0.0) + pnl

                    profit_taken.append({"pos": pos, "type": "flip_2x_partial", "mult": price_mult, "pnl": pnl})

                # Check for quick flip (1.5x) - sell all (new aggressive threshold)
                elif price_mult >= TAKE_PROFIT_MULT:
                    fill = self.simulate_sell(bids, pos["shares"])

                    if not fill:
                        continue

                    pnl = fill.total_cost - pos["amount_invested"]

                    log(f"QUICK FLIP 1.5x: {pos['title'][:30]}...")
                    log(f"  Sold {fill.shares_filled:.1f} @ ${fill.avg_price:.4f} | P&L: ${pnl:+.2f}")

                    pos["status"] = "flip_1.5x"
                    pos["exit_price"] = fill.avg_price
                    pos["pnl"] = pnl

                    self.portfolio["current_balance"] += fill.total_cost
                    self.portfolio["total_pnl"] += pnl
                    self.portfolio["flips"] = self.portfolio.get("flips", 0) + 1
                    self.portfolio["flip_pnl"] = self.portfolio.get("flip_pnl", 0.0) + pnl
                    self.portfolio["closed_positions"].append(pos)
                    self.portfolio["positions"].remove(pos)

                    profit_taken.append({"pos": pos, "type": "flip_1.5x", "mult": price_mult})

            except Exception as e:
                continue

        if profit_taken:
            self._save_portfolio()

        return profit_taken

    async def check_resolutions(self) -> list:
        """
        HYBRID SNIPER: Check if any open positions have resolved.

        These are positions that didn't flip in time (held past 48h window)
        and went to resolution. Tracked separately from flips.
        """
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
                        # Normalize comparison
                        our_outcome = pos["outcome"].lower().strip()
                        winning_outcome = winner.lower().strip()
                        won = (our_outcome == winning_outcome)

                        if won:
                            payout = pos["shares"] * 1.0
                            pnl = payout - pos["amount_invested"]
                            self.portfolio["wins"] += 1
                            log(f"RESOLUTION WON: {pos['title'][:30]}... P&L: +${pnl:.2f}")
                        else:
                            payout = 0
                            pnl = -pos["amount_invested"]
                            self.portfolio["losses"] += 1
                            log(f"RESOLUTION LOST: {pos['title'][:30]}... P&L: -${pos['amount_invested']:.2f}")

                        pos["status"] = "resolution_won" if won else "resolution_lost"
                        pos["exit_price"] = 1.0 if won else 0.0
                        pos["pnl"] = pnl

                        self.portfolio["current_balance"] += payout
                        self.portfolio["total_pnl"] += pnl
                        # Track as resolution (distinct from flips)
                        self.portfolio["resolutions"] = self.portfolio.get("resolutions", 0) + 1
                        self.portfolio["resolution_pnl"] = self.portfolio.get("resolution_pnl", 0.0) + pnl
                        self.portfolio["closed_positions"].append(pos)
                        self.portfolio["positions"].remove(pos)

                        resolved.append(pos)
                        break

            except Exception as e:
                continue

        if resolved:
            self._save_portfolio()

        return resolved

    async def check_time_based_exits(self) -> list:
        """
        HYBRID SNIPER: Time-based exit logic.

        1. If down 50%+ after 24h → cut losses (don't hold to zero like cry.eth2)
        2. After 48h with no flip → position enters "resolution mode" (no forced exit)

        Returns list of positions that were cut.
        """
        cuts = []
        now = datetime.now()
        positions_copy = self.portfolio["positions"][:]

        for pos in positions_copy:
            try:
                entry_time = datetime.fromisoformat(pos["entry_time"])
                hours_held = (now - entry_time).total_seconds() / 3600

                # Only check positions held more than CUT_LOSS_HOURS
                if hours_held < CUT_LOSS_HOURS:
                    continue

                # Get current bid price
                token_id = pos.get("token_id", "")
                if not token_id:
                    continue

                bids, _ = await self.fetch_order_book(token_id)
                if not bids:
                    continue

                current_bid = bids[0].price
                entry_price = pos["entry_price"]

                if entry_price <= 0:
                    continue

                # Calculate P&L percentage
                pnl_pct = (current_bid - entry_price) / entry_price

                # Rule 1: Cut losses if down 50%+ after 24h
                if pnl_pct < CUT_LOSS_THRESHOLD:
                    fill = self.simulate_sell(bids, pos["shares"])
                    if not fill:
                        continue

                    pnl = fill.total_cost - pos["amount_invested"]

                    log(f"CUT LOSS: {pos['title'][:30]}... {pnl_pct:.0%} after {hours_held:.0f}h")
                    log(f"  Sold {fill.shares_filled:.1f} @ ${fill.avg_price:.4f} | P&L: ${pnl:+.2f}")

                    pos["status"] = "cut_loss"
                    pos["exit_price"] = fill.avg_price
                    pos["pnl"] = pnl

                    self.portfolio["current_balance"] += fill.total_cost
                    self.portfolio["total_pnl"] += pnl
                    self.portfolio["cuts"] = self.portfolio.get("cuts", 0) + 1
                    self.portfolio["cut_pnl"] = self.portfolio.get("cut_pnl", 0.0) + pnl
                    self.portfolio["closed_positions"].append(pos)
                    self.portfolio["positions"].remove(pos)

                    cuts.append(pos)

                # Rule 2: After 48h, position enters "resolution mode"
                # No forced exit - let check_resolutions handle it

            except Exception:
                continue

        if cuts:
            self._save_portfolio()

        return cuts

    def get_summary(self) -> str:
        """Get portfolio summary."""
        p = self.portfolio
        open_value = sum(pos["amount_invested"] for pos in p["positions"])
        total_trades = p.get("total_trades", 0)
        wins = p.get("wins", 0)
        losses = p.get("losses", 0)
        win_rate = (wins / max(1, wins + losses) * 100)
        total_return = (p['total_pnl'] / p['starting_balance'] * 100) if p['starting_balance'] > 0 else 0

        return f"""PAPER TRADING (Realistic)

Balance: ${p['current_balance']:,.2f}
Open: {len(p['positions'])} (${open_value:,.2f})
P&L: ${p['total_pnl']:+,.2f} ({total_return:+.1f}%)
Record: {wins}W / {losses}L ({win_rate:.0f}%)
Skipped (low liq): {p.get('skipped_low_liquidity', 0)}"""

    def get_detailed_status(self) -> str:
        """Get detailed portfolio status."""
        p = self.portfolio
        wins = p.get("wins", 0)
        losses = p.get("losses", 0)

        lines = [
            "=" * 50,
            "  PAPER TRADING (Realistic Liquidity)",
            "=" * 50,
            "",
            f"Starting Balance:  ${p['starting_balance']:>12,.2f}",
            f"Current Balance:   ${p['current_balance']:>12,.2f}",
            f"Total P&L:         ${p['total_pnl']:>+12,.2f}",
            f"Return:            {p['total_pnl']/p['starting_balance']*100:>+11.1f}%",
            "",
            f"Total Trades: {p.get('total_trades', 0)}",
            f"Wins: {wins} | Losses: {losses} | Win Rate: {wins/max(1, wins+losses)*100:.0f}%",
            f"Skipped (low liquidity): {p.get('skipped_low_liquidity', 0)}",
            "",
        ]

        if p["positions"]:
            lines.append("OPEN POSITIONS:")
            lines.append("-" * 50)
            for pos in p["positions"][:20]:
                lines.append(f"  {pos['title'][:40]}...")
                lines.append(f"    {pos['outcome']} @ ${pos['entry_price']:.4f} x {pos['shares']:.1f} = ${pos['amount_invested']:.2f}")
                if pos.get('slippage_pct'):
                    lines.append(f"    Slippage: {pos['slippage_pct']:.2f}%")
            if len(p["positions"]) > 20:
                lines.append(f"  ... and {len(p['positions']) - 20} more")
            lines.append("")

        if p["closed_positions"]:
            recent = p["closed_positions"][-5:]
            lines.append("RECENT TRADES:")
            lines.append("-" * 50)
            for pos in reversed(recent):
                if pos["status"] == "won":
                    status = "WIN"
                elif pos["status"] == "lost":
                    status = "LOSS"
                elif "profit" in pos["status"]:
                    status = "PROFIT"
                else:
                    status = pos["status"].upper()
                lines.append(f"  [{status}] {pos['title'][:35]}... P&L: ${pos['pnl']:+,.2f}")

        return "\n".join(lines)

    async def close(self):
        """Cleanup."""
        self._save_portfolio()
        await self.client.aclose()


async def run_paper_trading():
    """Run paper trading on new market opportunities."""
    log("=" * 50)
    log("  PAPER TRADING - HYBRID SNIPER Mode")
    log("  Exit liquidity check | 1.5x/2x/3x flips | 24h loss cuts")
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
                    log(f"\nOPPORTUNITY: {opp.title[:50]}...")
                    log(f"  {opp.cheap_outcome_name} @ ${opp.prices[opp.cheap_outcome_idx]:.4f}")
                    log(f"  Score: {opp.mispricing_score:.0%} | Token: {opp.token_id[:20]}...")

                    # Open paper position with exit liquidity checking
                    success = await trader.open_position(
                        slug=opp.slug,
                        title=opp.title,
                        outcome=opp.cheap_outcome_name,
                        token_id=opp.token_id,
                        target_price=opp.prices[opp.cheap_outcome_idx],
                    )

                    if success:
                        log(f"\n{trader.get_summary()}\n")

            # Check for profit-taking opportunities (flips)
            profit_taken = await trader.check_profit_taking()
            if profit_taken:
                log(f"\n{trader.get_summary()}\n")

            # Check for time-based exits (cut losses after 24h if down 50%+)
            cuts = await trader.check_time_based_exits()
            if cuts:
                log(f"\n{trader.get_summary()}\n")

            # Check for resolved positions (held to resolution)
            resolved = await trader.check_resolutions()
            if resolved:
                log(f"\n{trader.get_summary()}\n")

            await asyncio.sleep(60)

    except KeyboardInterrupt:
        log("\nStopping...")
    finally:
        log(f"\n{trader.get_detailed_status()}")
        await trader.close()
        await monitor.close()


def main():
    parser = argparse.ArgumentParser(
        description="Paper Trading CLI with Realistic Liquidity"
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
