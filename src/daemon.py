"""
Auto-pilot daemon for poly-scout.
Detects explosive growth patterns in Polymarket wallets.
Finds emerging alpha traders BEFORE they become famous.
Only alerts after reverse-engineering the strategy.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from collections import Counter

os.environ['PYTHONUNBUFFERED'] = '1'

import httpx
from dotenv import load_dotenv

from src.scanner import WalletScanner, WalletProfile

load_dotenv()


def log(msg: str):
    print(msg, flush=True)


# Configuration
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Velocity thresholds
MIN_VELOCITY = float(os.getenv("MIN_VELOCITY", "300"))  # $/day
MAX_ACCOUNT_AGE_DAYS = int(os.getenv("MAX_ACCOUNT_AGE_DAYS", "30"))
MIN_TRADES_WEEK = int(os.getenv("MIN_TRADES_WEEK", "30"))
MIN_LEADERBOARD_PROFIT = float(os.getenv("MIN_LEADERBOARD_PROFIT", "1000"))

SEEN_WALLETS_FILE = Path("/root/poly-scout/data/seen_wallets.json")

# Strategy classifications
STRATEGY_CRYPTO_ARB = "CRYPTO_ARB"
STRATEGY_SPORTS = "SPORTS"
STRATEGY_POLITICAL = "POLITICAL"
STRATEGY_MARKET_MAKER = "MARKET_MAKER"
STRATEGY_MIXED = "MIXED"
STRATEGY_UNKNOWN = "UNKNOWN"

# Only alert on these strategies (replicable/interesting)
ALERT_STRATEGIES = {STRATEGY_CRYPTO_ARB, STRATEGY_MARKET_MAKER}

STRATEGY_EMOJI = {
    STRATEGY_CRYPTO_ARB: "🤖",
    STRATEGY_SPORTS: "🏈",
    STRATEGY_POLITICAL: "🏛️",
    STRATEGY_MARKET_MAKER: "📊",
    STRATEGY_MIXED: "🎲",
    STRATEGY_UNKNOWN: "❓",
}


def load_seen_wallets() -> set:
    if SEEN_WALLETS_FILE.exists():
        try:
            with open(SEEN_WALLETS_FILE) as f:
                return set(json.load(f))
        except:
            pass
    return set()


def save_seen_wallets(wallets: set):
    SEEN_WALLETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_WALLETS_FILE, "w") as f:
        json.dump(list(wallets), f)


async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[TG] Not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                log("[TG] Sent")
            else:
                log(f"[TG] Failed: {resp.status_code}")
    except Exception as e:
        log(f"[TG] Error: {e}")


def classify_strategy(activity: list) -> dict:
    """
    Analyze trading activity to classify the strategy.
    Returns strategy type and supporting metrics.
    """
    if not activity:
        return {"strategy": STRATEGY_UNKNOWN, "confidence": 0}

    # Categorize trades by market type
    crypto_keywords = ["Up or Down", "Bitcoin", "Ethereum", "Solana", "XRP", "BTC", "ETH", "SOL", "Crypto"]
    sports_keywords = ["NFL", "NBA", "MLB", "NHL", "Super Bowl", "Championship", "vs", "Game", "Match", "Win"]
    political_keywords = ["President", "Election", "Trump", "Biden", "Congress", "Senate", "Governor", "Vote"]

    crypto_trades = []
    sports_trades = []
    political_trades = []
    other_trades = []

    for trade in activity:
        title = trade.get("title", "")
        if any(kw.lower() in title.lower() for kw in crypto_keywords):
            crypto_trades.append(trade)
        elif any(kw.lower() in title.lower() for kw in sports_keywords):
            sports_trades.append(trade)
        elif any(kw.lower() in title.lower() for kw in political_keywords):
            political_trades.append(trade)
        else:
            other_trades.append(trade)

    total = len(activity)
    crypto_pct = len(crypto_trades) / total if total else 0
    sports_pct = len(sports_trades) / total if total else 0
    political_pct = len(political_trades) / total if total else 0

    # Calculate trade frequency and size patterns
    sizes = [float(t.get("usdcSize", 0) or 0) for t in activity]
    avg_size = sum(sizes) / len(sizes) if sizes else 0

    # Count unique markets traded
    markets = set(t.get("slug", "") for t in activity)
    unique_markets = len(markets)

    # Analyze buy/sell balance (market makers have ~50/50)
    buys = len([t for t in activity if t.get("side") == "BUY"])
    sells = len([t for t in activity if t.get("side") == "SELL"])
    buy_sell_ratio = buys / sells if sells > 0 else float('inf')

    # Classify strategy
    strategy = STRATEGY_UNKNOWN
    confidence = 0
    details = {}

    # Crypto arbitrage: High crypto %, small sizes, high frequency, balanced buy/sell
    if crypto_pct >= 0.7 and avg_size < 100 and 0.8 <= buy_sell_ratio <= 1.25:
        strategy = STRATEGY_CRYPTO_ARB
        confidence = min(crypto_pct * 100, 95)
        details = {
            "type": "15-min crypto spread capture",
            "markets": "ETH/BTC/SOL Up or Down",
            "edge": "Buy YES+NO < $1, profit on resolution",
        }

    # Market maker: Balanced buy/sell, many markets, consistent sizes
    elif 0.7 <= buy_sell_ratio <= 1.4 and unique_markets > 20:
        strategy = STRATEGY_MARKET_MAKER
        confidence = 70
        details = {
            "type": "Liquidity provision",
            "markets": f"{unique_markets} unique markets",
            "edge": "Spread capture across markets",
        }

    # Sports betting
    elif sports_pct >= 0.5:
        strategy = STRATEGY_SPORTS
        confidence = min(sports_pct * 100, 95)
        details = {
            "type": "Sports betting",
            "focus": "NFL/NBA/etc",
        }

    # Political
    elif political_pct >= 0.5:
        strategy = STRATEGY_POLITICAL
        confidence = min(political_pct * 100, 95)
        details = {
            "type": "Political markets",
            "focus": "Elections/policy",
        }

    # Mixed
    elif crypto_pct < 0.5 and sports_pct < 0.5 and political_pct < 0.5:
        strategy = STRATEGY_MIXED
        confidence = 50
        details = {"type": "Diversified trading"}

    return {
        "strategy": strategy,
        "confidence": confidence,
        "details": details,
        "crypto_pct": crypto_pct,
        "sports_pct": sports_pct,
        "political_pct": political_pct,
        "avg_trade_size": avg_size,
        "unique_markets": unique_markets,
        "buy_sell_ratio": buy_sell_ratio,
    }


def format_alert(wallet: dict) -> str:
    """Format alert message with strategy analysis."""
    strat = wallet["strategy_info"]
    emoji = STRATEGY_EMOJI.get(strat["strategy"], "❓")

    msg = f"""{emoji} <b>NEW: {strat['strategy'].replace('_', ' ')}</b>

<b>Address:</b> <code>{wallet['address']}</code>
<b>Account Age:</b> {wallet['account_age_days']:.0f} days
<b>Velocity:</b> ${wallet['velocity']:,.0f}/day
<b>Total Profit:</b> ${wallet['total_profit']:,.0f}
<b>Trades/Week:</b> {wallet['trades_this_week']}

<b>Strategy Analysis:</b>
• Confidence: {strat['confidence']:.0f}%
• Crypto: {strat['crypto_pct']:.0%}
• Avg Trade: ${strat['avg_trade_size']:,.0f}
• Markets: {strat['unique_markets']}
• Buy/Sell: {strat['buy_sell_ratio']:.2f}"""

    if strat.get("details"):
        msg += "\n\n<b>Edge:</b>"
        for k, v in strat["details"].items():
            msg += f"\n• {k}: {v}"

    msg += f"\n\n<a href=\"https://polymarket.com/profile/{wallet['address']}\">View Profile</a>"

    return msg


async def analyze_wallet(scanner: WalletScanner, address: str, leaderboard_profit: float) -> dict | None:
    """
    Analyze wallet for explosive growth AND reverse-engineer strategy.
    Only returns if strategy is interesting/replicable.
    """
    try:
        url = f"{scanner.BASE_URL}/activity"
        activity = await scanner._request("GET", url, {"user": address, "limit": 500})

        if not activity or len(activity) < 10:
            return None

        # Calculate velocity metrics
        now = datetime.now().timestamp()
        week_ago = now - 7 * 86400

        timestamps = [float(a.get("timestamp", 0)) for a in activity if a.get("timestamp")]
        if not timestamps:
            return None

        first_trade = min(timestamps)
        account_age_days = max((now - first_trade) / 86400, 1)

        # Skip if account too old
        if account_age_days > MAX_ACCOUNT_AGE_DAYS:
            return None

        velocity = leaderboard_profit / account_age_days

        # Skip if velocity too low
        if velocity < MIN_VELOCITY:
            return None

        # Trade frequency this week
        this_week_trades = [a for a in activity if float(a.get("timestamp", 0)) > week_ago]
        trades_this_week = len(this_week_trades)

        if trades_this_week < MIN_TRADES_WEEK:
            return None

        # Reverse engineer strategy
        strategy_info = classify_strategy(activity)

        # Only alert on interesting strategies
        if strategy_info["strategy"] not in ALERT_STRATEGIES:
            return None

        return {
            "address": address,
            "account_age_days": account_age_days,
            "velocity": velocity,
            "trades_this_week": trades_this_week,
            "total_profit": leaderboard_profit,
            "strategy_info": strategy_info,
        }

    except Exception as e:
        log(f"  Error analyzing {address[:12]}: {e}")
        return None


async def run_scan() -> list[dict]:
    """Scan for explosive growth wallets with interesting strategies."""
    log(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning...")

    async with WalletScanner() as scanner:
        log("  Fetching leaderboards...")

        leaderboard_all = await scanner.fetch_leaderboard(limit=200, period="all")
        await asyncio.sleep(0.5)
        leaderboard_week = await scanner.fetch_leaderboard(limit=200, period="week")

        all_candidates = {}
        for p in leaderboard_all:
            if p.profit >= MIN_LEADERBOARD_PROFIT:
                all_candidates[p.address] = p
        for p in leaderboard_week:
            if p.address not in all_candidates and p.profit >= MIN_LEADERBOARD_PROFIT / 2:
                all_candidates[p.address] = p

        log(f"  {len(all_candidates)} candidates")

        results = []
        checked = 0
        skipped_strategy = 0

        sorted_candidates = sorted(all_candidates.values(), key=lambda x: x.profit, reverse=True)

        for candidate in sorted_candidates[:100]:
            checked += 1

            result = await analyze_wallet(scanner, candidate.address, candidate.profit)

            if result:
                strat = result["strategy_info"]["strategy"]
                log(f"  ✓ {strat}: {candidate.address[:12]}... "
                    f"vel=${result['velocity']:,.0f}/d, "
                    f"conf={result['strategy_info']['confidence']:.0f}%")
                results.append(result)

            await asyncio.sleep(0.5)

        log(f"  Checked {checked}, found {len(results)} with interesting strategies")
        return results


async def daemon_loop():
    log("=" * 60)
    log("  POLY-SCOUT: STRATEGY HUNTER")
    log("=" * 60)
    log("  Looking for: Emerging traders with replicable strategies")
    log("")
    log("  Filters:")
    log(f"    - Account <= {MAX_ACCOUNT_AGE_DAYS} days old")
    log(f"    - Velocity >= ${MIN_VELOCITY:,.0f}/day")
    log(f"    - Trades/week >= {MIN_TRADES_WEEK}")
    log("")
    log("  Alert strategies:")
    for s in ALERT_STRATEGIES:
        log(f"    - {STRATEGY_EMOJI.get(s, '')} {s}")
    log("")
    log(f"  Scan interval: {SCAN_INTERVAL_MINUTES} min")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 60)

    seen_wallets = load_seen_wallets()
    log(f"Loaded {len(seen_wallets)} seen wallets")

    await send_telegram("🟢 <b>Poly-Scout Strategy Hunter Started</b>\n\nLooking for crypto arb & market maker strategies...")

    while True:
        try:
            results = await run_scan()
            new_wallets = [w for w in results if w["address"] not in seen_wallets]

            if new_wallets:
                log(f"🚨 {len(new_wallets)} NEW interesting wallet(s)!")
                for wallet in new_wallets:
                    await send_telegram(format_alert(wallet))
                    seen_wallets.add(wallet["address"])
                save_seen_wallets(seen_wallets)
            else:
                log(f"No new wallets ({len(results)} matched, already seen or filtered)")

        except Exception as e:
            log(f"ERROR: {e}")

        log(f"Next scan in {SCAN_INTERVAL_MINUTES} min...")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)


def main():
    try:
        asyncio.run(daemon_loop())
    except KeyboardInterrupt:
        log("Stopped.")


if __name__ == "__main__":
    main()
