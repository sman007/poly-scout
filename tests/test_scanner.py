"""
Unit tests for the Polymarket Wallet Scanner module.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scanner import (
    WalletScanner,
    WalletProfile,
    Trade,
    SimpleCache,
    RateLimiter,
    quick_scan,
    get_wallet_info,
)


# ============================================================================
# Test Data Models
# ============================================================================

def test_trade_creation():
    """Test Trade dataclass creation."""
    trade = Trade(
        timestamp=datetime.now(),
        market_id="market_123",
        side="buy",
        size=100.0,
        price=0.65,
        outcome="YES",
        profit=25.0,
    )

    assert trade.market_id == "market_123"
    assert trade.side == "buy"
    assert trade.size == 100.0
    assert trade.profit == 25.0


def test_trade_timestamp_conversion():
    """Test Trade timestamp conversion from various formats."""
    # Test with integer timestamp
    trade1 = Trade(
        timestamp=1640000000,
        market_id="market_123",
        side="buy",
        size=100.0,
        price=0.65,
        outcome="YES",
        profit=25.0,
    )
    assert isinstance(trade1.timestamp, datetime)

    # Test with datetime object
    now = datetime.now()
    trade2 = Trade(
        timestamp=now,
        market_id="market_123",
        side="buy",
        size=100.0,
        price=0.65,
        outcome="YES",
        profit=25.0,
    )
    assert trade2.timestamp == now


def test_wallet_profile_creation():
    """Test WalletProfile dataclass creation."""
    profile = WalletProfile(
        address="0x1234567890abcdef",
        username="test_trader",
        profit=10000.0,
        win_rate=0.85,
        trade_count=100,
        markets_traded=25,
    )

    assert profile.address == "0x1234567890abcdef"
    assert profile.username == "test_trader"
    assert profile.profit == 10000.0
    assert profile.win_rate == 0.85


def test_wallet_profile_age_days():
    """Test WalletProfile age_days property."""
    profile = WalletProfile(
        address="0x1234",
        first_seen=datetime(2024, 1, 1),
    )

    # Age should be positive number of days
    assert profile.age_days is not None
    assert profile.age_days > 0


def test_wallet_profile_avg_profit():
    """Test WalletProfile avg_profit_per_trade property."""
    profile = WalletProfile(
        address="0x1234",
        profit=1000.0,
        trade_count=10,
    )

    assert profile.avg_profit_per_trade == 100.0

    # Test with zero trades
    profile2 = WalletProfile(address="0x5678", profit=100.0, trade_count=0)
    assert profile2.avg_profit_per_trade == 0.0


def test_wallet_profile_to_dict():
    """Test WalletProfile to_dict method."""
    profile = WalletProfile(
        address="0x1234",
        username="trader",
        profit=5000.0,
        win_rate=0.90,
        trade_count=50,
    )

    profile_dict = profile.to_dict()

    assert isinstance(profile_dict, dict)
    assert profile_dict["address"] == "0x1234"
    assert profile_dict["username"] == "trader"
    assert profile_dict["profit"] == 5000.0
    assert profile_dict["win_rate"] == 0.90


# ============================================================================
# Test Cache
# ============================================================================

def test_simple_cache_set_get():
    """Test basic cache set and get operations."""
    cache = SimpleCache(ttl_seconds=60)

    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    cache.set("key2", {"data": 123})
    assert cache.get("key2") == {"data": 123}


def test_simple_cache_expiration():
    """Test cache expiration."""
    cache = SimpleCache(ttl_seconds=1)

    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"

    # Wait for expiration
    import time
    time.sleep(1.1)

    assert cache.get("key1") is None


def test_simple_cache_clear():
    """Test cache clear operation."""
    cache = SimpleCache()

    cache.set("key1", "value1")
    cache.set("key2", "value2")

    assert cache.get("key1") == "value1"
    assert cache.get("key2") == "value2"

    cache.clear()

    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_simple_cache_make_key():
    """Test cache key generation."""
    key1 = SimpleCache.make_key("arg1", "arg2", param1="value1")
    key2 = SimpleCache.make_key("arg1", "arg2", param1="value1")
    key3 = SimpleCache.make_key("arg1", "arg3", param1="value1")

    # Same arguments should produce same key
    assert key1 == key2

    # Different arguments should produce different key
    assert key1 != key3


# ============================================================================
# Test Rate Limiter
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_basic():
    """Test basic rate limiting."""
    limiter = RateLimiter(requests_per_second=10.0)

    start_time = asyncio.get_event_loop().time()

    # Make 3 requests
    for _ in range(3):
        await limiter.acquire()

    end_time = asyncio.get_event_loop().time()
    elapsed = end_time - start_time

    # Should take at least 0.2 seconds (2 intervals at 0.1s each)
    assert elapsed >= 0.2


@pytest.mark.asyncio
async def test_rate_limiter_concurrent():
    """Test rate limiting with concurrent requests."""
    limiter = RateLimiter(requests_per_second=5.0)

    async def make_request():
        await limiter.acquire()
        return True

    # Make 5 concurrent requests
    results = await asyncio.gather(*[make_request() for _ in range(5)])

    assert len(results) == 5
    assert all(results)


# ============================================================================
# Test WalletScanner
# ============================================================================

@pytest.mark.asyncio
async def test_wallet_scanner_initialization():
    """Test WalletScanner initialization."""
    scanner = WalletScanner(
        rate_limit=5.0,
        cache_ttl=300,
        timeout=30,
        max_retries=3,
    )

    assert scanner.rate_limiter.requests_per_second == 5.0
    assert scanner.cache.ttl_seconds == 300
    assert scanner.timeout == 30
    assert scanner.max_retries == 3


@pytest.mark.asyncio
async def test_wallet_scanner_context_manager():
    """Test WalletScanner context manager."""
    async with WalletScanner() as scanner:
        assert scanner.client is not None

    # Client should be closed after exiting context
    # Note: We can't directly test if client is closed, but it should be


@pytest.mark.asyncio
async def test_wallet_scanner_clear_cache():
    """Test cache clearing."""
    async with WalletScanner() as scanner:
        scanner.cache.set("test_key", "test_value")
        assert scanner.cache.get("test_key") == "test_value"

        scanner.clear_cache()
        assert scanner.cache.get("test_key") is None


# ============================================================================
# Test Mocked API Calls
# ============================================================================

@pytest.mark.asyncio
async def test_fetch_leaderboard_mock():
    """Test fetch_leaderboard with mocked API response."""
    mock_response = [
        {
            "address": "0x1234",
            "username": "trader1",
            "profit": 10000.0,
            "win_rate": 0.85,
            "trade_count": 100,
            "markets_traded": 25,
            "volume": 50000.0,
        },
        {
            "address": "0x5678",
            "username": "trader2",
            "profit": 8000.0,
            "win_rate": 0.80,
            "trade_count": 80,
            "markets_traded": 20,
            "volume": 40000.0,
        },
    ]

    async with WalletScanner() as scanner:
        # Mock the _request method
        scanner._request = AsyncMock(return_value=mock_response)

        leaderboard = await scanner.fetch_leaderboard(limit=10)

        assert len(leaderboard) == 2
        assert leaderboard[0].address == "0x1234"
        assert leaderboard[0].username == "trader1"
        assert leaderboard[0].profit == 10000.0
        assert leaderboard[0].rank == 1
        assert leaderboard[1].rank == 2


@pytest.mark.asyncio
async def test_fetch_wallet_activity_mock():
    """Test fetch_wallet_activity with mocked API response."""
    mock_response = [
        {
            "timestamp": 1640000000,
            "market_id": "market_123",
            "side": "buy",
            "size": 100.0,
            "price": 0.65,
            "outcome": "YES",
            "profit": 25.0,
        },
        {
            "timestamp": 1640001000,
            "market_id": "market_456",
            "side": "sell",
            "size": 150.0,
            "price": 0.55,
            "outcome": "NO",
            "profit": -10.0,
        },
    ]

    async with WalletScanner() as scanner:
        scanner._request = AsyncMock(return_value=mock_response)

        trades = await scanner.fetch_wallet_activity("0x1234", limit=100)

        assert len(trades) == 2
        assert trades[0].market_id == "market_123"
        assert trades[0].side == "buy"
        assert trades[0].profit == 25.0
        assert trades[1].profit == -10.0


@pytest.mark.asyncio
async def test_fetch_wallet_stats_mock():
    """Test fetch_wallet_stats with mocked API response."""
    mock_user_response = {
        "address": "0x1234",
        "username": "trader1",
        "profit": 10000.0,
        "win_rate": 0.85,
        "trade_count": 100,
        "markets_traded": 25,
        "volume": 50000.0,
    }

    mock_activity_response = [
        {
            "timestamp": 1640000000,
            "market_id": "market_123",
            "side": "buy",
            "size": 100.0,
            "price": 0.65,
            "outcome": "YES",
            "profit": 25.0,
        },
    ]

    async with WalletScanner() as scanner:
        # Mock both API calls
        scanner._request = AsyncMock(side_effect=[
            mock_user_response,
            mock_activity_response,
        ])

        profile = await scanner.fetch_wallet_stats("0x1234")

        assert profile is not None
        assert profile.address == "0x1234"
        assert profile.username == "trader1"
        assert profile.profit == 10000.0
        assert len(profile.trades) == 1


# ============================================================================
# Test Convenience Functions
# ============================================================================

@pytest.mark.asyncio
async def test_quick_scan_mock():
    """Test quick_scan convenience function with mock."""
    with patch('scanner.WalletScanner') as MockScanner:
        mock_scanner_instance = MockScanner.return_value.__aenter__.return_value
        mock_scanner_instance.scan_for_emerging_traders = AsyncMock(return_value=[
            WalletProfile(
                address="0x1234",
                username="emerging_trader",
                profit=6000.0,
                win_rate=0.90,
                trade_count=50,
            ),
        ])

        results = await quick_scan(min_profit=5000, min_win_rate=0.85, max_age_days=60)

        assert len(results) == 1
        assert results[0].address == "0x1234"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
