"""
Auto-pilot daemon for poly-scout.
Scans for high-frequency crypto arbitrage traders like 0x8dxd.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
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
MIN_PROFIT = float(os.getenv("SCAN_MIN_PROFIT", "10000"))
MIN_TRADES_24H = int(os.getenv("SCAN_MIN_TRADES_24H", "50"))  # High frequency filter
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SEEN_WALLETS_FILE = Path("/root/poly-scout/data/seen_wallets.json")


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


def format_notification(wallet: dict) -> str:
    return f"""🚨 <b>Potential Crypto Arb Bot Found!</b>

<b>Address:</b> <code>{wallet['address']}</code>
<b>Profit:</b> ${wallet['profit']:,.0f}
<b>24h Trades:</b> {wallet['trades_24h']}
<b>Crypto %:</b> {wallet['crypto_pct']:.0%}
<b>Avg Trade:</b> ${wallet['avg_trade_size']:,.0f}

<a href="https://polymarket.com/profile/{wallet['address']}">View Profile</a>
"""


async def analyze_wallet(scanner: WalletScanner, address: str, leaderboard_profit: float) -> dict | None:
    """
    Analyze a wallet to see if it's a crypto arb bot.
    Returns wallet info if it matches criteria, None otherwise.
    """
    try:
        # Get recent activity
        url = f"{scanner.BASE_URL}/activity"
        activity = await scanner._request("GET", url, {"user": address, "limit": 500})

        if not activity or len(activity) < 10:
            return None

        # Count trades in last 24 hours
        now = datetime.now().timestamp()
        day_ago = now - 86400
        recent_trades = [a for a in activity if float(a.get("timestamp", 0)) > day_ago]
        trades_24h = len(recent_trades)

        # Count crypto UP/DOWN trades
        crypto_keywords = ["Up or Down", "Bitcoin", "Ethereum", "Solana", "XRP", "BTC", "ETH", "SOL"]
        crypto_trades = [a for a in activity if any(kw in a.get("title", "") for kw in crypto_keywords)]
        crypto_pct = len(crypto_trades) / len(activity) if activity else 0

        # Calculate average trade size
        sizes = [float(a.get("usdcSize", 0) or 0) for a in activity if a.get("usdcSize")]
        avg_size = sum(sizes) / len(sizes) if sizes else 0

        # Check if this looks like a crypto arb bot
        is_high_frequency = trades_24h >= MIN_TRADES_24H
        is_crypto_focused = crypto_pct >= 0.5  # At least 50% crypto trades
        is_small_size = avg_size < 500  # Small trade sizes typical of arb
        is_profitable = leaderboard_profit >= MIN_PROFIT

        if is_high_frequency and is_crypto_focused and is_profitable:
            return {
                "address": address,
                "profit": leaderboard_profit,
                "trades_24h": trades_24h,
                "crypto_pct": crypto_pct,
                "avg_trade_size": avg_size,
                "is_arb_bot": True
            }

        return None

    except Exception as e:
        log(f"  Error analyzing {address[:12]}: {e}")
        return None


async def run_scan() -> list[dict]:
    """Scan for crypto arb bots."""
    log(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning for crypto arb bots...")
    log(f"  Filters: profit>${MIN_PROFIT:,.0f}, trades_24h>{MIN_TRADES_24H}, crypto>50%")

    async with WalletScanner() as scanner:
        # Get leaderboard - check more wallets
        leaderboard = await scanner.fetch_leaderboard(limit=200)

        # Filter by minimum profit
        candidates = [p for p in leaderboard if p.profit >= MIN_PROFIT]
        log(f"  {len(candidates)} candidates with profit >= ${MIN_PROFIT:,.0f}")

        results = []
        checked = 0

        for candidate in candidates[:50]:  # Check top 50
            checked += 1

            result = await analyze_wallet(scanner, candidate.address, candidate.profit)

            if result:
                log(f"  ✓ MATCH: {candidate.address[:12]}... {result['trades_24h']} trades/24h, {result['crypto_pct']:.0%} crypto")
                results.append(result)

            # Rate limit
            await asyncio.sleep(0.5)

        log(f"  Checked {checked} wallets, found {len(results)} arb bot candidates")
        return results


async def daemon_loop():
    log("=" * 50)
    log("  POLY-SCOUT CRYPTO ARB HUNTER")
    log("=" * 50)
    log(f"  Looking for: High-frequency crypto traders")
    log(f"  Min profit: ${MIN_PROFIT:,.0f}")
    log(f"  Min trades/24h: {MIN_TRADES_24H}")
    log(f"  Scan interval: {SCAN_INTERVAL_MINUTES} min")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 50)

    seen_wallets = load_seen_wallets()
    log(f"Loaded {len(seen_wallets)} seen wallets")

    await send_telegram("🟢 <b>Poly-Scout Started</b>\n\nHunting for crypto arb bots...")

    while True:
        try:
            results = await run_scan()
            new_wallets = [w for w in results if w["address"] not in seen_wallets]

            if new_wallets:
                log(f"🚨 {len(new_wallets)} NEW arb bot(s) found!")
                for wallet in new_wallets:
                    await send_telegram(format_notification(wallet))
                    seen_wallets.add(wallet["address"])
                save_seen_wallets(seen_wallets)
            else:
                log(f"No new bots ({len(results)} matched, already seen)")

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
