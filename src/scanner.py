"""
Polymarket Wallet Scanner Module

Scans Polymarket for wallets with sudden profit growth and identifies emerging alpha traders.
Uses async HTTP requests with rate limiting, caching, and error handling.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

import httpx


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Trade:
    """Represents a single trade on Polymarket."""

    timestamp: datetime
    market_id: str
    side: str  # "buy" or "sell"
    size: float
    price: float
    outcome: str
    profit: float
    market_title: Optional[str] = None

    def __post_init__(self):
        """Convert timestamp to datetime if it's a string or int."""
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        elif isinstance(self.timestamp, (int, float)):
            self.timestamp = datetime.fromtimestamp(self.timestamp)


@dataclass
class WalletProfile:
    """Represents a trader's wallet profile with performance metrics."""

    address: str
    username: Optional[str] = None
    profit: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0
    first_seen: Optional[datetime] = None
    markets_traded: int = 0
    volume: float = 0.0
    rank: Optional[int] = None
    avg_position_size: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    trades: List[Trade] = field(default_factory=list)

    @property
    def age_days(self) -> Optional[float]:
        """Calculate account age in days."""
        if self.first_seen:
            return (datetime.now() - self.first_seen).days
        return None

    @property
    def avg_profit_per_trade(self) -> float:
        """Calculate average profit per trade."""
        if self.trade_count > 0:
            return self.profit / self.trade_count
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'address': self.address,
            'username': self.username,
            'profit': self.profit,
            'win_rate': self.win_rate,
            'trade_count': self.trade_count,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'markets_traded': self.markets_traded,
            'volume': self.volume,
            'rank': self.rank,
            'avg_position_size': self.avg_position_size,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'age_days': self.age_days,
            'avg_profit_per_trade': self.avg_profit_per_trade,
        }


# ============================================================================
# Cache Implementation
# ============================================================================

class SimpleCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, tuple[Any, float]] = {}
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp."""
        self.cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_str = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()


# ============================================================================
# Rate Limiter
# ============================================================================

class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, requests_per_second: float = 5.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        async with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_interval:
                wait_time = self.min_interval - time_since_last_request
                await asyncio.sleep(wait_time)

            self.last_request_time = time.time()


# ============================================================================
# Main Scanner Class
# ============================================================================

class WalletScanner:
    """
    Polymarket Wallet Scanner

    Scans Polymarket for wallets with sudden profit growth and identifies
    emerging alpha traders using various API endpoints.
    """

    BASE_URL = "https://data-api.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(
        self,
        rate_limit: float = 5.0,
        cache_ttl: int = 300,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize the wallet scanner.

        Args:
            rate_limit: Maximum requests per second (default: 5.0)
            cache_ttl: Cache time-to-live in seconds (default: 300)
            timeout: HTTP request timeout in seconds (default: 30)
            max_retries: Maximum number of retries for failed requests (default: 3)
        """
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit)
        self.cache = SimpleCache(ttl_seconds=cache_ttl)
        self.timeout = timeout
        self.max_retries = max_retries
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with rate limiting, caching, and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            params: Query parameters
            use_cache: Whether to use cache for this request

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPError: If all retries fail
        """
        # Check cache first
        if use_cache and method.upper() == 'GET':
            cache_key = SimpleCache.make_key(url, params)
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result

        # Ensure client is initialized
        if not self.client:
            self.client = httpx.AsyncClient(timeout=self.timeout)

        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                await self.rate_limiter.acquire()

                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                )
                response.raise_for_status()

                result = response.json()

                # Cache successful GET requests
                if use_cache and method.upper() == 'GET':
                    cache_key = SimpleCache.make_key(url, params)
                    self.cache.set(cache_key, result)

                return result

            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                continue

        # All retries failed
        raise last_exception

    async def fetch_leaderboard(
        self,
        limit: int = 500,
        period: str = "all",
    ) -> List[WalletProfile]:
        """
        Fetch the Polymarket leaderboard of top performers.

        Args:
            limit: Maximum number of traders to fetch (default: 500)
            period: Time period - "all", "month", "week", "day" (default: "all")

        Returns:
            List of WalletProfile objects for top traders
        """
        url = f"{self.BASE_URL}/v1/leaderboard"
        params = {
            "limit": limit,
            "window": period,  # API uses "window" not "period"
        }

        try:
            data = await self._request("GET", url, params)

            # Parse response - structure may vary based on actual API
            profiles = []
            traders = data if isinstance(data, list) else data.get('traders', [])

            for idx, trader in enumerate(traders[:limit], start=1):
                profile = WalletProfile(
                    address=trader.get('address', ''),
                    username=trader.get('username') or trader.get('name'),
                    profit=float(trader.get('profit', 0) or trader.get('pnl', 0) or 0),
                    win_rate=float(trader.get('win_rate', 0) or trader.get('winRate', 0) or 0),
                    trade_count=int(trader.get('trade_count', 0) or trader.get('trades', 0) or 0),
                    markets_traded=int(trader.get('markets_traded', 0) or trader.get('markets', 0) or 0),
                    volume=float(trader.get('volume', 0) or 0),
                    rank=idx,
                )
                profiles.append(profile)

            return profiles

        except Exception as e:
            print(f"Error fetching leaderboard: {e}")
            return []

    async def fetch_wallet_activity(
        self,
        address: str,
        limit: int = 500,
    ) -> List[Trade]:
        """
        Fetch trade history for a specific wallet.

        Args:
            address: Wallet address
            limit: Maximum number of trades to fetch (default: 500, max: 500)

        Returns:
            List of Trade objects
        """
        url = f"{self.BASE_URL}/activity"
        params = {
            "user": address,  # API uses "user" not "address"
            "limit": min(limit, 500),  # Max 500 per API docs
        }

        try:
            data = await self._request("GET", url, params)

            # Parse response
            trades = []
            activities = data if isinstance(data, list) else data.get('activity', [])

            for activity in activities[:limit]:
                try:
                    trade = Trade(
                        timestamp=activity.get('timestamp', datetime.now()),
                        market_id=activity.get('market_id', '') or activity.get('marketId', ''),
                        side=activity.get('side', 'buy'),
                        size=float(activity.get('size', 0) or activity.get('amount', 0) or 0),
                        price=float(activity.get('price', 0) or 0),
                        outcome=activity.get('outcome', '') or activity.get('asset', ''),
                        profit=float(activity.get('profit', 0) or activity.get('pnl', 0) or 0),
                        market_title=activity.get('market_title') or activity.get('title'),
                    )
                    trades.append(trade)
                except Exception as e:
                    # Skip malformed trades
                    continue

            return trades

        except Exception as e:
            print(f"Error fetching wallet activity for {address}: {e}")
            return []

    async def fetch_wallet_stats(self, address: str) -> Optional[WalletProfile]:
        """
        Fetch comprehensive statistics for a specific wallet.

        Derives stats from activity data since there's no direct user endpoint.

        Args:
            address: Wallet address

        Returns:
            WalletProfile with detailed stats, or None if not found
        """
        try:
            # Fetch activity to derive stats
            trades = await self.fetch_wallet_activity(address, limit=500)

            if not trades:
                print(f"No activity found for {address}")
                return None

            # Calculate stats from trades
            total_profit = sum(t.profit for t in trades)
            winning_trades = [t for t in trades if t.profit > 0]
            win_rate = len(winning_trades) / len(trades) if trades else 0

            # Get unique markets
            markets = set(t.market_id for t in trades if t.market_id)

            # Calculate volume
            volume = sum(t.size * t.price for t in trades if t.size and t.price)

            # Position sizes
            sizes = [t.size for t in trades if t.size > 0]
            avg_size = sum(sizes) / len(sizes) if sizes else 0

            # Profits
            profits = [t.profit for t in trades]
            largest_win = max(profits) if profits else 0
            largest_loss = min(profits) if profits else 0

            # First seen
            timestamps = [t.timestamp for t in trades if t.timestamp]
            first_seen = min(timestamps) if timestamps else None

            profile = WalletProfile(
                address=address,
                profit=total_profit,
                win_rate=win_rate,
                trade_count=len(trades),
                markets_traded=len(markets),
                volume=volume,
                avg_position_size=avg_size,
                largest_win=largest_win,
                largest_loss=largest_loss,
                first_seen=first_seen,
                trades=trades,
            )

            return profile

        except Exception as e:
            print(f"Error fetching wallet stats for {address}: {e}")
            return None

    async def fetch_market_data(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch market data from Gamma API.

        Args:
            market_id: Market identifier

        Returns:
            Market data dictionary or None if not found
        """
        url = f"{self.GAMMA_URL}/markets/{market_id}"

        try:
            data = await self._request("GET", url)
            return data
        except Exception as e:
            print(f"Error fetching market data for {market_id}: {e}")
            return None

    async def scan_for_emerging_traders(
        self,
        min_profit: float = 5000.0,
        min_win_rate: float = 0.85,
        max_age_days: int = 60,
        leaderboard_limit: int = 500,
    ) -> List[WalletProfile]:
        """
        Scan for emerging traders with sudden profit growth.

        Identifies wallets that are:
        - Relatively new (account age <= max_age_days)
        - Highly profitable (profit >= min_profit)
        - High win rate (win_rate >= min_win_rate)

        Args:
            min_profit: Minimum profit in USD (default: 5000)
            min_win_rate: Minimum win rate 0-1 (default: 0.85)
            max_age_days: Maximum account age in days (default: 60)
            leaderboard_limit: Number of leaderboard entries to scan (default: 500)

        Returns:
            List of WalletProfile objects matching criteria, sorted by profit
        """
        print(f"Scanning leaderboard for emerging traders...")
        print(f"Criteria: profit >= ${min_profit}, win_rate >= {min_win_rate*100}%, age <= {max_age_days} days")

        # Fetch leaderboard
        leaderboard = await self.fetch_leaderboard(limit=leaderboard_limit)

        # Filter by profit and win rate first (quick filters)
        candidates = [
            profile for profile in leaderboard
            if profile.profit >= min_profit and profile.win_rate >= min_win_rate
        ]

        print(f"Found {len(candidates)} candidates meeting profit/win-rate criteria")

        # Fetch detailed stats for each candidate to check age
        emerging_traders = []

        for i, candidate in enumerate(candidates, start=1):
            print(f"Analyzing candidate {i}/{len(candidates)}: {candidate.address}")

            # Get detailed stats including first_seen
            detailed_profile = await self.fetch_wallet_stats(candidate.address)

            if detailed_profile and detailed_profile.age_days is not None:
                if detailed_profile.age_days <= max_age_days:
                    print(f"  -> MATCH! Age: {detailed_profile.age_days} days, Profit: ${detailed_profile.profit:.2f}")
                    emerging_traders.append(detailed_profile)
                else:
                    print(f"  -> Too old ({detailed_profile.age_days} days)")
            else:
                print(f"  -> Could not determine age")

        # Sort by profit (descending)
        emerging_traders.sort(key=lambda x: x.profit, reverse=True)

        print(f"\nFound {len(emerging_traders)} emerging traders!")
        return emerging_traders

    async def batch_fetch_wallet_stats(
        self,
        addresses: List[str],
        max_concurrent: int = 5,
    ) -> List[WalletProfile]:
        """
        Fetch stats for multiple wallets concurrently.

        Args:
            addresses: List of wallet addresses
            max_concurrent: Maximum concurrent requests (default: 5)

        Returns:
            List of WalletProfile objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_with_semaphore(address: str) -> Optional[WalletProfile]:
            async with semaphore:
                return await self.fetch_wallet_stats(address)

        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None and exceptions
        profiles = [
            result for result in results
            if isinstance(result, WalletProfile)
        ]

        return profiles

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self.cache.clear()


# ============================================================================
# Convenience Functions
# ============================================================================

async def quick_scan(
    min_profit: float = 5000.0,
    min_win_rate: float = 0.85,
    max_age_days: int = 60,
) -> List[WalletProfile]:
    """
    Quick convenience function to scan for emerging traders.

    Args:
        min_profit: Minimum profit in USD
        min_win_rate: Minimum win rate (0-1)
        max_age_days: Maximum account age in days

    Returns:
        List of emerging trader profiles
    """
    async with WalletScanner() as scanner:
        return await scanner.scan_for_emerging_traders(
            min_profit=min_profit,
            min_win_rate=min_win_rate,
            max_age_days=max_age_days,
        )


async def get_wallet_info(address: str) -> Optional[WalletProfile]:
    """
    Quick convenience function to get info for a single wallet.

    Args:
        address: Wallet address

    Returns:
        WalletProfile or None if not found
    """
    async with WalletScanner() as scanner:
        return await scanner.fetch_wallet_stats(address)


# ============================================================================
# Example Usage
# ============================================================================

async def main():
    """Example usage of the WalletScanner."""

    # Create scanner instance
    async with WalletScanner(rate_limit=5.0, cache_ttl=300) as scanner:

        # 1. Fetch leaderboard
        print("Fetching leaderboard...")
        leaderboard = await scanner.fetch_leaderboard(limit=10)
        print(f"Top {len(leaderboard)} traders:")
        for profile in leaderboard[:5]:
            print(f"  {profile.rank}. {profile.username or profile.address[:8]}: ${profile.profit:.2f}")

        print()

        # 2. Get detailed stats for a specific wallet
        if leaderboard:
            top_trader = leaderboard[0]
            print(f"Fetching detailed stats for {top_trader.address}...")
            stats = await scanner.fetch_wallet_stats(top_trader.address)
            if stats:
                print(f"  Profit: ${stats.profit:.2f}")
                print(f"  Win Rate: {stats.win_rate*100:.1f}%")
                print(f"  Trades: {stats.trade_count}")
                print(f"  Markets: {stats.markets_traded}")
                print(f"  Age: {stats.age_days} days" if stats.age_days else "  Age: Unknown")

        print()

        # 3. Scan for emerging traders
        print("Scanning for emerging traders...")
        emerging = await scanner.scan_for_emerging_traders(
            min_profit=5000,
            min_win_rate=0.85,
            max_age_days=60,
        )

        print(f"\nFound {len(emerging)} emerging traders:")
        for trader in emerging[:10]:
            print(f"  {trader.username or trader.address[:8]}")
            print(f"    Profit: ${trader.profit:.2f}")
            print(f"    Win Rate: {trader.win_rate*100:.1f}%")
            print(f"    Age: {trader.age_days} days")
            print(f"    Trades: {trader.trade_count}")


if __name__ == "__main__":
    asyncio.run(main())
