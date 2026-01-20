#!/usr/bin/env python3
"""Compare NFC/AFC championship odds: Polymarket vs Sportsbooks"""

import requests
import json

ODDS_API_KEY = "4f966793260d394e5fe551bd517d4957"

def american_to_prob(price):
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

def get_polymarket_prices(slug):
    """Get current Polymarket prices for an event"""
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    resp = requests.get(url)
    data = resp.json()

    prices = {}
    if data:
        for market in data[0].get("markets", []):
            if market.get("active") and not market.get("closed"):
                title = market.get("groupItemTitle", market.get("question", "?"))
                outcome_prices = json.loads(market.get("outcomePrices", "[0,0]"))
                prices[title] = float(outcome_prices[0])
    return prices

def get_sportsbook_odds(sport_key):
    """Get odds from The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "outrights,h2h",
        "oddsFormat": "american"
    }
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        return resp.json()
    return []

def main():
    print("=" * 80)
    print("NFC/AFC CHAMPIONSHIP: POLYMARKET vs SPORTSBOOKS")
    print("=" * 80)

    # NFC Championship - Jan 26
    print("\n--- NFC CHAMPIONSHIP (Jan 26) ---")
    nfc_poly = get_polymarket_prices("nfc-champion-1")
    print(f"Polymarket: {nfc_poly}")

    # Check if sum < 100%
    nfc_sum = sum(nfc_poly.values())
    print(f"NFC Sum: {nfc_sum:.1%} (edge: {(1-nfc_sum)*100:.1f}%)")

    # AFC Championship - Jan 26
    print("\n--- AFC CHAMPIONSHIP (Jan 26) ---")
    afc_poly = get_polymarket_prices("afc-champion-1")
    print(f"Polymarket: {afc_poly}")

    afc_sum = sum(afc_poly.values())
    print(f"AFC Sum: {afc_sum:.1%} (edge: {(1-afc_sum)*100:.1f}%)")

    # Get sportsbook odds for conference championships
    print("\n--- SPORTSBOOK ODDS ---")

    # Try to find conference championship odds
    # The key might be different - let me search
    sports = requests.get(f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}").json()

    nfl_sports = [s for s in sports if "nfl" in s.get("key", "").lower() or "football" in s.get("title", "").lower()]
    print(f"\nNFL-related sports keys: {[s.get('key') for s in nfl_sports]}")

    # Try NFL championship markets
    for sport in nfl_sports:
        key = sport.get("key")
        title = sport.get("title")
        print(f"\n{title} ({key}):")

        odds = get_sportsbook_odds(key)
        if odds:
            for event in odds[:5]:
                home = event.get("home_team", "")
                away = event.get("away_team", "")
                time = event.get("commence_time", "")[:16]

                print(f"  {away} @ {home} ({time})")

                for bm in event.get("bookmakers", [])[:2]:
                    bm_name = bm.get("title")
                    for market in bm.get("markets", []):
                        mkt_key = market.get("key")
                        if mkt_key in ["h2h", "outrights"]:
                            print(f"    {bm_name}:")
                            for o in market.get("outcomes", []):
                                name = o.get("name")
                                price = o.get("price")
                                prob = american_to_prob(price)
                                print(f"      {name}: {price:+d} ({prob:.1%})")
        else:
            print("  No odds available")

    # College Football Championship
    print("\n" + "=" * 80)
    print("COLLEGE FOOTBALL CHAMPIONSHIP (Jan 20)")
    print("=" * 80)

    cfb_poly = get_polymarket_prices("college-football-champion-2026-684")
    print(f"\nPolymarket: {cfb_poly}")
    cfb_sum = sum(cfb_poly.values())
    print(f"Sum: {cfb_sum:.1%} (edge: {(1-cfb_sum)*100:.1f}%)")

    # Try to get CFB championship odds
    cfb_odds = get_sportsbook_odds("americanfootball_ncaaf_championship_winner")
    if cfb_odds:
        print("\nSportsbook (NCAAF Championship):")
        for event in cfb_odds[:3]:
            for bm in event.get("bookmakers", [])[:3]:
                print(f"  {bm.get('title')}:")
                for market in bm.get("markets", []):
                    for o in market.get("outcomes", []):
                        name = o.get("name")
                        price = o.get("price")
                        prob = american_to_prob(price)
                        print(f"    {name}: {price:+d} ({prob:.1%})")

    # Summary
    print("\n" + "=" * 80)
    print("SPREAD CAPTURE OPPORTUNITIES")
    print("=" * 80)

    opportunities = []

    if nfc_sum < 0.99:
        opportunities.append(f"NFC Championship: {nfc_sum:.1%} sum = {(1-nfc_sum)*100:.1f}% edge")

    if afc_sum < 0.99:
        opportunities.append(f"AFC Championship: {afc_sum:.1%} sum = {(1-afc_sum)*100:.1f}% edge")

    if cfb_sum < 0.99:
        opportunities.append(f"CFB Championship: {cfb_sum:.1%} sum = {(1-cfb_sum)*100:.1f}% edge")

    if opportunities:
        print("\nFOUND:")
        for opp in opportunities:
            print(f"  - {opp}")
    else:
        print("\nNo spread capture opportunities (all sums >= 99%)")
        print("BUT sportsbook-signal strategy may still work if prices differ!")

if __name__ == "__main__":
    main()
