#!/usr/bin/env python3
"""Find all Polymarket game markets by trying slug patterns"""

import requests
import json

ODDS_API_KEY = "4f966793260d394e5fe551bd517d4957"

def american_to_prob(price):
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)

def try_slug(slug):
    """Try to fetch a Polymarket event by slug"""
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    resp = requests.get(url, timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        if data and len(data) > 0:
            return data[0]
    return None

def main():
    print("=" * 80)
    print("FINDING POLYMARKET GAME MARKETS BY SLUG")
    print("=" * 80)

    # Try known slugs from web search
    known_slugs = [
        "nba-phx-bkn-2026-01-19",  # Suns vs Nets (we found this)
        "nba-mil-atl-2026-01-19",  # Bucks vs Hawks
        "nba-okc-cle-2026-01-19",  # Thunder vs Cavs
        "nba-lac-wsh-2026-01-19",  # Clippers vs Wizards
        "nba-dal-nyk-2026-01-19",  # Mavs vs Knicks
        "nba-uta-sas-2026-01-19",  # Jazz vs Spurs
    ]

    print("\n--- NBA Games ---")
    found_games = []

    for slug in known_slugs:
        event = try_slug(slug)
        if event:
            title = event.get("title", "?")
            volume = event.get("volume", 0)
            end = event.get("endDate", "")[:16]
            closed = event.get("closed", False)

            print(f"\nFOUND: {slug}")
            print(f"  Title: {title}")
            print(f"  Volume: ${volume:,.0f}")
            print(f"  Ends: {end}")
            print(f"  Closed: {closed}")

            # Get market prices
            markets = event.get("markets", [])
            active = [m for m in markets if m.get("active") and not m.get("closed")]

            # Find win markets (not props)
            for m in active:
                q = m.get("question", "")
                if "win" in q.lower() and "o/u" not in q.lower():
                    prices = json.loads(m.get("outcomePrices", "[0,0]"))
                    yes = float(prices[0]) if prices else 0
                    name = m.get("groupItemTitle") or q[:30]
                    print(f"    {name}: {yes:.1%}")

            found_games.append({
                "slug": slug,
                "title": title,
                "volume": volume
            })
        else:
            print(f"NOT FOUND: {slug}")

    # Try La Liga slugs
    print("\n--- La Liga Games ---")
    la_liga_slugs = [
        "lal-sev-elc-2026-01-19",
        "lal-elc-sev-2026-01-19",
        "laliga-sev-elc-2026-01-19",
    ]

    for slug in la_liga_slugs:
        event = try_slug(slug)
        if event:
            print(f"FOUND: {slug} - {event.get('title')}")
            found_games.append({"slug": slug, "title": event.get("title")})

    # Try EPL slugs
    print("\n--- EPL Games ---")
    epl_slugs = [
        "epl-bou-bha-2026-01-19",
        "epl-bha-bou-2026-01-19",
    ]

    for slug in epl_slugs:
        event = try_slug(slug)
        if event:
            print(f"FOUND: {slug} - {event.get('title')}")
            found_games.append({"slug": slug, "title": event.get("title")})

    # Summary
    print("\n" + "=" * 80)
    print(f"TOTAL FOUND: {len(found_games)} game markets")
    print("=" * 80)

    # Now compare to sportsbooks for found games
    if found_games:
        print("\n--- SPORTSBOOK COMPARISON ---")

        # Get NBA odds
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey={ODDS_API_KEY}&regions=us&markets=h2h&oddsFormat=american"
        resp = requests.get(url)
        if resp.status_code == 200:
            nba_games = resp.json()

            for pm in found_games:
                if "nba-" in pm["slug"]:
                    pm_title = pm["title"].lower()

                    for sb in nba_games:
                        home = sb.get("home_team", "")
                        away = sb.get("away_team", "")

                        # Try to match
                        if (home.split()[-1].lower() in pm_title or
                            away.split()[-1].lower() in pm_title):

                            # Get sportsbook odds
                            probs = {}
                            for bm in sb.get("bookmakers", []):
                                for mkt in bm.get("markets", []):
                                    if mkt.get("key") == "h2h":
                                        for o in mkt.get("outcomes", []):
                                            t = o.get("name")
                                            p = american_to_prob(o.get("price", 0))
                                            if t not in probs:
                                                probs[t] = []
                                            probs[t].append(p)

                            print(f"\n{pm['title']} vs Sportsbooks:")
                            for team, odds in probs.items():
                                avg = sum(odds) / len(odds)
                                print(f"  {team}: SB {avg:.1%}")

if __name__ == "__main__":
    main()
