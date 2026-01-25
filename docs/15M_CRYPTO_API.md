# 15-Minute Crypto Markets - API Reference

## How to Query 15-Minute BTC Markets

### CORRECT Method
```
GET https://gamma-api.polymarket.com/markets?slug=btc-updown-15m-{timestamp}
```

Returns an **array** with the market object.

### WRONG Method (Returns 422)
```
GET https://gamma-api.polymarket.com/markets/{slug}
```
This endpoint expects a **numeric ID**, not a slug. Error: `{"type":"validation error","error":"id is invalid"}`

## Timestamp Calculation

Markets resolve every 15 minutes in Eastern Time (ET = UTC-5 in winter, UTC-4 in summer).

```python
import time

# Current Unix timestamp
now = int(time.time())

# ET offset (EST = UTC-5, EDT = UTC-4)
et_offset = -5 * 3600  # Winter (EST)

# Calculate next 15-min window end
et_time = now + et_offset
next_window_end = ((int(et_time) // 900) + 1) * 900 - et_offset

# Construct slug
slug = f'btc-updown-15m-{next_window_end}'
```

## Example Response

```json
[{
  "id": "1260997",
  "question": "Bitcoin Up or Down - January 25, 4:45PM-5:00PM ET",
  "conditionId": "0xb7a94dce0b29e828e1233abb12e916acd82f2bdad9cd90cabfc6caef462ff0ca",
  "slug": "btc-updown-15m-1769377500",
  "resolutionSource": "https://data.chain.link/streams/btc-usd",
  "endDate": "2026-01-25T22:00:00Z",
  "liquidity": "11354.8648",
  "startDate": "2026-01-24T21:53:23.435562Z",
  "image": "https://polymarket-upload.s3.us-east-2.amazonaws.com/BTC+fullsize.png",
  "outcomePrices": "[\"0.5\", \"0.5\"]",
  "outcomes": "[\"Up\", \"Down\"]",
  "clobTokenIds": "[\"token_id_up\", \"token_id_down\"]"
}]
```

## Other Crypto Assets

Same pattern works for:
- `eth-updown-15m-{timestamp}` - Ethereum
- `sol-updown-15m-{timestamp}` - Solana
- `xrp-updown-15m-{timestamp}` - XRP

## Fee Structure (CRITICAL)

| Market Type | Maker Fee | Taker Fee | Viability |
|-------------|-----------|-----------|-----------|
| **15-min crypto** | 0% | **~3.15%** | NOT VIABLE for arb |
| Hourly crypto | 0% | 0% | VIABLE |
| 4-hour+ crypto | 0% | 0% | VIABLE |

## Why 15-Min Arb Doesn't Work

1. **3.15% taker fee** at 50% probability eliminates any edge
2. Even with YES+NO < $1.00, fees consume the profit
3. Reference Wallet ($8.96M) **stopped trading these** in Jan 2026
4. They shifted to multi-outcome political arbitrage instead

## What TO Use Instead

1. **Hourly crypto arbitrage** - Same logic, 0% fees
2. **Multi-outcome political arbitrage** - Reference Wallet's current strategy
3. **Sports mispricing** - Already in poly-scout daemon
4. **Resolution farming** - 99-99.5c markets near resolution

## Webpage

Live markets: https://polymarket.com/crypto/15M

---

*Documented: 2026-01-26*
*Source: API debugging session*
