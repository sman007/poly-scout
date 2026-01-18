# Polymarket Wallet Scanner

A comprehensive Python module for scanning Polymarket to identify emerging alpha traders with sudden profit growth.

## Features

- **Async HTTP requests** using httpx
- **Rate limiting** (max 5 req/sec by default)
- **Response caching** with configurable TTL
- **Automatic retries** with exponential backoff
- **Typed data models** (WalletProfile, Trade)
- **Batch operations** for analyzing multiple wallets
- **Error handling** with graceful degradation

## Quick Start

```python
import asyncio
from scanner import WalletScanner

async def main():
    async with WalletScanner() as scanner:
        # Find emerging traders
        emerging = await scanner.scan_for_emerging_traders(
            min_profit=5000,      # Min $5k profit
            min_win_rate=0.85,    # Min 85% win rate
            max_age_days=60,      # Max 60 days old
        )

        for trader in emerging:
            print(f"{trader.username}: ${trader.profit:.2f}")

asyncio.run(main())
```

## Module Structure

### Core Files

- **`C:/Projects/poly-scout/src/scanner.py`** (633 lines)
  - Main scanner module with all functionality
  - Classes: `WalletScanner`, `WalletProfile`, `Trade`, `SimpleCache`, `RateLimiter`
  - Methods: `fetch_leaderboard()`, `fetch_wallet_activity()`, `fetch_wallet_stats()`, `scan_for_emerging_traders()`

- **`C:/Projects/poly-scout/examples/scan_example.py`**
  - Comprehensive usage examples
  - 5 different example scenarios

- **`C:/Projects/poly-scout/tests/test_scanner.py`**
  - Unit tests for all major components
  - Includes mocked API tests

- **`C:/Projects/poly-scout/docs/SCANNER_API.md`**
  - Complete API documentation
  - Usage examples and best practices

## Key Classes

### WalletScanner

Main class for interacting with Polymarket APIs.

```python
scanner = WalletScanner(
    rate_limit=5.0,      # Max requests per second
    cache_ttl=300,       # Cache TTL in seconds
    timeout=30,          # HTTP timeout
    max_retries=3,       # Max retry attempts
)
```

### WalletProfile

Represents a trader's profile:

```python
@dataclass
class WalletProfile:
    address: str
    username: Optional[str]
    profit: float
    win_rate: float
    trade_count: int
    first_seen: Optional[datetime]
    markets_traded: int
    volume: float
    # ... and more
```

### Trade

Represents a single trade:

```python
@dataclass
class Trade:
    timestamp: datetime
    market_id: str
    side: str
    size: float
    price: float
    outcome: str
    profit: float
```

## Main Methods

### fetch_leaderboard(limit=500)

Fetch top performers from Polymarket leaderboard.

```python
leaderboard = await scanner.fetch_leaderboard(limit=100)
```

### fetch_wallet_activity(address, limit=1000)

Get trade history for a wallet.

```python
trades = await scanner.fetch_wallet_activity("0x1234...", limit=100)
```

### fetch_wallet_stats(address)

Get comprehensive stats for a wallet.

```python
profile = await scanner.fetch_wallet_stats("0x1234...")
```

### scan_for_emerging_traders(...)

Find new successful traders.

```python
emerging = await scanner.scan_for_emerging_traders(
    min_profit=5000,
    min_win_rate=0.85,
    max_age_days=60,
)
```

## API Endpoints

The scanner uses these Polymarket endpoints:

1. **Data API**: `https://data-api.polymarket.com`
   - `/leaderboard` - Top performers
   - `/activity` - Trade history
   - `/users/{address}` - User stats

2. **Gamma API**: `https://gamma-api.polymarket.com`
   - `/markets/{market_id}` - Market data

## Rate Limiting

Built-in token bucket rate limiter:

- Default: 5 requests/second
- Automatically throttles all requests
- Prevents API blocking

## Caching

Automatic response caching:

- Default TTL: 300 seconds (5 minutes)
- Cache key based on request parameters
- Clear cache: `scanner.clear_cache()`

## Error Handling

Automatic retry with exponential backoff:

- Default: 3 retries
- Wait times: 1s, 2s, 4s
- Graceful degradation on failure

## Examples

Run the comprehensive example script:

```bash
cd C:/Projects/poly-scout
python examples/scan_example.py
```

This demonstrates:
1. Fetching leaderboard
2. Analyzing wallet details
3. Scanning for emerging traders
4. Batch wallet analysis
5. Using convenience functions

## Testing

Run the test suite:

```bash
cd C:/Projects/poly-scout
pytest tests/test_scanner.py -v
```

Tests include:
- Data model validation
- Cache functionality
- Rate limiting
- Mocked API calls
- Convenience functions

## Usage Tips

1. **Always use context manager** for automatic cleanup:
   ```python
   async with WalletScanner() as scanner:
       # Your code
   ```

2. **Use batch operations** for multiple wallets:
   ```python
   profiles = await scanner.batch_fetch_wallet_stats(addresses)
   ```

3. **Handle missing data**:
   ```python
   if profile and profile.age_days is not None:
       print(f"Age: {profile.age_days} days")
   ```

4. **Clear cache** for fresh data:
   ```python
   scanner.clear_cache()
   ```

## Complete API Documentation

See `C:/Projects/poly-scout/docs/SCANNER_API.md` for:
- Detailed API reference
- All parameters and return types
- Advanced usage patterns
- Troubleshooting guide
- Performance tips

## Requirements

```toml
httpx>=0.27.0
asyncio>=3.4.3
python>=3.10
```

Already included in `pyproject.toml`.

## File Locations

- Scanner module: `C:/Projects/poly-scout/src/scanner.py`
- Examples: `C:/Projects/poly-scout/examples/scan_example.py`
- Tests: `C:/Projects/poly-scout/tests/test_scanner.py`
- Documentation: `C:/Projects/poly-scout/docs/SCANNER_API.md`

## Quick Commands

```bash
# Test import
python -c "from src.scanner import WalletScanner; print('OK')"

# Run examples
python examples/scan_example.py

# Run tests
pytest tests/test_scanner.py -v

# Check syntax
python -m py_compile src/scanner.py
```

## License

Part of the poly-scout project.
