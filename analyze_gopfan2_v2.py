import json
from collections import defaultdict
from datetime import datetime

# Load data
with open('C:/Projects/poly-scout/docs/gopfan2_trades_raw.json', 'r') as f:
    trades = json.load(f)

with open('C:/Projects/poly-scout/docs/gopfan2_positions_raw.json', 'r') as f:
    positions = json.load(f)

# More comprehensive weather keywords
weather_keywords = [
    'temperature', 'temp', 'weather', 'precipitation', 'rain', 'snow',
    'celsius', 'fahrenheit', 'degrees', 'climate', 'hottest', 'coldest',
    'heat', 'freeze', 'storm', 'hurricane', 'tornado', 'drought', 'flood'
]

def is_weather_trade(trade):
    title = trade.get('title', '').lower()
    slug = trade.get('slug', '').lower()
    return any(keyword in title or keyword in slug for keyword in weather_keywords)

weather_trades = [t for t in trades if is_weather_trade(t)]
weather_positions = [p for p in positions if is_weather_trade(p)]

print(f"Total trades: {len(trades)}")
print(f"Weather/climate trades: {len(weather_trades)}")
print(f"Total positions: {len(positions)}")
print(f"Weather/climate positions: {len(weather_positions)}")
print()

# If no weather trades found, print all unique markets
if len(weather_trades) == 0:
    print("No weather trades found in recent 500 trades.")
    print("\nThis suggests gopfan2's weather trading activity was earlier.")
    print("\nRecent trade date range:")
    print(f"  Newest: {datetime.fromtimestamp(trades[0]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Oldest: {datetime.fromtimestamp(trades[-1]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check for any climate-related trades
    climate_trades = [t for t in trades if 'hottest' in t['title'].lower() or 'climate' in t['title'].lower() or 'storm' in t['title'].lower()]
    if climate_trades:
        print(f"\nFound {len(climate_trades)} climate-related trades:")
        for t in climate_trades:
            dt = datetime.fromtimestamp(t['timestamp'])
            print(f"  {dt.strftime('%Y-%m-%d')}: {t['side']} {t['outcome']} @ ${t['price']:.4f} - {t['title']}")

    print("\n" + "="*80)
    print("GENERAL TRADING ANALYSIS (Recent 500 trades)")
    print("="*80)

    # Overall stats
    buy_count = sum(1 for t in trades if t['side'] == 'BUY')
    sell_count = sum(1 for t in trades if t['side'] == 'SELL')
    print(f"\nOverall Buy/Sell:")
    print(f"  Buy trades: {buy_count} ({buy_count/len(trades)*100:.1f}%)")
    print(f"  Sell trades: {sell_count} ({sell_count/len(trades)*100:.1f}%)")

    # Total volume
    total_volume = sum(t['usdcSize'] for t in trades)
    print(f"\nTotal trading volume (last 500 trades): ${total_volume:,.2f}")

    # Market categories
    print("\nTop 10 markets by trade count:")
    markets = defaultdict(int)
    for t in trades:
        markets[t['title']] += 1
    for market, count in sorted(markets.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {count:3d} trades: {market}")

    # Price range analysis
    prices = [t['price'] for t in trades]
    print(f"\nPrice range: ${min(prices):.4f} - ${max(prices):.4f}")

    # Low probability betting (< 0.10)
    low_prob = [t for t in trades if t['price'] < 0.10]
    print(f"\nLow probability bets (< $0.10): {len(low_prob)} trades ({len(low_prob)/len(trades)*100:.1f}%)")
    if low_prob:
        print(f"  Average price: ${sum(t['price'] for t in low_prob)/len(low_prob):.4f}")
        print(f"  Total volume: ${sum(t['usdcSize'] for t in low_prob):,.2f}")

    sys.exit(0)

# Analyze weather trades if found
if weather_trades:
    print("=" * 80)
    print("WEATHER/CLIMATE TRADE ANALYSIS")
    print("=" * 80)
    print()

    # Buy vs Sell
    buy_count = sum(1 for t in weather_trades if t['side'] == 'BUY')
    sell_count = sum(1 for t in weather_trades if t['side'] == 'SELL')
    print(f"Buy trades: {buy_count} ({buy_count/len(weather_trades)*100:.1f}%)")
    print(f"Sell trades: {sell_count} ({sell_count/len(weather_trades)*100:.1f}%)")
    if sell_count > 0:
        print(f"Buy/Sell ratio: {buy_count/sell_count:.2f}")
    print()

    # Price distribution
    prices = [t['price'] for t in weather_trades]
    print(f"Price range: ${min(prices):.4f} - ${max(prices):.4f}")
    print(f"Average price: ${sum(prices)/len(prices):.4f}")
    print(f"Median price: ${sorted(prices)[len(prices)//2]:.4f}")
    print()

    # Price buckets
    price_buckets = defaultdict(int)
    for price in prices:
        if price < 0.1:
            price_buckets['0.00-0.10'] += 1
        elif price < 0.2:
            price_buckets['0.10-0.20'] += 1
        elif price < 0.3:
            price_buckets['0.20-0.30'] += 1
        elif price < 0.4:
            price_buckets['0.30-0.40'] += 1
        elif price < 0.5:
            price_buckets['0.40-0.50'] += 1
        elif price < 0.6:
            price_buckets['0.50-0.60'] += 1
        elif price < 0.7:
            price_buckets['0.60-0.70'] += 1
        elif price < 0.8:
            price_buckets['0.70-0.80'] += 1
        elif price < 0.9:
            price_buckets['0.80-0.90'] += 1
        else:
            price_buckets['0.90-1.00'] += 1

    print("Price distribution:")
    for bucket in sorted(price_buckets.keys()):
        pct = price_buckets[bucket] / len(weather_trades) * 100
        print(f"  {bucket}: {price_buckets[bucket]:3d} trades ({pct:5.1f}%)")
    print()

    # Outcome preferences (Yes vs No)
    yes_count = sum(1 for t in weather_trades if t.get('outcome') == 'Yes')
    no_count = sum(1 for t in weather_trades if t.get('outcome') == 'No')
    print(f"Yes outcomes: {yes_count} ({yes_count/len(weather_trades)*100:.1f}%)")
    print(f"No outcomes: {no_count} ({no_count/len(weather_trades)*100:.1f}%)")
    print()

    # Markets traded
    markets = defaultdict(list)
    for t in weather_trades:
        markets[t['title']].append(t)

    print(f"Unique weather markets traded: {len(markets)}")
    print("\nAll weather markets:")
    for market, market_trades in sorted(markets.items(), key=lambda x: len(x[1]), reverse=True):
        total_vol = sum(t['usdcSize'] for t in market_trades)
        avg_price = sum(t['price'] for t in market_trades) / len(market_trades)
        print(f"\n  {market}")
        print(f"    Trades: {len(market_trades)}")
        print(f"    Total volume: ${total_vol:.2f}")
        print(f"    Avg price: ${avg_price:.4f}")
        print(f"    Side: {sum(1 for t in market_trades if t['side'] == 'BUY')} BUY, {sum(1 for t in market_trades if t['side'] == 'SELL')} SELL")
    print()

    # Position sizes (USDC)
    usdc_sizes = [t['usdcSize'] for t in weather_trades]
    print(f"Position size (USDC) range: ${min(usdc_sizes):.2f} - ${max(usdc_sizes):.2f}")
    print(f"Average position size: ${sum(usdc_sizes)/len(usdc_sizes):.2f}")
    print(f"Median position size: ${sorted(usdc_sizes)[len(usdc_sizes)//2]:.2f}")
    print(f"Total volume: ${sum(usdc_sizes):,.2f}")
    print()

    # Sample trades
    print("All weather trades (chronological):")
    for i, t in enumerate(weather_trades, 1):
        dt = datetime.fromtimestamp(t['timestamp'])
        print(f"\n{i}. {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Market: {t['title']}")
        print(f"   Side: {t['side']} {t['outcome']} @ ${t['price']:.4f}")
        print(f"   Size: {t['size']:.2f} shares (${t['usdcSize']:.2f} USDC)")

import sys
