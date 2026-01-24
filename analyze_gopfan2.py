import json
from collections import defaultdict
from datetime import datetime

# Load data
with open('C:/Projects/poly-scout/docs/gopfan2_trades_raw.json', 'r') as f:
    trades = json.load(f)

with open('C:/Projects/poly-scout/docs/gopfan2_positions_raw.json', 'r') as f:
    positions = json.load(f)

# Filter for weather/temperature related trades
weather_keywords = ['temperature', 'temp', 'weather', 'precipitation', 'rain', 'snow',
                   'nyc', 'london', 'celsius', 'fahrenheit', 'degrees', 'high temp',
                   'low temp', 'or higher', 'or lower', 'climate']

def is_weather_trade(trade):
    title = trade.get('title', '').lower()
    slug = trade.get('slug', '').lower()
    return any(keyword in title or keyword in slug for keyword in weather_keywords)

weather_trades = [t for t in trades if is_weather_trade(t)]
weather_positions = [p for p in positions if is_weather_trade(p)]

print(f"Total trades: {len(trades)}")
print(f"Weather trades: {len(weather_trades)}")
print(f"Total positions: {len(positions)}")
print(f"Weather positions: {len(weather_positions)}")
print()

# Analyze weather trades
if weather_trades:
    print("=" * 80)
    print("WEATHER TRADE ANALYSIS")
    print("=" * 80)
    print()

    # Buy vs Sell
    buy_count = sum(1 for t in weather_trades if t['side'] == 'BUY')
    sell_count = sum(1 for t in weather_trades if t['side'] == 'SELL')
    print(f"Buy trades: {buy_count}")
    print(f"Sell trades: {sell_count}")
    print(f"Buy/Sell ratio: {buy_count/sell_count if sell_count > 0 else 'N/A'}")
    print()

    # Price distribution
    prices = [t['price'] for t in weather_trades]
    print(f"Price range: ${min(prices):.4f} - ${max(prices):.4f}")
    print(f"Average price: ${sum(prices)/len(prices):.4f}")
    print()

    # Price buckets
    price_buckets = defaultdict(int)
    for price in prices:
        if price < 0.1:
            price_buckets['0.00-0.10'] += 1
        elif price < 0.2:
            price_buckets['0.10-0.20'] += 1
        elif price < 0.3:
            price_buckets['0.30-0.40'] += 1
        elif price < 0.4:
            price_buckets['0.40-0.50'] += 1
        elif price < 0.5:
            price_buckets['0.50-0.60'] += 1
        elif price < 0.6:
            price_buckets['0.60-0.70'] += 1
        elif price < 0.7:
            price_buckets['0.70-0.80'] += 1
        elif price < 0.8:
            price_buckets['0.80-0.90'] += 1
        else:
            price_buckets['0.90-1.00'] += 1

    print("Price distribution:")
    for bucket in sorted(price_buckets.keys()):
        print(f"  {bucket}: {price_buckets[bucket]} trades")
    print()

    # Outcome preferences (Yes vs No)
    yes_count = sum(1 for t in weather_trades if t.get('outcome') == 'Yes')
    no_count = sum(1 for t in weather_trades if t.get('outcome') == 'No')
    print(f"Yes outcomes: {yes_count}")
    print(f"No outcomes: {no_count}")
    print()

    # Markets traded
    markets = defaultdict(int)
    for t in weather_trades:
        markets[t['title']] += 1

    print(f"Unique markets traded: {len(markets)}")
    print("\nTop 10 markets by trade count:")
    for market, count in sorted(markets.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {count:3d} trades: {market}")
    print()

    # Position sizes (USDC)
    usdc_sizes = [t['usdcSize'] for t in weather_trades]
    print(f"Position size (USDC) range: ${min(usdc_sizes):.2f} - ${max(usdc_sizes):.2f}")
    print(f"Average position size: ${sum(usdc_sizes)/len(usdc_sizes):.2f}")
    print(f"Total volume: ${sum(usdc_sizes):.2f}")
    print()

    # Sample trades
    print("Sample weather trades (first 5):")
    for i, t in enumerate(weather_trades[:5], 1):
        dt = datetime.fromtimestamp(t['timestamp'])
        print(f"\n{i}. {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Market: {t['title']}")
        print(f"   Side: {t['side']} {t['outcome']} @ ${t['price']:.4f}")
        print(f"   Size: {t['size']:.2f} shares (${t['usdcSize']:.2f} USDC)")
    print()

# Analyze current positions
if weather_positions:
    print("=" * 80)
    print("CURRENT WEATHER POSITIONS")
    print("=" * 80)
    print()

    for i, p in enumerate(weather_positions[:10], 1):
        print(f"{i}. {p['market']}")
        print(f"   Outcome: {p['outcome']}")
        print(f"   Size: {p.get('size', 'N/A')} shares")
        print(f"   Value: ${p.get('value', 'N/A')}")
        print()

# Extract bracket types from titles
print("=" * 80)
print("BRACKET TYPE ANALYSIS")
print("=" * 80)
print()

bracket_types = defaultdict(int)
for t in weather_trades:
    title = t['title'].lower()
    if 'or higher' in title:
        bracket_types['or_higher'] += 1
    elif 'or lower' in title:
        bracket_types['or_lower'] += 1
    elif 'exactly' in title or 'exact' in title:
        bracket_types['exact'] += 1
    elif 'between' in title:
        bracket_types['between'] += 1
    else:
        bracket_types['other'] += 1

print("Bracket type distribution:")
for bracket_type, count in sorted(bracket_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {bracket_type}: {count} trades")
print()

# City analysis
print("=" * 80)
print("CITY ANALYSIS")
print("=" * 80)
print()

cities = defaultdict(int)
for t in weather_trades:
    title = t['title'].lower()
    if 'nyc' in title or 'new york' in title:
        cities['NYC'] += 1
    elif 'london' in title:
        cities['London'] += 1
    elif 'paris' in title:
        cities['Paris'] += 1
    elif 'tokyo' in title:
        cities['Tokyo'] += 1
    elif 'chicago' in title:
        cities['Chicago'] += 1
    elif 'los angeles' in title or 'la' in title:
        cities['Los Angeles'] += 1
    else:
        cities['Other'] += 1

print("City distribution:")
for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True):
    print(f"  {city}: {count} trades")
