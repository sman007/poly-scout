#!/usr/bin/env python3
"""Debug market structure"""

import requests
import json

def get_markets(limit=5):
    url = f"https://gamma-api.polymarket.com/markets?closed=false&limit={limit}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

markets = get_markets()
print(json.dumps(markets[0] if markets else {}, indent=2))
