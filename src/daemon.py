"""
Auto-pilot daemon for poly-scout.
Detects explosive growth patterns in Polymarket wallets.
Finds emerging alpha traders BEFORE they become famous.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

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

# Tier 1: Rising Star - New wallet with high velocity
TIER1_MIN_VELOCITY = float(os.getenv("TIER1_MIN_VELOCITY", "500"))  # $/day
TIER1_MAX_ACCOUNT_AGE_DAYS = int(os.getenv("TIER1_MAX_ACCOUNT_AGE_DAYS", "14"))
TIER1_MIN_TRADES_WEEK = int(os.getenv("TIER1_MIN_TRADES_WEEK", "30"))

# Tier 2: Fast Grower - High velocity regardless of age
TIER2_MIN_VELOCITY = float(os.getenv("TIER2_MIN_VELOCITY", "300"))  # $/day
TIER2_MAX_ACCOUNT_AGE_DAYS = int(os.getenv("TIER2_MAX_ACCOUNT_AGE_DAYS", "30"))
TIER2_MIN_PROFIT = float(os.getenv("TIER2_MIN_PROFIT", "3000"))

# Tier 3: Hot Streak - High recent activity with good profit
TIER3_MIN_VELOCITY = float(os.getenv("TIER3_MIN_VELOCITY", "150"))  # $/day
TIER3_MAX_TOTAL_PROFIT = float(os.getenv("TIER3_MAX_TOTAL_PROFIT", "30000"))
TIER3_MIN_TRADES_WEEK = int(os.getenv("TIER3_MIN_TRADES_WEEK", "50"))

# Minimum profit to even consider (filters out noise)
MIN_LEADERBOARD_PROFIT = float(os.getenv("MIN_LEADERBOARD_PROFIT", "1000"))

SEEN_WALLETS_FILE = Path("/root/poly-scout/data/seen_wallets.json")

# Tier display info
TIER_NAMES = {1: "RISING STAR", 2: "FAST GROWER", 3: "HOT STREAK"}
TIER_EMOJI = {1: "🚀", 2: "📈", 3: "🔥"}


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


def format_growth_notification(wallet: dict) -> str:
    tier = wallet["tier"]

    return f"""{TIER_EMOJI[tier]} <b>Tier {tier}: {TIER_NAMES[tier]}</b>

<b>Address:</b> <code>{wallet['address']}</code>
<b>Account Age:</b> {wallet['account_age_days']:.0f} days
<b>Velocity:</b> ${wallet['velocity']:,.0f}/day
<b>Trades/Week:</b> {wallet['trades_this_week']}
<b>Total Profit:</b> ${wallet['total_profit']:,.0f}

<a href="https://polymarket.com/profile/{wallet['address']}">View Profile</a>
"""


async def analyze_wallet_growth(scanner: WalletScanner, address: str, leaderboard_profit: float) -> dict | None:
    """
    Analyze wallet for explosive growth using profit velocity.
    Velocity = total_profit / account_age_days
    """
    try:
        url = f"{scanner.BASE_URL}/activity"
        activity = await scanner._request("GET", url, {"user": address, "limit": 500})

        if not activity or len(activity) < 5:
            return None

        # Parse timestamps
        now = datetime.now().timestamp()
        week_ago = now - 7 * 86400

        # Get first trade timestamp (account age)
        timestamps = [float(a.get("timestamp", 0)) for a in activity if a.get("timestamp")]
        if not timestamps:
            return None

        first_trade = min(timestamps)
        account_age_days = max((now - first_trade) / 86400, 1)  # At least 1 day to avoid division by zero

        # Calculate velocity (profit per day)
        velocity = leaderboard_profit / account_age_days

        # Trade frequency this week
        this_week_trades = [a for a in activity if float(a.get("timestamp", 0)) > week_ago]
        trades_this_week = len(this_week_trades)

        # Determine tier
        tier = None

        # Tier 1: Rising Star - New wallet with explosive velocity
        if (account_age_days <= TIER1_MAX_ACCOUNT_AGE_DAYS
            and velocity >= TIER1_MIN_VELOCITY
            and trades_this_week >= TIER1_MIN_TRADES_WEEK):
            tier = 1

        # Tier 2: Fast Grower - High velocity, relatively new
        elif (account_age_days <= TIER2_MAX_ACCOUNT_AGE_DAYS
              and velocity >= TIER2_MIN_VELOCITY
              and leaderboard_profit >= TIER2_MIN_PROFIT):
            tier = 2

        # Tier 3: Hot Streak - Good velocity + high activity, not too big yet
        elif (velocity >= TIER3_MIN_VELOCITY
              and leaderboard_profit <= TIER3_MAX_TOTAL_PROFIT
              and trades_this_week >= TIER3_MIN_TRADES_WEEK):
            tier = 3

        if tier:
            return {
                "address": address,
                "tier": tier,
                "account_age_days": account_age_days,
                "velocity": velocity,
                "trades_this_week": trades_this_week,
                "total_profit": leaderboard_profit,
            }

        return None

    except Exception as e:
        log(f"  Error analyzing {address[:12]}: {e}")
        return None


async def run_scan() -> list[dict]:
    """Scan for explosive growth wallets."""
    log(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning for explosive growth...")

    async with WalletScanner() as scanner:
        # Fetch both all-time and weekly leaderboards to catch new risers
        log("  Fetching leaderboards (all-time + weekly)...")

        leaderboard_all = await scanner.fetch_leaderboard(limit=200, period="all")
        await asyncio.sleep(0.5)  # Rate limit
        leaderboard_week = await scanner.fetch_leaderboard(limit=200, period="week")

        # Combine and dedupe - weekly leaders might be new hot wallets not on all-time yet
        all_candidates = {}
        for p in leaderboard_all:
            if p.profit >= MIN_LEADERBOARD_PROFIT:
                all_candidates[p.address] = p
        for p in leaderboard_week:
            if p.address not in all_candidates and p.profit >= MIN_LEADERBOARD_PROFIT / 2:
                all_candidates[p.address] = p

        log(f"  {len(all_candidates)} unique candidates (profit >= ${MIN_LEADERBOARD_PROFIT:,.0f})")

        results = []
        checked = 0

        # Sort by profit descending but check more wallets
        sorted_candidates = sorted(all_candidates.values(), key=lambda x: x.profit, reverse=True)

        for candidate in sorted_candidates[:100]:  # Check top 100
            checked += 1

            result = await analyze_wallet_growth(scanner, candidate.address, candidate.profit)

            if result:
                tier = result["tier"]
                log(f"  ✓ T{tier} {TIER_NAMES[tier]}: {candidate.address[:12]}... "
                    f"age={result['account_age_days']:.0f}d, "
                    f"vel=${result['velocity']:,.0f}/d, "
                    f"trades={result['trades_this_week']}/wk")
                results.append(result)

            # Rate limit
            await asyncio.sleep(0.5)

        log(f"  Checked {checked} wallets, found {len(results)} growth candidates")

        # Sort results by tier (lower = higher priority)
        results.sort(key=lambda x: x["tier"])
        return results


async def daemon_loop():
    log("=" * 60)
    log("  POLY-SCOUT: EXPLOSIVE GROWTH DETECTOR v2")
    log("=" * 60)
    log("  Looking for: Emerging alpha traders (velocity-based)")
    log("")
    log("  Tier 1 (Rising Star):")
    log(f"    - Account <= {TIER1_MAX_ACCOUNT_AGE_DAYS} days old")
    log(f"    - Velocity >= ${TIER1_MIN_VELOCITY:,.0f}/day")
    log(f"    - Trades/week >= {TIER1_MIN_TRADES_WEEK}")
    log("")
    log("  Tier 2 (Fast Grower):")
    log(f"    - Account <= {TIER2_MAX_ACCOUNT_AGE_DAYS} days old")
    log(f"    - Velocity >= ${TIER2_MIN_VELOCITY:,.0f}/day")
    log(f"    - Profit >= ${TIER2_MIN_PROFIT:,.0f}")
    log("")
    log("  Tier 3 (Hot Streak):")
    log(f"    - Velocity >= ${TIER3_MIN_VELOCITY:,.0f}/day")
    log(f"    - Profit <= ${TIER3_MAX_TOTAL_PROFIT:,.0f}")
    log(f"    - Trades/week >= {TIER3_MIN_TRADES_WEEK}")
    log("")
    log(f"  Scan interval: {SCAN_INTERVAL_MINUTES} min")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 60)

    seen_wallets = load_seen_wallets()
    log(f"Loaded {len(seen_wallets)} seen wallets")

    await send_telegram("🟢 <b>Poly-Scout v2 Started</b>\n\nHunting for explosive growth wallets (velocity-based)...")

    while True:
        try:
            results = await run_scan()
            new_wallets = [w for w in results if w["address"] not in seen_wallets]

            if new_wallets:
                log(f"🚨 {len(new_wallets)} NEW growth wallet(s) found!")
                for wallet in new_wallets:
                    await send_telegram(format_growth_notification(wallet))
                    seen_wallets.add(wallet["address"])
                save_seen_wallets(seen_wallets)
            else:
                log(f"No new wallets ({len(results)} matched criteria, already seen)")

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
