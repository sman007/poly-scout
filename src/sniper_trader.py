"""
OPTIMAL SNIPER TRADER for poly-scout.

Performance-optimized paper trading with:
- WebSocket streaming for instant new market detection
- 5-second polling backup
- Async parallel order book fetching
- Event-driven architecture

Usage:
    python -m src.sniper_trader              # Run sniper mode
    python -m src.sniper_trader --status     # Show portfolio status
    python -m src.sniper_trader --reset      # Reset portfolio
"""

import argparse
import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, List, Callable, Dict
from queue import Queue
import time

import httpx

from src.config import GAMMA_API_BASE, CLOB_API_BASE
from src.polymarket_client import (
    PolymarketClient,
    AsyncPolymarketClient,
    MarketWebSocket,
    OrderBookLevel as SDKOrderBookLevel,
)

# =============================================================================
# CONFIGURATION - OPTIMIZED FOR SNIPING
# =============================================================================

PAPER_PORTFOLIO_FILE = "./data/sniper_portfolio.json"

# Timing - FAST for sniping
SCAN_INTERVAL_SECONDS = 5          # 5 seconds (was 60)
ORDER_BOOK_TIMEOUT = 3             # 3 second timeout for order books
MAX_CONCURRENT_REQUESTS = 10       # Parallel order book fetches

# Position sizing
MAX_POSITION_PCT = 0.05            # 5% of portfolio per trade
MIN_POSITION_USD = 5.0
MAX_POSITION_USD = 300.0

# Liquidity constraints
MAX_BOOK_DEPTH_PCT = 0.10
MIN_LIQUIDITY_USD = 50.0
MIN_EXIT_LIQUIDITY_USD = 100.0     # Must have bids to exit
MAX_SLIPPAGE_PCT = 75.0            # Reject fills with >75% slippage
MAX_ENTRY_PRICE = 0.08             # Reject fills with avg price >8c

# Selectivity - prioritize faster-moving markets
MIN_RESOLUTION_DAYS = 1            # Skip markets resolving too soon
MAX_RESOLUTION_DAYS = 90           # Skip markets resolving too late
OPTIMAL_RESOLUTION_MAX = 30        # Sweet spot: 1-30 days

# Quality gates (profit-first: take all good opportunities)
MIN_OPPORTUNITY_SCORE = 0.40       # Quality gate - reject low-score opps
MAX_CAPITAL_EXPOSURE = 0.80        # Don't deploy more than 80% of capital

# Scoring weights (sum to 1.0)
WEIGHT_PRICE = 0.40                # Lower price = higher score
WEIGHT_RESOLUTION = 0.35           # Closer to sweet spot = higher
WEIGHT_LIQUIDITY = 0.25            # Better exit liquidity = higher

# Profit-taking (aggressive sniper targets)
TAKE_PROFIT_MULT = 1.25            # Quick flip at 1.25x (25% gain)
TAKE_PARTIAL_PROFIT_MULT = 2.0     # Partial at 2x
TAKE_FULL_PROFIT_MULT = 3.0        # Full exit at 3x

# Loss cutting
CUT_LOSS_HOURS = 24
CUT_LOSS_THRESHOLD = -0.50         # Cut if down 50%+


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [SNIPER] {msg}", flush=True)


def calculate_days_to_resolution(end_date_str: Optional[str]) -> Optional[int]:
    """Calculate days until market resolution from endDate string."""
    if not end_date_str:
        return None
    try:
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        now = datetime.now(end_date.tzinfo) if end_date.tzinfo else datetime.now()
        delta = end_date - now
        return max(0, delta.days)
    except Exception:
        return None


def calculate_opportunity_score(
    price: float,
    days_to_resolution: Optional[int],
    exit_liquidity_usd: float
) -> float:
    """
    Calculate composite opportunity score (0.0 to 1.0, higher = better).

    - Price score: Lower price = higher (8c=0, 1c=0.875)
    - Resolution score: 1-30 days = 1.0, falls off outside
    - Liquidity score: More exit liquidity = higher
    """
    # Price score: (max_price - price) / max_price
    price_score = max(0, (MAX_ENTRY_PRICE - price) / MAX_ENTRY_PRICE)

    # Resolution score
    if days_to_resolution is None:
        resolution_score = 0.0
    elif days_to_resolution < MIN_RESOLUTION_DAYS:
        resolution_score = days_to_resolution / MIN_RESOLUTION_DAYS * 0.5
    elif days_to_resolution <= OPTIMAL_RESOLUTION_MAX:
        resolution_score = 1.0  # Sweet spot
    elif days_to_resolution <= MAX_RESOLUTION_DAYS:
        excess = days_to_resolution - OPTIMAL_RESOLUTION_MAX
        range_size = MAX_RESOLUTION_DAYS - OPTIMAL_RESOLUTION_MAX
        resolution_score = 1.0 - (excess / range_size)
    else:
        resolution_score = 0.0

    # Liquidity score: normalize against $1000 max
    liquidity_score = min(1.0, exit_liquidity_usd / 1000.0)

    # Weighted composite
    return round(
        WEIGHT_PRICE * price_score +
        WEIGHT_RESOLUTION * resolution_score +
        WEIGHT_LIQUIDITY * liquidity_score,
        4
    )


@dataclass
class OrderBookLevel:
    price: float
    size: float


@dataclass
class FillResult:
    shares_filled: float
    avg_price: float
    total_cost: float
    slippage_pct: float


@dataclass
class NewMarketEvent:
    """Event for new market detection."""
    slug: str
    title: str
    outcome: str
    token_id: str
    price: float
    timestamp: datetime
    # Selectivity fields
    end_date: Optional[str] = None
    days_to_resolution: Optional[int] = None
    exit_liquidity_usd: float = 0.0
    score: float = 0.0


class SniperTrader:
    """
    Performance-optimized sniper trader.

    Uses:
    - WebSocket streaming for real-time order book updates on positions
    - SDK client for order books (HTTP/2 + keep-alive)
    - Async parallel fetching
    - Gamma API polling for new market detection only
    """

    def __init__(self, starting_balance: float = 10000.0):
        self.starting_balance = starting_balance
        self.portfolio = self._load_portfolio()

        # HTTP clients
        self.http_client = httpx.AsyncClient(timeout=ORDER_BOOK_TIMEOUT)
        self.sdk_client = AsyncPolymarketClient()

        # WebSocket for real-time order book streaming
        self.ws = MarketWebSocket(on_message=self._handle_ws_message)
        self.order_book_cache: Dict[str, Tuple[List[OrderBookLevel], List[OrderBookLevel]]] = {}
        self._cache_lock = threading.Lock()

        # Seen markets (for deduplication)
        self.seen_markets: set = self._load_seen_markets()

        # Stats
        self.scan_count = 0
        self.last_scan_time = 0.0
        self.ws_updates = 0

        log(f"Initialized: ${self.portfolio['current_balance']:,.2f} | "
            f"{len(self.portfolio['positions'])} positions | "
            f"{len(self.seen_markets)} seen markets")

    def _handle_ws_message(self, data: dict):
        """Handle WebSocket order book update."""
        try:
            # Parse Polymarket WebSocket message format
            asset_id = data.get("asset_id") or data.get("market")
            if not asset_id:
                return

            bids_data = data.get("bids", [])
            asks_data = data.get("asks", [])

            bids = [OrderBookLevel(float(b.get("price", 0)), float(b.get("size", 0))) for b in bids_data]
            asks = [OrderBookLevel(float(a.get("price", 0)), float(a.get("size", 0))) for a in asks_data]

            # Sort: bids descending, asks ascending
            bids.sort(key=lambda x: x.price, reverse=True)
            asks.sort(key=lambda x: x.price)

            with self._cache_lock:
                self.order_book_cache[asset_id] = (bids, asks)
                self.ws_updates += 1

        except Exception:
            pass

    def start_websocket(self):
        """Start WebSocket and subscribe to held positions."""
        self.ws.start()
        time.sleep(1)  # Wait for connection

        # Subscribe to all held position token IDs
        token_ids = [pos["token_id"] for pos in self.portfolio["positions"]]
        if token_ids:
            self.ws.subscribe(token_ids)
            log(f"WebSocket subscribed to {len(token_ids)} held positions")

    def stop_websocket(self):
        """Stop WebSocket connection."""
        self.ws.stop()

    def _load_portfolio(self) -> dict:
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
            "flips": 0,
            "flip_pnl": 0.0,
            "cuts": 0,
            "cut_pnl": 0.0,
            "resolutions": 0,
            "resolution_pnl": 0.0,
            "skipped_low_liquidity": 0,
            "skipped_no_exit_liquidity": 0,
            "skipped_stale_book": 0,
        }

    def _save_portfolio(self):
        try:
            path = Path(PAPER_PORTFOLIO_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(self.portfolio, f, indent=2)
        except Exception as e:
            log(f"Error saving: {e}")

    def _load_seen_markets(self) -> set:
        try:
            path = Path("./data/sniper_seen.json")
            if path.exists():
                with open(path) as f:
                    return set(json.load(f))
        except Exception:
            pass
        return set()

    def _save_seen_markets(self):
        try:
            path = Path("./data/sniper_seen.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(list(self.seen_markets), f)
        except Exception:
            pass

    def get_cached_order_book(self, token_id: str) -> Optional[Tuple[List[OrderBookLevel], List[OrderBookLevel]]]:
        """Get order book from WebSocket cache (instant)."""
        with self._cache_lock:
            return self.order_book_cache.get(token_id)

    async def fetch_order_book(self, token_id: str, use_cache: bool = True) -> Tuple[List[OrderBookLevel], List[OrderBookLevel]]:
        """Fetch order book - uses WebSocket cache first, then SDK."""
        if not token_id:
            return [], []

        # Try WebSocket cache first (instant)
        if use_cache:
            cached = self.get_cached_order_book(token_id)
            if cached:
                return cached

        # Fallback to SDK
        try:
            book = await self.sdk_client.get_order_book(token_id)
            if book:
                bids = [OrderBookLevel(price=l.price, size=l.size) for l in book.bids]
                asks = [OrderBookLevel(price=l.price, size=l.size) for l in book.asks]
                asks.sort(key=lambda x: x.price)
                bids.sort(key=lambda x: x.price, reverse=True)
                # Update cache
                with self._cache_lock:
                    self.order_book_cache[token_id] = (bids, asks)
                return bids, asks
        except Exception:
            pass

        # Fallback to httpx
        try:
            resp = await self.http_client.get(
                f"{CLOB_API_BASE}/book?token_id={token_id}"
            )
            if resp.status_code == 200:
                data = resp.json()
                bids = [OrderBookLevel(float(l["price"]), float(l["size"]))
                        for l in data.get("bids", [])]
                asks = [OrderBookLevel(float(l["price"]), float(l["size"]))
                        for l in data.get("asks", [])]
                asks.sort(key=lambda x: x.price)
                bids.sort(key=lambda x: x.price, reverse=True)
                # Update cache
                with self._cache_lock:
                    self.order_book_cache[token_id] = (bids, asks)
                return bids, asks
        except Exception:
            pass

        return [], []

    async def fetch_order_books_parallel(self, token_ids: List[str]) -> dict:
        """Fetch multiple order books in parallel."""
        async def fetch_one(tid):
            return tid, await self.fetch_order_book(tid)

        tasks = [fetch_one(tid) for tid in token_ids[:MAX_CONCURRENT_REQUESTS]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        books = {}
        for result in results:
            if isinstance(result, tuple):
                tid, (bids, asks) = result
                books[tid] = (bids, asks)
        return books

    async def get_last_trade_price(self, token_id: str) -> Optional[float]:
        """
        Get last trade price for more accurate fill simulation.

        Falls back to midpoint if no recent trades.
        """
        try:
            return await self.sdk_client.get_last_trade_price(token_id)
        except Exception:
            return None

    def simulate_buy(self, asks: List[OrderBookLevel], max_spend: float, last_trade: Optional[float] = None) -> Optional[FillResult]:
        """
        Simulate market buy with order book walking.

        If last_trade is provided, validates that fill price is within 20% of
        recent trading activity to detect stale order books.
        """
        if not asks:
            return None

        total_liquidity = sum(l.price * l.size for l in asks)
        if total_liquidity < MIN_LIQUIDITY_USD:
            return None

        max_spend = min(max_spend, total_liquidity * MAX_BOOK_DEPTH_PCT)
        if max_spend < MIN_POSITION_USD:
            return None

        total_cost = 0.0
        total_shares = 0.0
        best_price = asks[0].price
        remaining = max_spend

        for level in asks:
            if remaining <= 0:
                break
            level_cost = level.price * level.size
            if level_cost <= remaining:
                total_cost += level_cost
                total_shares += level.size
                remaining -= level_cost
            else:
                shares = remaining / level.price
                total_cost += remaining
                total_shares += shares
                remaining = 0

        if total_shares <= 0:
            return None

        avg_price = total_cost / total_shares
        slippage = ((avg_price - best_price) / best_price * 100) if best_price > 0 else 0

        # Reject excessive slippage
        if slippage > MAX_SLIPPAGE_PCT:
            log(f"SKIP: Slippage too high ({slippage:.0f}% > {MAX_SLIPPAGE_PCT}%)")
            return None

        # Reject if fill price exceeds max entry price
        if avg_price > MAX_ENTRY_PRICE:
            log(f"SKIP: Entry price too high (${avg_price:.4f} > ${MAX_ENTRY_PRICE:.2f})")
            return None

        # Sanity check against last trade price (if available)
        # Reject if fill price deviates >20% from last trade (stale order book)
        if last_trade and last_trade > 0:
            price_deviation = abs(avg_price - last_trade) / last_trade
            if price_deviation > 0.20:
                log(f"SKIP: Order book stale - fill ${avg_price:.4f} vs last trade ${last_trade:.4f}")
                return None

        return FillResult(total_shares, avg_price, total_cost, slippage)

    def simulate_sell(self, bids: List[OrderBookLevel], shares: float) -> Optional[FillResult]:
        if not bids or shares <= 0:
            return None

        total_proceeds = 0.0
        total_sold = 0.0
        best_price = bids[0].price
        remaining = shares

        for level in bids:
            if remaining <= 0:
                break
            if level.size <= remaining:
                total_proceeds += level.price * level.size
                total_sold += level.size
                remaining -= level.size
            else:
                total_proceeds += level.price * remaining
                total_sold += remaining
                remaining = 0

        if total_sold <= 0:
            return None

        avg_price = total_proceeds / total_sold
        slippage = ((best_price - avg_price) / best_price * 100) if best_price > 0 else 0

        return FillResult(total_sold, avg_price, total_proceeds, slippage)

    async def scan_new_markets(self) -> List[NewMarketEvent]:
        """Scan for NEW markets only. Warmup marks existing markets as seen."""
        start = time.time()
        events = []

        # Warmup: paginate through ALL markets to build complete seen set
        is_warmup = not self.seen_markets

        if is_warmup:
            log("Warmup: fetching ALL markets (this may take a moment)...")
            offset = 0
            page_size = 500
            total_fetched = 0

            while True:
                try:
                    resp = await self.http_client.get(
                        f"{GAMMA_API_BASE}/events?active=true&closed=false&limit={page_size}&offset={offset}"
                    )
                    if resp.status_code != 200:
                        break

                    data = resp.json()
                    if not data:
                        break  # No more results

                    for event in data:
                        slug = event.get("slug", "")
                        if slug:
                            self.seen_markets.add(slug)

                    total_fetched += len(data)
                    log(f"Warmup: fetched {total_fetched} events ({len(self.seen_markets)} unique slugs)...")

                    if len(data) < page_size:
                        break  # Last page

                    offset += page_size
                    await asyncio.sleep(0.1)  # Rate limit

                except Exception as e:
                    log(f"Warmup fetch error: {e}")
                    break

            log(f"Warmup complete: tracking {len(self.seen_markets)} existing markets")
            self._save_seen_markets()
            return events  # Return empty - no positions during warmup

        # After warmup: Only check first page for NEW markets (they appear at top)
        try:
            resp = await self.http_client.get(
                f"{GAMMA_API_BASE}/events?active=true&closed=false&limit=200"
            )
            if resp.status_code != 200:
                return events

            data = resp.json()

            # After warmup: Only process NEW markets (not in seen_markets)
            for event in data:
                slug = event.get("slug", "")
                if not slug:
                    continue

                # Skip already seen markets
                if slug in self.seen_markets:
                    continue

                # NEW market detected - mark as seen
                self.seen_markets.add(slug)

                # Extract and validate end date for selectivity
                end_date_str = event.get("endDate")
                days_to_res = calculate_days_to_resolution(end_date_str)

                # Filter by resolution time
                if days_to_res is None:
                    self.portfolio.setdefault("skipped_no_end_date", 0)
                    self.portfolio["skipped_no_end_date"] += 1
                    continue

                if days_to_res > MAX_RESOLUTION_DAYS:
                    self.portfolio.setdefault("skipped_too_far_out", 0)
                    self.portfolio["skipped_too_far_out"] += 1
                    continue

                # Analyze for mispricing
                for market in event.get("markets", []):
                    try:
                        # Skip closed markets
                        if market.get("closed"):
                            continue

                        outcomes = market.get("outcomes", [])
                        prices_str = market.get("outcomePrices", "[]")
                        token_ids_raw = market.get("clobTokenIds", [])

                        if isinstance(outcomes, str):
                            outcomes = json.loads(outcomes)
                        prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                        prices = [float(p) for p in prices]
                        if isinstance(token_ids_raw, str):
                            token_ids = json.loads(token_ids_raw)
                        else:
                            token_ids = token_ids_raw

                        if len(prices) < 2:
                            continue

                        # Check for mispricing - cheap longshot (<8c)
                        min_price = min(prices)
                        if min_price < 0.08:
                            idx = prices.index(min_price)
                            outcome = outcomes[idx] if idx < len(outcomes) else "Unknown"
                            token_id = token_ids[idx] if idx < len(token_ids) else ""

                            if not token_id:
                                continue

                            events.append(NewMarketEvent(
                                slug=slug,
                                title=event.get("title", "")[:100],
                                outcome=outcome,
                                token_id=token_id,
                                price=min_price,
                                timestamp=datetime.now(),
                                end_date=end_date_str,
                                days_to_resolution=days_to_res,
                            ))
                            log(f"NEW: {event.get('title', '')[:40]}... {outcome} @ ${min_price:.3f} ({days_to_res}d)")

                    except Exception:
                        continue

            self._save_seen_markets()

        except Exception as e:
            log(f"Scan error: {e}")

        elapsed = time.time() - start
        self.scan_count += 1
        self.last_scan_time = elapsed

        return events

    async def open_position(self, event: NewMarketEvent) -> bool:
        """Open position with exit liquidity check and last trade validation."""
        max_spend = min(
            self.portfolio["current_balance"] * MAX_POSITION_PCT,
            MAX_POSITION_USD
        )

        if max_spend < MIN_POSITION_USD:
            return False

        # Fetch order book and last trade price in parallel
        bids, asks = await self.fetch_order_book(event.token_id)
        last_trade = await self.get_last_trade_price(event.token_id)

        if not asks:
            self.portfolio["skipped_low_liquidity"] += 1
            return False

        # Check exit liquidity
        bid_liquidity = sum(l.price * l.size for l in bids) if bids else 0
        if bid_liquidity < MIN_EXIT_LIQUIDITY_USD:
            self.portfolio["skipped_no_exit_liquidity"] += 1
            log(f"SKIP: No exit liq (${bid_liquidity:.0f}) for {event.title[:30]}...")
            return False

        # Calculate final opportunity score with actual liquidity
        event.exit_liquidity_usd = bid_liquidity
        event.score = calculate_opportunity_score(
            price=event.price,
            days_to_resolution=event.days_to_resolution,
            exit_liquidity_usd=bid_liquidity
        )

        # Quality gate: reject low-score opportunities
        if event.score < MIN_OPPORTUNITY_SCORE:
            self.portfolio.setdefault("skipped_low_score", 0)
            self.portfolio["skipped_low_score"] += 1
            log(f"SKIP: Low score {event.score:.3f} < {MIN_OPPORTUNITY_SCORE} for {event.title[:30]}...")
            return False

        # Capital exposure gate: don't over-deploy
        total_invested = sum(p.get("amount_invested", 0) for p in self.portfolio["positions"])
        current_exposure = total_invested / self.portfolio["starting_balance"]
        if current_exposure >= MAX_CAPITAL_EXPOSURE:
            self.portfolio.setdefault("skipped_exposure_limit", 0)
            self.portfolio["skipped_exposure_limit"] += 1
            log(f"SKIP: Exposure {current_exposure:.1%} >= {MAX_CAPITAL_EXPOSURE:.0%} limit")
            return False

        # Simulate buy with last trade price for validation
        fill = self.simulate_buy(asks, max_spend, last_trade=last_trade)
        if not fill:
            # Check if it was a stale book skip (last_trade exists but fill failed)
            if last_trade and last_trade > 0 and asks:
                best_ask = asks[0].price
                if abs(best_ask - last_trade) / last_trade > 0.20:
                    self.portfolio["skipped_stale_book"] += 1
                else:
                    self.portfolio["skipped_low_liquidity"] += 1
            else:
                self.portfolio["skipped_low_liquidity"] += 1
            return False

        position = {
            "slug": event.slug,
            "title": event.title,
            "outcome": event.outcome,
            "token_id": event.token_id,
            "entry_price": fill.avg_price,
            "shares": fill.shares_filled,
            "amount_invested": fill.total_cost,
            "entry_time": datetime.now().isoformat(),
            "slippage_pct": fill.slippage_pct,
            "status": "open",
            "score": event.score,
            "days_to_resolution": event.days_to_resolution,
        }

        self.portfolio["positions"].append(position)
        self.portfolio["current_balance"] -= fill.total_cost
        self.portfolio["total_trades"] += 1
        self._save_portfolio()

        # Subscribe to WebSocket for real-time updates on this position
        self.ws.subscribe([event.token_id])

        days_str = f"{event.days_to_resolution}d" if event.days_to_resolution else "?"
        log(f"OPEN: {fill.shares_filled:.0f} {event.outcome} @ ${fill.avg_price:.4f} = ${fill.total_cost:.2f} "
            f"[score:{event.score:.3f} {days_str}]")
        return True

    async def check_exits(self):
        """Check all positions for exits (parallel)."""
        if not self.portfolio["positions"]:
            return

        # Get all token IDs
        token_ids = [p.get("token_id", "") for p in self.portfolio["positions"] if p.get("token_id")]
        if not token_ids:
            return

        # Fetch all order books in parallel
        books = await self.fetch_order_books_parallel(token_ids)

        positions_copy = self.portfolio["positions"][:]
        now = datetime.now()

        for pos in positions_copy:
            token_id = pos.get("token_id", "")
            if token_id not in books:
                continue

            bids, asks = books[token_id]
            if not bids:
                continue

            current_bid = bids[0].price
            entry_price = pos["entry_price"]

            if entry_price <= 0:
                continue

            price_mult = current_bid / entry_price

            # Check profit targets
            if price_mult >= TAKE_FULL_PROFIT_MULT:
                fill = self.simulate_sell(bids, pos["shares"])
                if fill:
                    self._close_position(pos, fill, "flip_3x")

            elif price_mult >= TAKE_PROFIT_MULT:
                fill = self.simulate_sell(bids, pos["shares"])
                if fill:
                    self._close_position(pos, fill, "flip_1.5x")

            # Check loss cutting
            else:
                entry_time = datetime.fromisoformat(pos["entry_time"])
                hours_held = (now - entry_time).total_seconds() / 3600
                pnl_pct = (current_bid - entry_price) / entry_price

                if hours_held >= CUT_LOSS_HOURS and pnl_pct <= CUT_LOSS_THRESHOLD:
                    fill = self.simulate_sell(bids, pos["shares"])
                    if fill:
                        self._close_position(pos, fill, "cut_loss")

    def _close_position(self, pos: dict, fill: FillResult, status: str):
        """Close a position."""
        pnl = fill.total_cost - pos["amount_invested"]

        pos["status"] = status
        pos["exit_price"] = fill.avg_price
        pos["pnl"] = pnl

        self.portfolio["current_balance"] += fill.total_cost
        self.portfolio["total_pnl"] += pnl

        if "flip" in status:
            self.portfolio["flips"] += 1
            self.portfolio["flip_pnl"] += pnl
            log(f"FLIP: {pos['title'][:30]}... P&L: ${pnl:+.2f}")
        elif status == "cut_loss":
            self.portfolio["cuts"] += 1
            self.portfolio["cut_pnl"] += pnl
            log(f"CUT: {pos['title'][:30]}... P&L: ${pnl:+.2f}")

        self.portfolio["closed_positions"].append(pos)
        self.portfolio["positions"].remove(pos)
        self._save_portfolio()

        # Unsubscribe from WebSocket
        self.ws.unsubscribe([pos["token_id"]])

    async def check_resolutions(self):
        """Check for resolved markets."""
        if not self.portfolio["positions"]:
            return

        for pos in self.portfolio["positions"][:]:
            try:
                resp = await self.http_client.get(
                    f"{GAMMA_API_BASE}/events?slug={pos['slug']}"
                )
                if resp.status_code != 200:
                    continue

                events = resp.json()
                if not events or not events[0].get("closed"):
                    continue

                for market in events[0].get("markets", []):
                    winner = market.get("winner")
                    if winner:
                        won = pos["outcome"].lower().strip() == winner.lower().strip()

                        if won:
                            pnl = pos["shares"] - pos["amount_invested"]
                            self.portfolio["wins"] += 1
                        else:
                            pnl = -pos["amount_invested"]
                            self.portfolio["losses"] += 1

                        pos["status"] = "resolution_won" if won else "resolution_lost"
                        pos["pnl"] = pnl
                        pos["exit_price"] = 1.0 if won else 0.0

                        self.portfolio["current_balance"] += (pos["shares"] if won else 0)
                        self.portfolio["total_pnl"] += pnl
                        self.portfolio["resolutions"] += 1
                        self.portfolio["resolution_pnl"] += pnl
                        self.portfolio["closed_positions"].append(pos)
                        self.portfolio["positions"].remove(pos)

                        # Unsubscribe from WebSocket
                        self.ws.unsubscribe([pos["token_id"]])

                        log(f"RESOLVED: {pos['title'][:30]}... {'WON' if won else 'LOST'} ${pnl:+.2f}")
                        break

            except Exception:
                continue

        self._save_portfolio()

    def get_status(self) -> str:
        p = self.portfolio
        ret = p['total_pnl'] / p['starting_balance'] * 100 if p['starting_balance'] > 0 else 0
        ws_status = "ON" if self.ws.running else "OFF"

        # Calculate average score of open positions
        scores = [pos.get("score", 0) for pos in p["positions"]]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Calculate capital exposure
        total_invested = sum(pos.get("amount_invested", 0) for pos in p["positions"])
        exposure_pct = total_invested / p["starting_balance"] * 100 if p["starting_balance"] > 0 else 0

        # Skip counts
        skipped_no_date = p.get("skipped_no_end_date", 0)
        skipped_far = p.get("skipped_too_far_out", 0)
        skipped_score = p.get("skipped_low_score", 0)
        skipped_exposure = p.get("skipped_exposure_limit", 0)

        return f"""
╔══════════════════════════════════════════════════════╗
║  SNIPER TRADER - ${p['current_balance']:>10,.2f} balance
║  P&L: ${p['total_pnl']:>+10,.2f} ({ret:>+.1f}%)
║  Open: {len(p['positions'])} | Exposure: {exposure_pct:.0f}% | Avg Score: {avg_score:.3f}
║  Flips: {p.get('flips',0)} | Cuts: {p.get('cuts',0)} | Resolved: {p.get('resolutions',0)}
║  Skip: noDate:{skipped_no_date} far:{skipped_far} score:{skipped_score} exp:{skipped_exposure}
║  Scan: {self.scan_count} | WS: {ws_status} ({self.ws_updates} updates)
╚══════════════════════════════════════════════════════╝"""

    async def close(self):
        self._save_portfolio()
        self._save_seen_markets()
        self.stop_websocket()
        await self.http_client.aclose()


async def run_sniper():
    """Main sniper loop - optimized for speed with WebSocket streaming."""
    log("=" * 60)
    log("  SNIPER TRADER - WEBSOCKET STREAMING MODE")
    log(f"  Gamma poll: {SCAN_INTERVAL_SECONDS}s | Order books: WebSocket real-time")
    log("=" * 60)

    trader = SniperTrader(starting_balance=10000.0)

    # Check time sync with server
    time_offset = await trader.sdk_client.get_time_offset()
    log(f"Server time offset: {time_offset}ms (local {'ahead' if time_offset > 0 else 'behind'})")

    # Start WebSocket for real-time order book updates
    trader.start_websocket()

    log(trader.get_status())

    try:
        while True:
            loop_start = time.time()

            # 1. Scan for new markets
            new_events = await trader.scan_new_markets()

            # 2. Sort by preliminary score (best first) and open positions
            # Note: Final score uses actual liquidity from open_position
            new_events.sort(
                key=lambda e: calculate_opportunity_score(
                    e.price, e.days_to_resolution, 0
                ),
                reverse=True
            )
            for event in new_events:
                await trader.open_position(event)

            # 3. Check all positions for exits (parallel)
            await trader.check_exits()

            # 4. Check resolutions
            await trader.check_resolutions()

            # Status every 60 scans (~5 min)
            if trader.scan_count % 60 == 0:
                log(trader.get_status())

            # Sleep to hit target interval
            elapsed = time.time() - loop_start
            sleep_time = max(0, SCAN_INTERVAL_SECONDS - elapsed)
            await asyncio.sleep(sleep_time)

    except KeyboardInterrupt:
        log("\nShutting down...")
    finally:
        log(trader.get_status())
        await trader.close()


def main():
    parser = argparse.ArgumentParser(description="Sniper Trader - Optimal Performance")
    parser.add_argument("--status", "-s", action="store_true", help="Show status")
    parser.add_argument("--reset", "-r", action="store_true", help="Reset portfolio")
    args = parser.parse_args()

    if args.status:
        trader = SniperTrader()
        print(trader.get_status())
        return

    if args.reset:
        trader = SniperTrader()
        trader.portfolio = trader._create_empty_portfolio()
        trader.seen_markets = set()
        trader._save_portfolio()
        trader._save_seen_markets()
        log("Portfolio reset")
        return

    asyncio.run(run_sniper())


if __name__ == "__main__":
    main()
