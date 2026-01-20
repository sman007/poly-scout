#!/usr/bin/env python3
"""Compare today's sports games: Polymarket vs Sportsbooks"""

import requests
import json
from datetime import datetime, timedelta

ODDS_API_KEY = "4f966793260d394e5fe551bd517d4957"

def american_to_prob(price):
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

def get_polymarket_games():
    """Get all sports games from Polymarket for today/tomorrow"""
    games = []

    # Search for games by league prefix
    prefixes = ["nba-", "lal-", "epl-", "ser-", "bun-", "fl1-"]
    dates = ["2026-01-19", "2026-01-20", "2026-01-21"]

    for prefix in prefixes:
        for date in dates:
            slug = f"{prefix}*-{date}"
            # Try specific slugs we know exist
            pass

    # Better approach: search gamma API with filters
    # Get events ending soon
    url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=500"
    resp = requests.get(url)
    events = resp.json()

    for e in events:
        slug = e.get("slug", "")
        # Check if it's a game market (has date pattern and league prefix)
        is_game = any(p in slug for p in ["nba-", "lal-", "epl-", "ser-", "bun-", "fl1-", "nhl-", "ucl-"])
        is_game = is_game and any(d in slug for d in dates)

        if is_game:
            markets = e.get("markets", [])
            active = [m for m in markets if m.get("active") and not m.get("closed")]

            # Get win probabilities (filter out props)
            win_markets = []
            for m in active:
                q = m.get("question", "").lower()
                # Skip props like "Points O/U"
                if "o/u" not in q and "over" not in q and "under" not in q:
                    prices = json.loads(m.get("outcomePrices", "[0,0]"))
                    win_markets.append({
                        "name": m.get("groupItemTitle") or m.get("question", "?")[:30],
                        "yes": float(prices[0]) if prices else 0
                    })

            if win_markets:
                games.append({
                    "slug": slug,
                    "title": e.get("title"),
                    "end": e.get("endDate", "")[:16],
                    "markets": win_markets
                })

    return games

def get_sportsbook_games(sport_key):
    """Get games from The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        return resp.json()
    return []

def main():
    print("=" * 80)
    print("TODAY'S GAMES: POLYMARKET vs SPORTSBOOKS")
    print("=" * 80)

    # Get Polymarket games
    pm_games = get_polymarket_games()
    print(f"\nPolymarket games found: {len(pm_games)}")

    for g in pm_games:
        print(f"\n{g['title']} ({g['slug']})")
        print(f"  Ends: {g['end']}")
        total = 0
        for m in g['markets'][:5]:
            print(f"  - {m['name']}: {m['yes']:.1%}")
            total += m['yes']
        if len(g['markets']) > 1:
            print(f"  SUM: {total:.1%}")

    # Get sportsbook odds for comparison
    print("\n" + "=" * 80)
    print("SPORTSBOOK COMPARISON")
    print("=" * 80)

    leagues = [
        ("basketball_nba", "NBA"),
        ("soccer_spain_la_liga", "La Liga"),
        ("soccer_epl", "EPL"),
        ("soccer_germany_bundesliga", "Bundesliga"),
        ("soccer_italy_serie_a", "Serie A"),
    ]

    for key, name in leagues:
        sb_games = get_sportsbook_games(key)
        if sb_games:
            print(f"\n--- {name} ---")
            for g in sb_games[:5]:
                home = g.get("home_team", "?")
                away = g.get("away_team", "?")
                time = g.get("commence_time", "")[:16].replace("T", " ")

                # Get average odds
                probs = {}
                count = 0
                for bm in g.get("bookmakers", []):
                    for mkt in bm.get("markets", []):
                        if mkt.get("key") == "h2h":
                            for o in mkt.get("outcomes", []):
                                name_t = o.get("name")
                                prob = american_to_prob(o.get("price", 0))
                                if name_t not in probs:
                                    probs[name_t] = []
                                probs[name_t].append(prob)
                            count += 1

                print(f"\n  {away} @ {home} ({time})")
                for team, odds_list in probs.items():
                    avg = sum(odds_list) / len(odds_list)
                    print(f"    {team}: {avg:.1%} (avg of {len(odds_list)} books)")

                # Try to find matching Polymarket game
                for pm in pm_games:
                    # Match by team names
                    pm_title = pm['title'].lower()
                    if (home.split()[-1].lower() in pm_title or
                        away.split()[-1].lower() in pm_title):
                        print(f"    --> Polymarket match: {pm['slug']}")
                        for m in pm['markets'][:3]:
                            pm_prob = m['yes']
                            # Find matching sportsbook team
                            for team, odds_list in probs.items():
                                if m['name'].lower() in team.lower() or team.split()[-1].lower() in m['name'].lower():
                                    sb_avg = sum(odds_list) / len(odds_list)
                                    diff = pm_prob - sb_avg
                                    signal = "BUY" if diff < -0.03 else "SELL" if diff > 0.03 else "Fair"
                                    print(f"        {m['name']}: PM {pm_prob:.1%} vs SB {sb_avg:.1%} = {diff*100:+.1f}% [{signal}]")

if __name__ == "__main__":
    main()
