#!/usr/bin/env python3
"""
Final Strategy Analysis: DiviLungaoBBW
ACTUAL STRATEGY: Sports Spread Betting (NHL/NBA/NCAA)
"""

import json
from collections import defaultdict, Counter
from datetime import datetime

def log(msg):
    print(f"[FINAL] {msg}", flush=True)

def load_trades():
    with open('C:/Projects/poly-scout/output/divi_trades.json', 'r') as f:
        return json.load(f)

def categorize_sport(title):
    """Categorize sport from title."""
    title_lower = title.lower()

    # NHL teams
    nhl_teams = ['rangers', 'islanders', 'devils', 'flyers', 'penguins', 'capitals',
                 'hurricanes', 'blue jackets', 'bruins', 'sabres', 'red wings', 'panthers',
                 'lightning', 'canadiens', 'senators', 'maple leafs', 'jets', 'blues',
                 'blackhawks', 'avalanche', 'stars', 'wild', 'predators', 'ducks', 'flames',
                 'oilers', 'canucks', 'golden knights', 'kings', 'sharks', 'kraken', 'coyotes']

    # NBA teams
    nba_teams = ['knicks', '76ers', 'sixers', 'nets', 'celtics', 'raptors', 'bulls',
                 'cavaliers', 'pistons', 'pacers', 'bucks', 'hawks', 'hornets', 'heat',
                 'magic', 'wizards', 'nuggets', 'timberwolves', 'thunder', 'trail blazers',
                 'jazz', 'warriors', 'clippers', 'lakers', 'suns', 'kings', 'mavericks',
                 'rockets', 'grizzlies', 'pelicans', 'spurs']

    # NCAA keywords
    ncaa_keywords = ['bulldogs', 'wildcats', 'raiders', 'terrapins', 'maryland', 'owls',
                     'kennesaw', 'bethune-cookman', 'wright state', 'florida gators']

    for team in nhl_teams:
        if team in title_lower:
            return 'NHL'

    for team in nba_teams:
        if team in title_lower:
            return 'NBA'

    for keyword in ncaa_keywords:
        if keyword in title_lower:
            return 'NCAA'

    if 'ufc' in title_lower:
        return 'UFC'

    if 'nfl' in title_lower or 'super bowl' in title_lower:
        return 'NFL'

    if 'crypto' in title_lower or 'bitcoin' in title_lower or 'btc' in title_lower:
        return 'Crypto'

    return 'Other'

def is_spread_bet(title):
    """Check if it's a spread bet."""
    title_lower = title.lower()
    return 'spread:' in title_lower or '(-' in title or '(+' in title

def is_over_under(outcome):
    """Check if outcome is Over/Under."""
    return outcome in ['Over', 'Under']

def main():
    log("="*70)
    log("FINAL STRATEGY: DIVILUNGAOBBW SPORTS_ARB")
    log("="*70)

    trades = load_trades()

    # Categorize all trades
    categorized = []
    for t in trades:
        sport = categorize_sport(t.get('title', ''))
        spread = is_spread_bet(t.get('title', ''))
        ou = is_over_under(t.get('outcome', ''))

        categorized.append({
            'trade': t,
            'sport': sport,
            'spread': spread,
            'over_under': ou
        })

    # Sport breakdown
    log(f"\n" + "="*70)
    log("SPORT BREAKDOWN")
    log("="*70)

    sport_counts = Counter(c['sport'] for c in categorized)
    for sport, count in sport_counts.most_common():
        pct = count / len(trades) * 100
        log(f"  {sport}: {count} trades ({pct:.1f}%)")

    # Spread vs Straight Up
    spread_count = len([c for c in categorized if c['spread']])
    log(f"\nSpread bets: {spread_count} ({spread_count/len(trades)*100:.1f}%)")
    log(f"Straight up: {len(trades) - spread_count} ({(len(trades) - spread_count)/len(trades)*100:.1f}%)")

    # Over/Under
    ou_count = len([c for c in categorized if c['over_under']])
    log(f"Over/Under: {ou_count} ({ou_count/len(trades)*100:.1f}%)")

    # ACTUAL STRATEGY EXTRACTION
    log(f"\n" + "="*70)
    log("ACTUAL STRATEGY REVEALED")
    log("="*70)

    log(f"\nMARKET FOCUS:")
    log(f"  - NHL: {sport_counts['NHL']} trades ({sport_counts['NHL']/len(trades)*100:.1f}%)")
    log(f"  - NBA: {sport_counts['NBA']} trades ({sport_counts['NBA']/len(trades)*100:.1f}%)")
    log(f"  - NCAA Basketball: {sport_counts['NCAA']} trades ({sport_counts['NCAA']/len(trades)*100:.1f}%)")
    log(f"  - Total SPORTS: {sport_counts['NHL'] + sport_counts['NBA'] + sport_counts['NCAA'] + sport_counts['UFC'] + sport_counts.get('NFL', 0)} trades")

    # Analyze NHL trades
    nhl_trades = [c['trade'] for c in categorized if c['sport'] == 'NHL']
    if nhl_trades:
        log(f"\n" + "-"*70)
        log(f"NHL STRATEGY ({len(nhl_trades)} trades)")
        log("-"*70)

        # Most common teams
        outcomes = Counter(t.get('outcome') for t in nhl_trades)
        log(f"\nMost bet teams:")
        for team, count in outcomes.most_common(5):
            log(f"  {team}: {count} bets")

        # Price analysis
        prices = [t.get('price') for t in nhl_trades]
        log(f"\nNHL Price stats:")
        log(f"  Avg: ${sum(prices)/len(prices):.4f}")
        log(f"  Range: ${min(prices):.4f} - ${max(prices):.4f}")

    # Analyze NBA trades
    nba_trades = [c['trade'] for c in categorized if c['sport'] == 'NBA']
    if nba_trades:
        log(f"\n" + "-"*70)
        log(f"NBA STRATEGY ({len(nba_trades)} trades)")
        log("-"*70)

        outcomes = Counter(t.get('outcome') for t in nba_trades)
        log(f"\nMost bet teams/outcomes:")
        for team, count in outcomes.most_common(5):
            log(f"  {team}: {count} bets")

    # FINAL BLUEPRINT
    log(f"\n" + "="*70)
    log("REPLICATION BLUEPRINT - $2000 CAPITAL")
    log("="*70)

    # Calculate metrics
    prices = [t.get('price') for t in trades]
    sizes = [t.get('usdcSize') for t in trades]

    log(f"\nSTRATEGY TYPE: Sports Directional + Spread Betting")
    log(f"\nMARKET SELECTION:")
    log(f"  1. NHL games (26.6% of portfolio)")
    log(f"  2. NBA games (21.6% of portfolio)")
    log(f"  3. NCAA Basketball (12.4% of portfolio)")
    log(f"  4. Focus on spread bets and over/under")

    log(f"\nENTRY RULES:")
    log(f"  - Price sweet spot: $0.45 - $0.50 (near coin flip)")
    log(f"  - Avg entry price: ${sum(prices)/len(prices):.4f}")
    log(f"  - ONLY BUY (96.2% of trades)")
    log(f"  - Rarely SELL")

    log(f"\nPOSITION SIZING:")
    median_size = sorted(sizes)[len(sizes)//2]
    log(f"  - Median position: ${median_size:.2f}")
    log(f"  - For $2000 capital: $20-100 per bet (1-5%)")
    log(f"  - Scale positions: Multiple entries on same game")

    log(f"\nTIMING:")
    log(f"  - Primary: Saturday (89.4% of trades)")
    log(f"  - Time: 4-6 AM UTC (likely night before games)")
    log(f"  - This suggests betting on Saturday NHL/NBA games")

    log(f"\nRISK MANAGEMENT:")
    log(f"  - Diversify across multiple games")
    log(f"  - Average 15.2 trades per market (scaling)")
    log(f"  - Never all-in on single game")

    log(f"\nEXPECTED EDGE:")
    log(f"  - Likely has statistical/research edge on:")
    log(f"    * NHL: Rangers, Kings, Stars")
    log(f"    * NBA: 76ers")
    log(f"    * NCAA: Butler, Wright State, Bethune-Cookman")
    log(f"  - May be exploiting line value vs bookmakers")
    log(f"  - Needs >50% win rate at avg $0.50 price to profit")

    log(f"\nSTEP-BY-STEP FOR $2000:")
    log(f"  1. Every Saturday, scan Polymarket for:")
    log(f"     - NHL spread bets")
    log(f"     - NBA spread bets")
    log(f"     - NCAA Basketball spreads")
    log(f"  2. Find lines priced $0.45-0.50")
    log(f"  3. Use sports research/stats to find value")
    log(f"  4. BUY YES on favored outcome")
    log(f"  5. Position size: $20-100 per game")
    log(f"  6. Can add to position if price improves")
    log(f"  7. Hold until game ends")
    log(f"  8. Repeat weekly")

    log(f"\nKEY INSIGHT:")
    log(f"  This is NOT arbitrage! It's DIRECTIONAL sports betting")
    log(f"  with likely statistical edge from sports research.")
    log(f"  Success requires:")
    log(f"  - Sports knowledge (NHL/NBA/NCAA)")
    log(f"  - Statistical analysis")
    log(f"  - Line shopping for value")
    log(f"  - Discipline to only bet value spots")

    log("\n" + "="*70)
    log("ANALYSIS COMPLETE")
    log("="*70)

if __name__ == "__main__":
    main()
