#!/usr/bin/env python3
"""Compare sportsbook odds to Polymarket prices to find mispricings"""

import requests
import json

ODDS_API_KEY = "4f966793260d394e5fe551bd517d4957"

def american_to_prob(price):
    """Convert American odds to implied probability"""
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

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
    return resp.json()

def get_polymarket_superbowl():
    """Get Polymarket Super Bowl prices"""
    url = "https://gamma-api.polymarket.com/events?slug=super-bowl-champion-2026-731"
    resp = requests.get(url)
    data = resp.json()

    teams = {}
    if data:
        for market in data[0].get("markets", []):
            if market.get("active") and not market.get("closed"):
                title = market.get("groupItemTitle", "?")
                prices = json.loads(market.get("outcomePrices", "[0,0]"))
                teams[title] = float(prices[0])
    return teams

def main():
    print("=" * 70)
    print("SUPER BOWL 2026: SPORTSBOOK vs POLYMARKET COMPARISON")
    print("=" * 70)

    # Get Polymarket prices
    poly_prices = get_polymarket_superbowl()
    print(f"\nPolymarket active teams: {list(poly_prices.keys())}")

    # Get sportsbook odds
    sb_data = get_sportsbook_odds("americanfootball_nfl_super_bowl_winner")

    # Aggregate by team
    team_odds = {}
    for event in sb_data:
        for bookmaker in event.get("bookmakers", []):
            bm_name = bookmaker.get("title", "?")
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("name", "?")
                    price = outcome.get("price", 0)
                    prob = american_to_prob(price)

                    if team not in team_odds:
                        team_odds[team] = {"probs": [], "bookmakers": {}}
                    team_odds[team]["probs"].append(prob)
                    team_odds[team]["bookmakers"][bm_name] = prob

    # Map team names (sportsbook uses full names, Polymarket uses city)
    name_map = {
        "Denver Broncos": "Denver",
        "Los Angeles Rams": "Los Angeles R",
        "New England Patriots": "New England",
        "Seattle Seahawks": "Seattle"
    }

    print("\n" + "-" * 70)
    print(f"{'Team':<25} {'Sportsbook':<12} {'Polymarket':<12} {'DIFF':<10} {'Signal'}")
    print("-" * 70)

    for full_name, poly_name in name_map.items():
        if full_name in team_odds and poly_name in poly_prices:
            sb_avg = sum(team_odds[full_name]["probs"]) / len(team_odds[full_name]["probs"])
            poly = poly_prices[poly_name]
            diff = poly - sb_avg

            # Signal: if Polymarket is lower than sportsbook, it's underpriced (buy)
            if diff < -0.03:
                signal = "BUY (underpriced)"
            elif diff > 0.03:
                signal = "SELL (overpriced)"
            else:
                signal = "Fair"

            print(f"{full_name:<25} {sb_avg*100:>10.1f}% {poly*100:>10.1f}% {diff*100:>+8.1f}% {signal}")

    print("-" * 70)
    print("\nSportsbooks included:")
    if sb_data:
        for bm in sb_data[0].get("bookmakers", [])[:5]:
            print(f"  - {bm.get('title')}")

    # Also check La Liga if available
    print("\n" + "=" * 70)
    print("LA LIGA UPCOMING GAMES")
    print("=" * 70)

    la_liga = get_sportsbook_odds("soccer_spain_la_liga")
    for event in la_liga[:5]:
        home = event.get("home_team", "?")
        away = event.get("away_team", "?")
        time = event.get("commence_time", "?")
        print(f"\n{home} vs {away} ({time[:10]})")

        for bm in event.get("bookmakers", [])[:2]:
            print(f"  {bm.get('title')}:")
            for market in bm.get("markets", []):
                if market.get("key") == "h2h":
                    for o in market.get("outcomes", []):
                        name = o.get("name")
                        price = o.get("price")
                        prob = american_to_prob(price)
                        print(f"    {name}: {price:+d} ({prob*100:.1f}%)")

if __name__ == "__main__":
    main()
