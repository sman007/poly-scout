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

# Tier 1: Rising Star - New wallet exploding
TIER1_MIN_WEEKLY_PNL = float(os.getenv("TIER1_MIN_WEEKLY_PNL", "2000"))
TIER1_MAX_ACCOUNT_AGE_DAYS = int(os.getenv("TIER1_MAX_ACCOUNT_AGE_DAYS", "14"))
TIER1_MIN_TRADES_WEEK = int(os.getenv("TIER1_MIN_TRADES_WEEK", "30"))

# Tier 2: Accelerating - Sudden growth spike
TIER2_ACCELERATION_FACTOR = float(os.getenv("TIER2_ACCELERATION_FACTOR", "3.0"))
TIER2_MIN_WEEKLY_PNL = float(os.getenv("TIER2_MIN_WEEKLY_PNL", "1000"))
TIER2_MAX_ACCOUNT_AGE_DAYS = int(os.getenv("TIER2_MAX_ACCOUNT_AGE_DAYS", "60"))

# Tier 3: Consistent Grinder - Sustainable early edge
TIER3_MIN_WEEKLY_PNL = float(os.getenv("TIER3_MIN_WEEKLY_PNL", "3000"))
TIER3_MAX_TOTAL_PROFIT = float(os.getenv("TIER3_MAX_TOTAL_PROFIT", "50000"))

# Minimum profit to even consider (filters out noise)
MIN_LEADERBOARD_PROFIT = float(os.getenv("MIN_LEADERBOARD_PROFIT", "1000"))

SEEN_WALLETS_FILE = Path("/root/poly-scout/data/seen_wallets.json")

# Tier display info
TIER_NAMES = {1: "RISING STAR", 2: "ACCELERATING", 3: "CONSISTENT GRINDER"}
TIER_EMOJI = {1: "🚀", 2: "📈", 3: "💪"}


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
    growth_str = f"{wallet['growth_rate']:.1f}x" if wallet['growth_rate'] != float('inf') else "NEW"

    return f"""{TIER_EMOJI[tier]} <b>Tier {tier}: {TIER_NAMES[tier]}</b>

<b>Address:</b> <code>{wallet['address']}</code>
<b>Account Age:</b> {wallet['account_age_days']:.0f} days
<b>This Week:</b> ${wallet['this_week_pnl']:,.0f}
<b>Last Week:</b> ${wallet['last_week_pnl']:,.0f}
<b>Growth:</b> {growth_str}
<b>Trades/Week:</b> {wallet['trades_this_week']}
<b>Total Profit:</b> ${wallet['total_profit']:,.0f}

<a href="https://polymarket.com/profile/{wallet['address']}">View Profile</a>
"""


async def analyze_wallet_growth(scanner: WalletScanner, address: str, leaderboard_profit: float) -> dict | None:
    """
    Analyze wallet for explosive growth patterns.
    Returns wallet info with tier classification if interesting, None otherwise.
    """
    try:
        url = f"{scanner.BASE_URL}/activity"
        activity = await scanner._request("GET", url, {"user": address, "limit": 500})

        if not activity or len(activity) < 5:
            return None

        # Parse timestamps
        now = datetime.now().timestamp()
        week_ago = now - 7 * 86400
        two_weeks_ago = now - 14 * 86400

        # Get first trade timestamp (account age)
        timestamps = [float(a.get("timestamp", 0)) for a in activity if a.get("timestamp")]
        if not timestamps:
            return None

        first_trade = min(timestamps)
        account_age_days = (now - first_trade) / 86400

        # Calculate this week's profit
        this_week_trades = [a for a in activity if float(a.get("timestamp", 0)) > week_ago]
        this_week_pnl = sum(float(a.get("pnl", 0) or 0) for a in this_week_trades)

        # Calculate last week's profit
        last_week_trades = [a for a in activity
                            if two_weeks_ago < float(a.get("timestamp", 0)) <= week_ago]
        last_week_pnl = sum(float(a.get("pnl", 0) or 0) for a in last_week_trades)

        # Trade frequency this week
        trades_this_week = len(this_week_trades)

        # Determine tier
        tier = None

        # Tier 1: Rising Star - New wallet exploding
        if (account_age_days < TIER1_MAX_ACCOUNT_AGE_DAYS
            and this_week_pnl > TIER1_MIN_WEEKLY_PNL
            and trades_this_week > TIER1_MIN_TRADES_WEEK):
            tier = 1

        # Tier 2: Accelerating - Sudden growth spike
        elif (last_week_pnl > 0
              and this_week_pnl > TIER2_ACCELERATION_FACTOR * last_week_pnl
              and this_week_pnl > TIER2_MIN_WEEKLY_PNL
              and account_age_days < TIER2_MAX_ACCOUNT_AGE_DAYS):
            tier = 2

        # Tier 3: Consistent Grinder - Sustainable early edge
        elif (this_week_pnl > TIER3_MIN_WEEKLY_PNL
              and last_week_pnl > TIER3_MIN_WEEKLY_PNL
              and leaderboard_profit < TIER3_MAX_TOTAL_PROFIT):
            tier = 3

        if tier:
            growth_rate = this_week_pnl / last_week_pnl if last_week_pnl > 0 else float('inf')
            return {
                "address": address,
                "tier": tier,
                "account_age_days": account_age_days,
                "this_week_pnl": this_week_pnl,
                "last_week_pnl": last_week_pnl,
                "growth_rate": growth_rate,
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
                    f"week=${result['this_week_pnl']:,.0f}, "
                    f"growth={result['growth_rate']:.1f}x")
                results.append(result)

            # Rate limit
            await asyncio.sleep(0.5)

        log(f"  Checked {checked} wallets, found {len(results)} growth candidates")

        # Sort results by tier (lower = higher priority)
        results.sort(key=lambda x: x["tier"])
        return results


async def daemon_loop():
    log("=" * 60)
    log("  POLY-SCOUT: EXPLOSIVE GROWTH DETECTOR")
    log("=" * 60)
    log("  Looking for: Emerging alpha traders")
    log("")
    log("  Tier 1 (Rising Star):")
    log(f"    - Account < {TIER1_MAX_ACCOUNT_AGE_DAYS} days old")
    log(f"    - Week PnL > ${TIER1_MIN_WEEKLY_PNL:,.0f}")
    log(f"    - Trades/week > {TIER1_MIN_TRADES_WEEK}")
    log("")
    log("  Tier 2 (Accelerating):")
    log(f"    - Growth > {TIER2_ACCELERATION_FACTOR}x week-over-week")
    log(f"    - Week PnL > ${TIER2_MIN_WEEKLY_PNL:,.0f}")
    log(f"    - Account < {TIER2_MAX_ACCOUNT_AGE_DAYS} days old")
    log("")
    log("  Tier 3 (Consistent Grinder):")
    log(f"    - Week PnL > ${TIER3_MIN_WEEKLY_PNL:,.0f} for 2+ weeks")
    log(f"    - Total profit < ${TIER3_MAX_TOTAL_PROFIT:,.0f}")
    log("")
    log(f"  Scan interval: {SCAN_INTERVAL_MINUTES} min")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 60)

    seen_wallets = load_seen_wallets()
    log(f"Loaded {len(seen_wallets)} seen wallets")

    await send_telegram("🟢 <b>Poly-Scout v2 Started</b>\n\nHunting for explosive growth wallets...")

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
