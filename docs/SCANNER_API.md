# Polymarket Wallet Scanner API Documentation

## Overview

The `scanner.py` module provides a comprehensive toolkit for scanning Polymarket to identify emerging alpha traders with sudden profit growth. It includes rate limiting, caching, error handling, and async support.

## Features

- **Async HTTP requests** using httpx
- **Rate limiting** (configurable, default 5 req/sec)
- **Response caching** with TTL support
- **Automatic retries** with exponential backoff
- **Typed data models** using dataclasses
- **Batch operations** for analyzing multiple wallets
- **Comprehensive error handling**

## Installation

The scanner requires the following dependencies (already in `pyproject.toml`):

```bash
pip install httpx asyncio
```

## Quick Start

```python
import asyncio
from scanner import WalletScanner

async def main():
    async with WalletScanner() as scanner:
        # Scan for emerging traders
        emerging = await scanner.scan_for_emerging_traders(
            min_profit=5000,
            min_win_rate=0.85,
            max_age_days=60,
        )

        for trader in emerging:
            print(f"{trader.username}: ${trader.profit:.2f}")

asyncio.run(main())
```

## Data Models

### WalletProfile

Represents a trader's wallet profile with performance metrics.

**Attributes:**
- `address` (str): Wallet address
- `username` (Optional[str]): Display name
- `profit` (float): Total profit in USD
- `win_rate` (float): Win rate (0-1)
- `trade_count` (int): Number of trades
- `first_seen` (Optional[datetime]): First trade timestamp
- `markets_traded` (int): Number of unique markets
- `volume` (float): Total trading volume
- `rank` (Optional[int]): Leaderboard rank
- `avg_position_size` (float): Average position size
- `largest_win` (float): Largest single win
- `largest_loss` (float): Largest single loss
- `trades` (List[Trade]): Recent trades

**Computed Properties:**
- `age_days`: Account age in days
- `avg_profit_per_trade`: Average profit per trade

**Methods:**
- `to_dict()`: Convert to dictionary for serialization

### Trade

Represents a single trade on Polymarket.

**Attributes:**
- `timestamp` (datetime): Trade execution time
- `market_id` (str): Market identifier
- `side` (str): "buy" or "sell"
- `size` (float): Position size in USD
- `price` (float): Execution price
- `outcome` (str): Outcome/asset identifier
- `profit` (float): P&L for this trade
- `market_title` (Optional[str]): Human-readable market name

## Main Class: WalletScanner

### Initialization

```python
scanner = WalletScanner(
    rate_limit=5.0,      # Max requests per second
    cache_ttl=300,       # Cache TTL in seconds
    timeout=30,          # HTTP timeout in seconds
    max_retries=3,       # Max retry attempts
)
```

### Context Manager Usage (Recommended)

```python
async with WalletScanner() as scanner:
    # Scanner is ready to use
    leaderboard = await scanner.fetch_leaderboard()
    # Client is automatically closed on exit
```

## Core Methods

### fetch_leaderboard()

Fetch the Polymarket leaderboard of top performers.

```python
leaderboard = await scanner.fetch_leaderboard(
    limit=500,           # Max traders to fetch
    period="all",        # "all", "month", "week", "day"
)
```

**Returns:** `List[WalletProfile]`

**Example:**
```python
async with WalletScanner() as scanner:
    top_traders = await scanner.fetch_leaderboard(limit=10)
    for trader in top_traders:
        print(f"#{trader.rank} {trader.username}: ${trader.profit:,.2f}")
```

### fetch_wallet_activity()

Fetch trade history for a specific wallet.

```python
trades = await scanner.fetch_wallet_activity(
    address="0x1234...",  # Wallet address
    limit=1000,           # Max trades to fetch
)
```

**Returns:** `List[Trade]`

**Example:**
```python
trades = await scanner.fetch_wallet_activity("0x1234...", limit=100)
for trade in trades:
    print(f"{trade.timestamp}: {trade.side} ${trade.size:.2f} @ {trade.price:.3f}")
```

### fetch_wallet_stats()

Fetch comprehensive statistics for a specific wallet.

```python
profile = await scanner.fetch_wallet_stats("0x1234...")
```

**Returns:** `Optional[WalletProfile]`

**Example:**
```python
profile = await scanner.fetch_wallet_stats("0x1234...")
if profile:
    print(f"Profit: ${profile.profit:,.2f}")
    print(f"Win Rate: {profile.win_rate*100:.1f}%")
    print(f"Age: {profile.age_days} days")
```

### scan_for_emerging_traders()

Scan for emerging traders with sudden profit growth.

```python
emerging = await scanner.scan_for_emerging_traders(
    min_profit=5000.0,        # Min profit in USD
    min_win_rate=0.85,        # Min win rate (0-1)
    max_age_days=60,          # Max account age
    leaderboard_limit=500,    # Leaderboard entries to scan
)
```

**Returns:** `List[WalletProfile]` (sorted by profit, descending)

**Example:**
```python
async with WalletScanner() as scanner:
    emerging = await scanner.scan_for_emerging_traders(
        min_profit=5000,
        min_win_rate=0.85,
        max_age_days=60,
    )

    print(f"Found {len(emerging)} emerging traders:")
    for trader in emerging:
        print(f"  {trader.username or trader.address[:8]}")
        print(f"    Profit: ${trader.profit:.2f}")
        print(f"    Win Rate: {trader.win_rate*100:.1f}%")
        print(f"    Age: {trader.age_days} days")
```

### batch_fetch_wallet_stats()

Fetch stats for multiple wallets concurrently.

```python
profiles = await scanner.batch_fetch_wallet_stats(
    addresses=["0x1234...", "0x5678...", ...],
    max_concurrent=5,     # Max concurrent requests
)
```

**Returns:** `List[WalletProfile]`

**Example:**
```python
addresses = ["0x1234...", "0x5678...", "0x9abc..."]
profiles = await scanner.batch_fetch_wallet_stats(addresses, max_concurrent=5)

total_profit = sum(p.profit for p in profiles)
print(f"Combined profit: ${total_profit:,.2f}")
```

### fetch_market_data()

Fetch market data from Gamma API.

```python
market = await scanner.fetch_market_data(market_id="123")
```

**Returns:** `Optional[Dict[str, Any]]`

### clear_cache()

Clear all cached responses.

```python
scanner.clear_cache()
```

## Convenience Functions

### quick_scan()

Quick function to scan for emerging traders without creating a scanner instance.

```python
emerging = await quick_scan(
    min_profit=5000.0,
    min_win_rate=0.85,
    max_age_days=60,
)
```

### get_wallet_info()

Quick function to get info for a single wallet.

```python
profile = await get_wallet_info("0x1234...")
```

## Advanced Features

### Rate Limiting

The scanner includes a token bucket rate limiter that ensures you don't exceed the configured requests per second:

```python
scanner = WalletScanner(rate_limit=5.0)  # Max 5 requests/second
```

The rate limiter automatically throttles requests across all methods.

### Caching

Responses are automatically cached to avoid duplicate API calls:

```python
scanner = WalletScanner(cache_ttl=300)  # Cache for 5 minutes

# First call hits API
data1 = await scanner.fetch_leaderboard()

# Second call uses cache (if within TTL)
data2 = await scanner.fetch_leaderboard()

# Clear cache if needed
scanner.clear_cache()
```

### Error Handling

The scanner includes automatic retry logic with exponential backoff:

```python
scanner = WalletScanner(
    max_retries=3,    # Retry up to 3 times
    timeout=30,       # 30 second timeout
)

# Automatically retries on failure with exponential backoff:
# 1st retry: wait 1 second
# 2nd retry: wait 2 seconds
# 3rd retry: wait 4 seconds
```

### Custom HTTP Client

For advanced use cases, you can access the underlying httpx client:

```python
async with WalletScanner() as scanner:
    # scanner.client is an httpx.AsyncClient
    custom_response = await scanner.client.get("https://...")
```

## API Endpoints Used

The scanner interacts with three Polymarket API endpoints:

1. **Data API** (`https://data-api.polymarket.com`)
   - `/leaderboard` - Top performers
   - `/activity` - Trade history
   - `/users/{address}` - User stats

2. **Gamma API** (`https://gamma-api.polymarket.com`)
   - `/markets/{market_id}` - Market data

## Examples

See `examples/scan_example.py` for comprehensive usage examples including:

- Example 1: Basic leaderboard fetching
- Example 2: Detailed wallet analysis
- Example 3: Scanning for emerging traders
- Example 4: Batch analysis of multiple wallets
- Example 5: Using convenience functions

Run the examples:

```bash
cd C:/Projects/poly-scout
python examples/scan_example.py
```

## Best Practices

1. **Always use context manager** for automatic resource cleanup:
   ```python
   async with WalletScanner() as scanner:
       # Your code here
   ```

2. **Respect rate limits** - don't set rate_limit too high to avoid getting blocked

3. **Use batch operations** when analyzing multiple wallets:
   ```python
   # Good - concurrent requests with rate limiting
   profiles = await scanner.batch_fetch_wallet_stats(addresses)

   # Bad - sequential requests
   profiles = [await scanner.fetch_wallet_stats(addr) for addr in addresses]
   ```

4. **Handle missing data** gracefully:
   ```python
   profile = await scanner.fetch_wallet_stats(address)
   if profile and profile.age_days is not None:
       print(f"Age: {profile.age_days} days")
   else:
       print("Age data not available")
   ```

5. **Clear cache** when you need fresh data:
   ```python
   scanner.clear_cache()
   leaderboard = await scanner.fetch_leaderboard()  # Fresh data
   ```

## Troubleshooting

### "Connection refused" or timeout errors

- Check your internet connection
- Verify the API endpoints are accessible
- Increase the timeout: `WalletScanner(timeout=60)`

### Rate limit exceeded

- Decrease rate_limit: `WalletScanner(rate_limit=2.0)`
- Add delays between scans: `await asyncio.sleep(5)`

### Empty results

- API endpoints may have changed - check Polymarket API docs
- Cache may be stale - call `scanner.clear_cache()`
- Adjust search criteria (lower min_profit, min_win_rate)

### Memory issues with large scans

- Reduce leaderboard_limit
- Process results in batches
- Clear trades from profiles if not needed

## Performance Tips

1. **Use caching** - Set appropriate cache_ttl based on your needs
2. **Batch operations** - Use batch_fetch_wallet_stats() for multiple wallets
3. **Adjust limits** - Only fetch the data you need
4. **Concurrent requests** - The scanner handles concurrency automatically

## Contributing

When extending the scanner:

1. Add type hints to all functions
2. Include docstrings with Args/Returns
3. Handle errors gracefully
4. Add tests for new functionality
5. Update this documentation

## License

Part of the poly-scout project. See main repository for license details.
