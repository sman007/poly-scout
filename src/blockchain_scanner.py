"""
Blockchain-based Smart Money Scanner for Polymarket.

Scans the Polygon blockchain for wallets with explosive growth patterns.
Identifies "smart money" BEFORE they hit leaderboards.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path

import httpx
from web3 import Web3
from web3.exceptions import Web3Exception

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.wallet_validator import validate_wallet, ValidationResult


def log(msg: str):
    print(f"[BLOCKCHAIN] {msg}", flush=True)


# Contract addresses on Polygon
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
USDC_PROXY = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Polymarket API endpoints
DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

# Smart money thresholds (relaxed to catch emerging smart money)
MIN_GROWTH_30D = 2.0        # 2x growth minimum (was 5x - too strict)
MAX_WALLET_AGE_DAYS = 120   # 4 months (was 90)
MIN_WIN_RATE = 0.60         # 60% win rate (was 70%)
MIN_PORTFOLIO_VALUE = 500   # $500 minimum (was $1k)

# Scan settings
# Note: With Alchemy Free (10-block limit), 1000 blocks = 100 API calls
BLOCKS_PER_SCAN = 1000      # ~33 minutes of blocks (2 sec/block)
SCAN_INTERVAL_MINUTES = 30  # Scan every 30 minutes

# Seen wallets file
SEEN_SMART_MONEY_FILE = Path("data/seen_smart_money.json")


# CTF Exchange ABI - OrderFilled event
CTF_EXCHANGE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": True, "name": "taker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "fee", "type": "uint256"},
        ],
        "name": "OrderFilled",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": True, "name": "taker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"},
        ],
        "name": "OrdersMatched",
        "type": "event",
    },
]


@dataclass
class SmartMoneyWallet:
    """A wallet flagged as potential smart money."""
    address: str
    wallet_age_days: int
    first_transaction_date: Optional[datetime]
    portfolio_value_usd: float
    growth_7d_pct: float
    growth_30d_pct: float
    growth_90d_pct: float
    markets_participated: int
    win_rate: float
    total_trades: int
    notable_wins: List[str] = field(default_factory=list)
    risk_score: str = "unknown"  # "likely_insider" | "skilled_trader" | "bot" | "unknown"
    validation: Optional[ValidationResult] = None  # Statistical validation result

    def to_telegram_message(self) -> str:
        """Format wallet for Telegram alert with validation stats."""
        # Format portfolio value in k/M
        pv = self.portfolio_value_usd
        if pv >= 1_000_000:
            pv_str = f"${pv / 1_000_000:.1f}M"
        elif pv >= 1_000:
            pv_str = f"${pv / 1_000:.0f}k"
        else:
            pv_str = f"${pv:.0f}"

        # Format notable wins compactly
        wins_compact = " | ".join(self.notable_wins[:3]) if self.notable_wins else "None"

        # Include validation stats if available
        val_str = ""
        if self.validation:
            val_str = f"""
STATISTICAL VALIDATION
Win Rate: {self.validation.win_rate:.1%} ({self.validation.sample_size} trades)
P-value: {self.validation.win_rate_pvalue:.6f}
Consistency: {self.validation.consistency_variance:.4f} variance
Confidence: {self.validation.confidence_level}
"""

        return f"""BLOCKCHAIN DISCOVERY: {self.address[:8]}...{self.address[-4:]}
{val_str}
{pv_str} | {self.win_rate:.0%} WR | {self.wallet_age_days}d old | {self.growth_30d_pct:+.0f}% (30d)
{self.total_trades} trades | {self.markets_participated} markets | {self.risk_score}

Top: {wins_compact}

polymarket.com/profile/{self.address}"""


@dataclass
class Trade:
    """A single trade on the CTF Exchange."""
    block_number: int
    tx_hash: str
    maker: str
    taker: str
    maker_asset_id: int
    taker_asset_id: int
    maker_amount: float
    taker_amount: float
    timestamp: Optional[datetime] = None


class BlockchainScanner:
    """
    Scan Polygon blockchain for Polymarket smart money.

    Uses a hybrid approach:
    1. Blockchain: Discover active traders in real-time
    2. Polymarket API: Get portfolio values, win rates, growth
    """

    def __init__(self, rpc_url: str):
        """Initialize with Polygon RPC URL."""
        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Polygon RPC: {rpc_url}")

        self.ctf_exchange = self.w3.eth.contract(
            address=Web3.to_checksum_address(CTF_EXCHANGE),
            abi=CTF_EXCHANGE_ABI
        )

        self.seen_wallets = self._load_seen_wallets()
        self.http_client = httpx.AsyncClient(timeout=30)

        log(f"Connected to Polygon (block {self.w3.eth.block_number})")

    def _load_seen_wallets(self) -> Set[str]:
        """Load previously seen smart money wallets."""
        if SEEN_SMART_MONEY_FILE.exists():
            try:
                with open(SEEN_SMART_MONEY_FILE) as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    def _save_seen_wallets(self):
        """Save seen wallets to disk."""
        SEEN_SMART_MONEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SEEN_SMART_MONEY_FILE, "w") as f:
            json.dump(list(self.seen_wallets), f)

    async def scan_recent_trades(self, blocks: int = BLOCKS_PER_SCAN) -> List[Trade]:
        """
        Scan recent blocks for Polymarket trades.

        Returns list of trades with maker/taker addresses.
        Scans in chunks to avoid RPC block range limits.
        """
        try:
            latest_block = self.w3.eth.block_number
            from_block = latest_block - blocks

            log(f"Scanning blocks {from_block:,} to {latest_block:,}...")

            # Chunk size depends on RPC tier:
            # - Alchemy Free: 10 blocks max for eth_getLogs
            # - Public polygon-rpc.com: 5 blocks max (very restrictive)
            # - Paid RPCs: much larger ranges
            if "alchemy.com" in self.rpc_url:
                CHUNK_SIZE = 10  # Alchemy Free tier limit
                DELAY_BETWEEN_CHUNKS = 0.1
            elif "polygon-rpc.com" in self.rpc_url:
                CHUNK_SIZE = 5  # Public RPC is very restrictive
                DELAY_BETWEEN_CHUNKS = 0.5  # Rate limit: 2 req/sec
            else:
                CHUNK_SIZE = 2000  # Paid RPCs
                DELAY_BETWEEN_CHUNKS = 0

            trades = []
            current_block = from_block

            while current_block <= latest_block:
                # -1 because block ranges are inclusive (block 0 to 9 = 10 blocks)
                chunk_end = min(current_block + CHUNK_SIZE - 1, latest_block)

                try:
                    # Get OrderFilled events (web3.py v6+ uses snake_case params)
                    events = self.ctf_exchange.events.OrderFilled.get_logs(
                        from_block=current_block,
                        to_block=chunk_end
                    )

                    for event in events:
                        trade = Trade(
                            block_number=event.blockNumber,
                            tx_hash=event.transactionHash.hex(),
                            maker=event.args.maker,
                            taker=event.args.taker,
                            maker_asset_id=event.args.makerAssetId,
                            taker_asset_id=event.args.takerAssetId,
                            maker_amount=event.args.makerAmountFilled / 1e6,  # USDC has 6 decimals
                            taker_amount=event.args.takerAmountFilled / 1e6,
                        )
                        trades.append(trade)

                except Exception as chunk_err:
                    log(f"  Chunk {current_block}-{chunk_end} error: {chunk_err}")

                current_block = chunk_end + 1

                # Rate limit between chunks
                if DELAY_BETWEEN_CHUNKS > 0:
                    await asyncio.sleep(DELAY_BETWEEN_CHUNKS)

            log(f"Found {len(trades)} trades in {blocks} blocks")
            return trades

        except Web3Exception as e:
            log(f"Web3 error scanning trades: {e}")
            return []
        except Exception as e:
            log(f"Error scanning trades: {e}")
            return []

    def get_unique_traders(self, trades: List[Trade]) -> Set[str]:
        """Extract unique trader addresses from trades."""
        traders = set()
        for trade in trades:
            traders.add(trade.maker.lower())
            traders.add(trade.taker.lower())
        return traders

    async def get_wallet_age(self, address: str) -> Optional[int]:
        """
        Get wallet age in days by checking first Polymarket activity.

        Uses Polymarket API since on-chain first tx might not be Polymarket.
        """
        try:
            url = f"{DATA_API}/activity?user={address}&limit=1&offset=0"
            resp = await self.http_client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    # Get oldest activity
                    url_all = f"{DATA_API}/activity?user={address}&limit=500"
                    resp_all = await self.http_client.get(url_all)
                    if resp_all.status_code == 200:
                        activities = resp_all.json()
                        if activities:
                            # Find oldest timestamp - handle both int (Unix ms) and string (ISO)
                            timestamps = [a.get("timestamp") for a in activities if a.get("timestamp")]
                            if not timestamps:
                                return None
                            oldest = min(timestamps)

                            # Parse timestamp - could be int (Unix ms) or string (ISO)
                            if isinstance(oldest, (int, float)):
                                # Unix milliseconds
                                first_date = datetime.fromtimestamp(oldest / 1000)
                                age = (datetime.now() - first_date).days
                            else:
                                # ISO string format
                                first_date = datetime.fromisoformat(str(oldest).replace("Z", "+00:00"))
                                age = (datetime.now(first_date.tzinfo) - first_date).days
                            return age
            return None
        except Exception as e:
            log(f"Error getting wallet age for {address[:10]}: {e}")
            return None

    async def get_wallet_portfolio(self, address: str) -> Dict:
        """
        Get wallet portfolio value and positions from Polymarket API.

        Returns dict with:
        - portfolio_value: Current total value in USD
        - positions: List of positions
        - markets_count: Number of unique markets
        """
        try:
            url = f"{DATA_API}/positions?user={address}"
            resp = await self.http_client.get(url)

            if resp.status_code != 200:
                return {"portfolio_value": 0, "positions": [], "markets_count": 0}

            positions = resp.json()

            # Calculate total value
            total_value = 0
            markets = set()

            for pos in positions:
                # Get current value of position
                size = float(pos.get("size", 0))
                current_price = float(pos.get("currentPrice", 0))
                value = size * current_price
                total_value += value

                # Track unique markets
                market_slug = pos.get("market", {}).get("slug", "")
                if market_slug:
                    markets.add(market_slug)

            return {
                "portfolio_value": total_value,
                "positions": positions,
                "markets_count": len(markets)
            }

        except Exception as e:
            log(f"Error getting portfolio for {address[:10]}: {e}")
            return {"portfolio_value": 0, "positions": [], "markets_count": 0}

    async def get_wallet_pnl(self, address: str) -> Dict:
        """
        Get wallet P&L and win rate from Polymarket API.

        Returns dict with:
        - total_pnl: Total profit/loss
        - win_rate: Percentage of winning trades
        - total_trades: Number of trades
        - notable_wins: List of big winning positions
        """
        try:
            # Get activity/trade history
            url = f"{DATA_API}/activity?user={address}&limit=500"
            resp = await self.http_client.get(url)

            if resp.status_code != 200:
                return {"total_pnl": 0, "win_rate": 0, "total_trades": 0, "notable_wins": []}

            activities = resp.json()

            # Analyze trades
            wins = 0
            losses = 0
            total_pnl = 0
            notable_wins = []

            for activity in activities:
                pnl = float(activity.get("profit", 0) or 0)
                total_pnl += pnl

                if pnl > 0:
                    wins += 1
                    # Track big wins (>$100)
                    if pnl > 100:
                        market_title = activity.get("market", {}).get("question", "Unknown")[:50]
                        notable_wins.append(f"${pnl:,.0f} on {market_title}")
                elif pnl < 0:
                    losses += 1

            total_trades = wins + losses
            win_rate = wins / total_trades if total_trades > 0 else 0

            # Sort notable wins by size (already have them as strings)
            notable_wins = sorted(notable_wins, key=lambda x: float(x.split("$")[1].split(" ")[0].replace(",", "")), reverse=True)[:5]

            return {
                "total_pnl": total_pnl,
                "win_rate": win_rate,
                "total_trades": total_trades,
                "notable_wins": notable_wins
            }

        except Exception as e:
            log(f"Error getting P&L for {address[:10]}: {e}")
            return {"total_pnl": 0, "win_rate": 0, "total_trades": 0, "notable_wins": []}

    async def get_historical_value(self, address: str, days: int) -> float:
        """
        Estimate historical portfolio value.

        This is approximate - we use total P&L to work backwards.
        """
        try:
            # Get current portfolio
            portfolio = await self.get_wallet_portfolio(address)
            current_value = portfolio["portfolio_value"]

            # Get P&L to estimate past value
            pnl_data = await self.get_wallet_pnl(address)
            total_pnl = pnl_data["total_pnl"]

            # Rough estimate: past value = current - pnl
            # This assumes all P&L came in the period (conservative estimate)
            past_value = max(0, current_value - total_pnl)

            return past_value

        except Exception:
            return 0

    async def analyze_wallet(self, address: str) -> Optional[SmartMoneyWallet]:
        """
        Deep analysis of a single wallet.

        Returns SmartMoneyWallet if it meets criteria, None otherwise.
        """
        try:
            # Get wallet age
            age_days = await self.get_wallet_age(address)
            if age_days is None:
                return None

            # Skip old wallets
            if age_days > MAX_WALLET_AGE_DAYS:
                return None

            # Get portfolio data
            portfolio = await self.get_wallet_portfolio(address)
            current_value = portfolio["portfolio_value"]

            # Skip low-value wallets
            if current_value < MIN_PORTFOLIO_VALUE:
                return None

            # Get P&L data
            pnl_data = await self.get_wallet_pnl(address)
            win_rate = pnl_data["win_rate"]
            total_trades = pnl_data["total_trades"]

            # Skip low-activity wallets
            if total_trades < 5:
                return None

            # Calculate growth
            # Past value = current - total_pnl (rough estimate)
            total_pnl = pnl_data["total_pnl"]
            initial_value = max(100, current_value - total_pnl)  # Assume at least $100 start

            growth_multiplier = current_value / initial_value if initial_value > 0 else 1
            growth_30d_pct = (growth_multiplier - 1) * 100

            # Estimate shorter periods (rough)
            growth_7d_pct = growth_30d_pct * 0.3  # Rough estimate
            growth_90d_pct = growth_30d_pct * 1.2  # Rough estimate

            # Check criteria
            is_explosive_growth = growth_multiplier >= MIN_GROWTH_30D
            is_high_win_rate = win_rate >= MIN_WIN_RATE

            # Must meet growth OR win rate criteria
            if not (is_explosive_growth or is_high_win_rate):
                return None

            # Classify risk
            risk_score = self._classify_risk(
                win_rate=win_rate,
                growth=growth_multiplier,
                trades=total_trades,
                age_days=age_days
            )

            # Calculate first transaction date
            first_tx_date = datetime.now() - timedelta(days=age_days) if age_days else None

            # ============================================================
            # STATISTICAL VALIDATION - Only alert on proven performers
            # ============================================================
            # Fetch positions and activities for validation
            positions = portfolio.get("positions", [])

            # Fetch activities for consistency testing
            activities_url = f"{DATA_API}/activity?user={address}&limit=500"
            try:
                activities_resp = await self.http_client.get(activities_url)
                activities = activities_resp.json() if activities_resp.status_code == 200 else []
            except Exception:
                activities = []

            # Run statistical validation
            validation = validate_wallet(positions, activities)

            if not validation.is_valid:
                log(f"  REJECTED {address[:10]}... - {validation.rejection_reason}")
                return None

            log(f"  VALIDATED {address[:10]}... - {validation.confidence_level} confidence, p={validation.win_rate_pvalue:.6f}")

            return SmartMoneyWallet(
                address=address,
                wallet_age_days=age_days,
                first_transaction_date=first_tx_date,
                portfolio_value_usd=current_value,
                growth_7d_pct=growth_7d_pct,
                growth_30d_pct=growth_30d_pct,
                growth_90d_pct=growth_90d_pct,
                markets_participated=portfolio["markets_count"],
                win_rate=win_rate,
                total_trades=total_trades,
                notable_wins=pnl_data["notable_wins"],
                risk_score=risk_score,
                validation=validation
            )

        except Exception as e:
            log(f"Error analyzing wallet {address[:10]}: {e}")
            return None

    def _classify_risk(self, win_rate: float, growth: float, trades: int, age_days: int) -> str:
        """
        Classify the risk profile of a wallet.

        Returns: "likely_insider" | "skilled_trader" | "bot" | "unknown"
        """
        # Likely insider: Too-perfect metrics on a new wallet
        if win_rate > 0.95 and growth > 10 and age_days < 30:
            return "likely_insider"

        # Bot: Very high frequency, consistent metrics
        trades_per_day = trades / max(1, age_days)
        if trades_per_day > 20 and 0.6 < win_rate < 0.7:
            return "bot"

        # Skilled trader: Good but not perfect metrics
        if win_rate > 0.65 and growth > 2:
            return "skilled_trader"

        return "unknown"

    async def find_smart_money(self) -> List[SmartMoneyWallet]:
        """
        Main scan loop: Find wallets meeting smart money criteria.

        1. Scan recent blocks for active traders
        2. Filter to new wallets (<90 days)
        3. Analyze each for smart money patterns
        4. Return those meeting criteria
        """
        # Scan blockchain for recent trades
        trades = await self.scan_recent_trades()

        if not trades:
            log("No trades found in scan")
            return []

        # Get unique traders
        traders = self.get_unique_traders(trades)
        log(f"Found {len(traders)} unique traders")

        # Filter out already-seen wallets
        new_traders = [t for t in traders if t not in self.seen_wallets]
        log(f"Analyzing {len(new_traders)} new traders...")

        # Analyze each trader (with rate limiting)
        smart_money = []

        for i, address in enumerate(new_traders):
            if i > 0 and i % 10 == 0:
                log(f"  Analyzed {i}/{len(new_traders)} wallets...")
                await asyncio.sleep(1)  # Rate limit

            wallet = await self.analyze_wallet(address)

            if wallet:
                smart_money.append(wallet)
                self.seen_wallets.add(address)
                log(f"  FOUND: {address[:10]}... (${wallet.portfolio_value_usd:,.0f}, {wallet.win_rate:.0%} WR)")

        # Save seen wallets
        self._save_seen_wallets()

        log(f"Scan complete: {len(smart_money)} smart money wallets found")
        return smart_money

    async def close(self):
        """Cleanup resources."""
        await self.http_client.aclose()


async def send_telegram_alert(message: str):
    """Send alert via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("Telegram not configured, skipping alert")
        return

    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "disable_web_page_preview": True
            })
            log("[TG] Alert sent")
    except Exception as e:
        log(f"[TG] Error: {e}")


async def run_scanner():
    """
    Main entry point for blockchain scanner.

    Runs continuous scan loop every SCAN_INTERVAL_MINUTES.
    """
    rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")

    log("=" * 50)
    log("BLOCKCHAIN SMART MONEY SCANNER")
    log("=" * 50)
    log(f"RPC: {rpc_url[:30]}...")
    log(f"Scan interval: {SCAN_INTERVAL_MINUTES} minutes")
    log(f"Criteria: {MIN_GROWTH_30D}x growth, <{MAX_WALLET_AGE_DAYS}d old, >{MIN_WIN_RATE:.0%} WR")
    log("=" * 50)

    try:
        scanner = BlockchainScanner(rpc_url)

        # Send startup notification
        await send_telegram_alert(f"Blockchain Scanner started\nMonitoring Polygon for smart money...")

        while True:
            try:
                log(f"\n--- Scan at {datetime.now().strftime('%H:%M:%S')} ---")

                # Find smart money
                wallets = await scanner.find_smart_money()

                # Alert on new finds
                for wallet in wallets:
                    await send_telegram_alert(wallet.to_telegram_message())

                # Wait for next scan
                log(f"Next scan in {SCAN_INTERVAL_MINUTES} minutes...")
                await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)

            except Exception as e:
                log(f"Scan error: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error

    except KeyboardInterrupt:
        log("Scanner stopped")
    except Exception as e:
        log(f"Fatal error: {e}")
        raise
    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(run_scanner())
