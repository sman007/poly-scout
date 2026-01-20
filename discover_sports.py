#!/usr/bin/env python3
"""Discover all sports markets on Polymarket and compare to sportsbooks"""

import requests
import json

ODDS_API_KEY = "4f966793260d394e5fe551bd517d4957"

def get_polymarket_sports():
    """Get all sports events from Polymarket"""
    tags = ["sports", "nfl", "nba", "soccer", "football", "basketball", "hockey", "baseball", "mma", "ufc", "tennis", "la-liga", "premier-league", "champions-league"]
    all_events = {}

    for tag in tags:
        try:
            url = f"https://gamma-api.polymarket.com/events?tag={tag}&active=true&closed=false&limit=100"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                events = resp.json()
                for e in events:
                    slug = e.get("slug", "")
                    if slug not in all_events:
                        all_events[slug] = e
        except Exception as ex:
            pass

    return all_events

def get_odds_api_sports():
    """Get list of available sports from The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}"
    resp = requests.get(url)
    return resp.json()

def get_upcoming_games(sport_key):
    """Get upcoming games for a sport"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american"
    }
    resp = requests.get(url, params=params)
    if resp.status_code == 200:
        return resp.json()
    return []

def american_to_prob(price):
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

def main():
    print("=" * 80)
    print("POLYMARKET SPORTS MARKET DISCOVERY")
    print("=" * 80)

    # Get Polymarket events
    pm_events = get_polymarket_sports()
    print(f"\nFound {len(pm_events)} Polymarket sports events\n")

    # Categorize
    individual_games = []
    futures = []

    for slug, event in pm_events.items():
        title = event.get("title", "")
        markets = event.get("markets", [])
        end_date = event.get("endDate", "")[:10] if event.get("endDate") else "?"

        active_markets = [m for m in markets if m.get("active") and not m.get("closed")]

        # Check for individual game patterns
        is_game = any(x in title.lower() for x in [" vs ", " v ", "winner of", "match", "game"])

        info = {
            "slug": slug,
            "title": title,
            "num_markets": len(active_markets),
            "end": end_date,
            "markets": active_markets
        }

        if is_game or len(active_markets) <= 3:
            individual_games.append(info)
        else:
            futures.append(info)

    # Print individual games
    print("-" * 80)
    print("INDIVIDUAL GAME MARKETS (like beachboy4 trades)")
    print("-" * 80)

    if individual_games:
        for g in sorted(individual_games, key=lambda x: x["end"])[:25]:
            print(f"\n{g['title']}")
            print(f"  Slug: {g['slug']}")
            print(f"  Markets: {g['num_markets']}, Ends: {g['end']}")
            for m in g["markets"][:5]:
                name = m.get("groupItemTitle") or m.get("question", "?")[:40]
                prices = json.loads(m.get("outcomePrices", "[0,0]"))
                yes_price = float(prices[0]) if prices else 0
                print(f"    - {name}: YES @ {yes_price:.2%}")
    else:
        print("\nNO INDIVIDUAL GAME MARKETS FOUND")

    # Print futures
    print("\n" + "-" * 80)
    print("FUTURES/SEASON MARKETS")
    print("-" * 80)

    for f in sorted(futures, key=lambda x: -f["num_markets"])[:10]:
        print(f"\n{f['title']}")
        print(f"  {f['num_markets']} markets, ends {f['end']}")

    # Now check The Odds API for upcoming games
    print("\n" + "=" * 80)
    print("SPORTSBOOK UPCOMING GAMES (The Odds API)")
    print("=" * 80)

    sports = get_odds_api_sports()
    active_sports = [s for s in sports if s.get("active")]

    print(f"\n{len(active_sports)} sports with active games:\n")

    for sport in active_sports[:15]:
        key = sport.get("key")
        title = sport.get("title")
        print(f"\n--- {title} ({key}) ---")

        games = get_upcoming_games(key)
        if games:
            for game in games[:3]:
                home = game.get("home_team", "?")
                away = game.get("away_team", "?")
                time = game.get("commence_time", "?")[:16].replace("T", " ")

                # Get best odds
                best_home = best_away = best_draw = None
                for bm in game.get("bookmakers", []):
                    for mkt in bm.get("markets", []):
                        if mkt.get("key") == "h2h":
                            for o in mkt.get("outcomes", []):
                                name = o.get("name")
                                prob = american_to_prob(o.get("price", 0))
                                if name == home:
                                    if not best_home or prob > best_home:
                                        best_home = prob
                                elif name == away:
                                    if not best_away or prob > best_away:
                                        best_away = prob
                                elif name == "Draw":
                                    if not best_draw or prob > best_draw:
                                        best_draw = prob

                print(f"  {away} @ {home} ({time})")
                if best_home and best_away:
                    total = (best_home or 0) + (best_away or 0) + (best_draw or 0)
                    print(f"    Home: {best_home:.1%}, Away: {best_away:.1%}", end="")
                    if best_draw:
                        print(f", Draw: {best_draw:.1%}", end="")
                    print(f" (sum: {total:.1%})")
        else:
            print("  No upcoming games")

    # Cross-reference: find Polymarket markets that match sportsbook games
    print("\n" + "=" * 80)
    print("CROSS-REFERENCE: Markets on BOTH platforms")
    print("=" * 80)

    pm_titles = [e.get("title", "").lower() for e in pm_events.values()]

    found_matches = []
    for sport in active_sports:
        games = get_upcoming_games(sport.get("key"))
        for game in games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")

            # Check if this game exists on Polymarket
            for slug, event in pm_events.items():
                title = event.get("title", "").lower()
                if (home.lower() in title or away.lower() in title) or \
                   (home.split()[-1].lower() in title and away.split()[-1].lower() in title):
                    found_matches.append({
                        "pm_title": event.get("title"),
                        "pm_slug": slug,
                        "sb_game": f"{away} @ {home}",
                        "sb_sport": sport.get("title")
                    })

    if found_matches:
        print("\nFOUND TRADEABLE MATCHES:")
        for m in found_matches:
            print(f"\n  Polymarket: {m['pm_title']}")
            print(f"  Sportsbook: {m['sb_game']} ({m['sb_sport']})")
    else:
        print("\nNo exact matches found between Polymarket and upcoming sportsbook games")
        print("This means no individual game markets are currently active on Polymarket")

if __name__ == "__main__":
    main()
