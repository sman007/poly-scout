#!/usr/bin/env python3
"""Find upcoming games on sportsbooks and match to Polymarket"""

import requests
import json
from datetime import datetime

ODDS_API_KEY = "4f966793260d394e5fe551bd517d4957"

def american_to_prob(price):
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

def main():
    # Get upcoming games from key leagues
    leagues = [
        ("soccer_epl", "EPL"),
        ("soccer_spain_la_liga", "La Liga"),
        ("soccer_france_ligue_one", "Ligue 1"),
        ("soccer_germany_bundesliga", "Bundesliga"),
        ("soccer_italy_serie_a", "Serie A"),
        ("basketball_nba", "NBA"),
    ]

    print("=" * 70)
    print("UPCOMING GAMES FROM SPORTSBOOKS")
    print("=" * 70)

    all_games = []

    for key, name in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{key}/odds"
        params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
        resp = requests.get(url, params=params)

        if resp.status_code == 200:
            games = resp.json()
            if games:
                print(f"\n{name} ({len(games)} games):")
                for g in games[:5]:
                    home = g.get("home_team", "?")
                    away = g.get("away_team", "?")
                    time = g.get("commence_time", "")[:16].replace("T", " ")

                    probs = {}
                    for bm in g.get("bookmakers", [])[:1]:
                        for mkt in bm.get("markets", []):
                            if mkt.get("key") == "h2h":
                                for o in mkt.get("outcomes", []):
                                    probs[o.get("name")] = american_to_prob(o.get("price", 0))

                    print(f"  {away} @ {home} ({time})")
                    for team, prob in probs.items():
                        print(f"    {team}: {prob:.1%}")

                    all_games.append({"home": home, "away": away, "league": name, "time": time, "probs": probs})

    # Get all Polymarket events
    print("\n" + "=" * 70)
    print("SEARCHING POLYMARKET FOR MATCHING MARKETS")
    print("=" * 70)

    pm_resp = requests.get("https://gamma-api.polymarket.com/events?active=true&closed=false&limit=500")
    pm_events = pm_resp.json()

    # Also search with tags
    for tag in ["sports", "soccer", "nba", "nfl", "football"]:
        try:
            tag_resp = requests.get(f"https://gamma-api.polymarket.com/events?tag={tag}&active=true&closed=false&limit=100")
            for e in tag_resp.json():
                if e.get("slug") not in [x.get("slug") for x in pm_events]:
                    pm_events.append(e)
        except:
            pass

    print(f"\nTotal Polymarket events to search: {len(pm_events)}")

    # Search for matches
    found_any = False
    for game in all_games[:20]:
        home = game["home"]
        away = game["away"]
        home_words = [w.lower() for w in home.split() if len(w) > 3]
        away_words = [w.lower() for w in away.split() if len(w) > 3]

        for event in pm_events:
            title = event.get("title", "").lower()
            slug = event.get("slug", "").lower()

            home_match = any(w in title or w in slug for w in home_words)
            away_match = any(w in title or w in slug for w in away_words)

            if home_match and away_match:
                markets = event.get("markets", [])
                active = [m for m in markets if m.get("active") and not m.get("closed")]

                if active:
                    found_any = True
                    print(f"\nFOUND MATCH: {away} @ {home} ({game['league']})")
                    print(f"  Polymarket: {event.get('title')}")
                    print(f"  Slug: {event.get('slug')}")
                    print(f"  Sportsbook odds:")
                    for team, prob in game["probs"].items():
                        print(f"    {team}: {prob:.1%}")

                    print(f"  Polymarket markets:")
                    pm_sum = 0
                    for m in active[:5]:
                        name = m.get("groupItemTitle") or m.get("question", "?")[:30]
                        prices = json.loads(m.get("outcomePrices", "[0,0]"))
                        yes = float(prices[0]) if prices else 0
                        pm_sum += yes
                        print(f"    {name}: {yes:.1%}")

                    if len(active) > 1:
                        print(f"  Sum: {pm_sum:.1%}")

    if not found_any:
        print("\nNo matching game markets found on Polymarket")
        print("\nLet me check if there are ANY game markets with dates in slug...")

        # Look for date patterns
        for event in pm_events:
            slug = event.get("slug", "")
            if any(d in slug for d in ["2026-01-19", "2026-01-20", "2026-01-21"]):
                print(f"  {slug}: {event.get('title')}")

if __name__ == "__main__":
    main()
