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

import httpx
from dotenv import load_dotenv

from src.scanner import WalletScanner, WalletProfile

load_dotenv()

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
        print(f"[NOTIFY] (Telegram not configured) {message}")
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
                print(f"[NOTIFY] Telegram sent successfully")
            else:
                print(f"[NOTIFY] Telegram failed: {resp.status_code}")
    except Exception as e:
        print(f"[NOTIFY] Telegram error: {e}")


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
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scan...")
    print(f"  Criteria: profit >= ${MIN_PROFIT:,.0f}, win_rate >= {MIN_WIN_RATE:.0%}, trades >= {MIN_TRADES}")

    async with WalletScanner() as scanner:
        # Get leaderboard
        leaderboard = await scanner.fetch_leaderboard(limit=100)

        # Filter by profit
        candidates = [p for p in leaderboard if p.profit >= MIN_PROFIT]
        print(f"  Found {len(candidates)} candidates with profit >= ${MIN_PROFIT:,.0f}")

        results = []
        for i, candidate in enumerate(candidates[:30], 1):  # Check top 30
            print(f"  Checking {i}/{min(len(candidates), 30)}: {candidate.address[:16]}...", end=" ")

            profile = await scanner.fetch_wallet_stats(candidate.address)
            if not profile:
                print("no data")
                continue

            # Apply filters
            if profile.win_rate < MIN_WIN_RATE:
                print(f"win rate {profile.win_rate:.1%} < {MIN_WIN_RATE:.0%}")
                continue

            if profile.trade_count < MIN_TRADES:
                print(f"trades {profile.trade_count} < {MIN_TRADES}")
                continue

            # Preserve leaderboard profit
            profile.profit = candidate.profit
            print(f"MATCH! {profile.win_rate:.1%} win rate, {profile.trade_count} trades")
            results.append(profile)

        return results


async def daemon_loop():
    """Main daemon loop."""
    print("=" * 60)
    print("  POLY-SCOUT DAEMON STARTED")
    print("=" * 60)
    print(f"  Scan interval: {SCAN_INTERVAL_MINUTES} minutes")
    print(f"  Min profit: ${MIN_PROFIT:,.0f}")
    print(f"  Min win rate: {MIN_WIN_RATE:.0%}")
    print(f"  Min trades: {MIN_TRADES}")
    print(f"  Telegram: {'configured' if TELEGRAM_BOT_TOKEN else 'NOT configured'}")
    print("=" * 60)

    seen_wallets = load_seen_wallets()
    print(f"Loaded {len(seen_wallets)} previously seen wallets")

    # Send startup notification
    await send_telegram("🟢 <b>Poly-Scout Daemon Started</b>\n\nScanning for emerging traders...")

    while True:
        try:
            results = await run_scan()

            # Filter out already-seen wallets
            new_wallets = [w for w in results if w.address not in seen_wallets]

            if new_wallets:
                print(f"\n🚨 Found {len(new_wallets)} NEW interesting wallet(s)!")

                for wallet in new_wallets:
                    # Send notification
                    message = format_notification(wallet)
                    await send_telegram(message)

                    # Mark as seen
                    seen_wallets.add(wallet.address)

                # Save updated seen list
                save_seen_wallets(seen_wallets)
            else:
                print(f"\nNo new wallets found. ({len(results)} matched but already seen)")

        except Exception as e:
            print(f"\n❌ Scan error: {e}")
            await send_telegram(f"⚠️ <b>Poly-Scout Error</b>\n\n<code>{str(e)[:200]}</code>")

        # Wait for next scan
        print(f"\nNext scan in {SCAN_INTERVAL_MINUTES} minutes...")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)


def main():
    """Entry point."""
    try:
        asyncio.run(daemon_loop())
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


if __name__ == "__main__":
    main()
