"""
Auto-pilot daemon for poly-scout.
Runs continuously, scans for emerging traders, and sends notifications.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Force unbuffered output for systemd journalctl
os.environ['PYTHONUNBUFFERED'] = '1'

import httpx
from dotenv import load_dotenv

from src.scanner import WalletScanner, WalletProfile

load_dotenv()


def log(msg: str):
    """Print with flush for systemd."""
    print(msg, flush=True)

# Configuration from environment
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
MIN_PROFIT = float(os.getenv("SCAN_MIN_PROFIT", "50000"))
MIN_WIN_RATE = float(os.getenv("SCAN_MIN_WIN_RATE", "0.7"))
MIN_TRADES = int(os.getenv("SCAN_MIN_TRADES", "10"))
MAX_AGE_DAYS = int(os.getenv("SCAN_MAX_AGE_DAYS", "60"))

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Track already-notified wallets to avoid spam
SEEN_WALLETS_FILE = Path("/root/poly-scout/data/seen_wallets.json")


def load_seen_wallets() -> set:
    """Load previously seen wallet addresses."""
    if SEEN_WALLETS_FILE.exists():
        try:
            with open(SEEN_WALLETS_FILE) as f:
                return set(json.load(f))
        except:
            pass
    return set()


def save_seen_wallets(wallets: set):
    """Save seen wallet addresses."""
    SEEN_WALLETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_WALLETS_FILE, "w") as f:
        json.dump(list(wallets), f)


async def send_telegram(message: str):
    """Send notification via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[NOTIFY] Telegram not configured")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                log("[NOTIFY] Telegram sent")
            else:
                log(f"[NOTIFY] Telegram failed: {resp.status_code}")
    except Exception as e:
        log(f"[NOTIFY] Telegram error: {e}")


def format_notification(wallet: WalletProfile) -> str:
    """Format wallet data for notification."""
    return f"""🚨 <b>New High-Performance Trader Found!</b>

<b>Address:</b> <code>{wallet.address}</code>
<b>Profit:</b> ${wallet.profit:,.0f}
<b>Win Rate:</b> {wallet.win_rate:.1%}
<b>Positions:</b> {wallet.trade_count}
<b>Volume:</b> ${wallet.volume:,.0f}

<a href="https://polymarket.com/profile/{wallet.address}">View Profile</a>
"""


async def run_scan() -> list[WalletProfile]:
    """Run a single scan and return new interesting wallets."""
    log(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanning...")

    async with WalletScanner() as scanner:
        leaderboard = await scanner.fetch_leaderboard(limit=100)
        candidates = [p for p in leaderboard if p.profit >= MIN_PROFIT]
        log(f"  {len(candidates)} candidates with profit >= ${MIN_PROFIT:,.0f}")

        results = []
        for i, candidate in enumerate(candidates[:30], 1):
            profile = await scanner.fetch_wallet_stats(candidate.address)
            if not profile:
                continue

            if profile.win_rate < MIN_WIN_RATE or profile.trade_count < MIN_TRADES:
                continue

            profile.profit = candidate.profit
            log(f"  MATCH: {candidate.address[:12]}... {profile.win_rate:.0%} win, {profile.trade_count} pos, ${profile.profit:,.0f}")
            results.append(profile)

        return results


async def daemon_loop():
    """Main daemon loop."""
    log("=" * 50)
    log("  POLY-SCOUT DAEMON STARTED")
    log("=" * 50)
    log(f"  Interval: {SCAN_INTERVAL_MINUTES}min | Profit: ${MIN_PROFIT:,.0f} | WinRate: {MIN_WIN_RATE:.0%}")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 50)

    seen_wallets = load_seen_wallets()
    log(f"Loaded {len(seen_wallets)} seen wallets")

    await send_telegram("🟢 <b>Poly-Scout Started</b>")

    while True:
        try:
            results = await run_scan()
            new_wallets = [w for w in results if w.address not in seen_wallets]

            if new_wallets:
                log(f"🚨 {len(new_wallets)} NEW wallet(s) found!")
                for wallet in new_wallets:
                    await send_telegram(format_notification(wallet))
                    seen_wallets.add(wallet.address)
                save_seen_wallets(seen_wallets)
            else:
                log(f"No new wallets ({len(results)} matched, already seen)")

        except Exception as e:
            log(f"ERROR: {e}")

        log(f"Next scan in {SCAN_INTERVAL_MINUTES} min...")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)


def main():
    """Entry point."""
    try:
        asyncio.run(daemon_loop())
    except KeyboardInterrupt:
        log("Stopped.")


if __name__ == "__main__":
    main()
