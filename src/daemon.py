"""
Auto-pilot daemon for poly-scout.
Detects mispriced markets and arbitrage opportunities on Polymarket.

Active sources:
- Sportsbook comparison (PM vs Vegas odds)
- New market monitoring (mispricing detection)
- Blockchain scanning (smart money detection)

Disabled sources (ENABLE_WALLET_ALERTS=false):
- Leaderboard wallet scanning
- X.com/Twitter scanning

All alerts require edge validation (min 3% edge, $1k liquidity).
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from collections import Counter
from functools import lru_cache
import time

os.environ['PYTHONUNBUFFERED'] = '1'

import httpx
from dotenv import load_dotenv

# === CACHING ===
# Cache for wallet activity data (expires after 5 minutes)
_activity_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes

def get_cached_activity(address: str) -> list | None:
    """Get cached activity if not expired."""
    if address in _activity_cache:
        timestamp, data = _activity_cache[address]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return data
        del _activity_cache[address]
    return None

def set_cached_activity(address: str, data: list):
    """Cache activity data."""
    _activity_cache[address] = (time.time(), data)

# Concurrency limiter for parallel requests
MAX_CONCURRENT_WALLETS = 10

from src.scanner import WalletScanner, WalletProfile, find_similar_wallets, update_saturation_trend
from src.sportsbook import SportsbookComparator, SportsbookOpportunity
from src.twitter_scanner import TwitterScanner
from src.validator import EdgeValidator, ValidationResult
from src.new_market_monitor import NewMarketMonitor, NewMarketOpportunity
from src.blockchain_scanner import BlockchainScanner
from src.longshot_scanner import LongshotScanner, LongshotOpportunity, send_longshot_alert
from src.weather_bucket_scanner import WeatherBucketScanner, BucketArbitrageOpportunity
from src.scalp_scanner import scan_once as scalp_scan_once
from src.paper_kelly import load_portfolio, save_portfolio, paper_trade_sports_edge, print_portfolio_summary
from src.reverse import (
    StrategyReverser,
    StrategyBlueprint,
    Trade as ReverseTrade,
    WalletProfile as ReverseWalletProfile,
    WalletAnalysis as ReverseWalletAnalysis,
)
from datetime import timedelta
from src.config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, POLYGON_RPC_URL,
    MIN_EDGE_PCT, MIN_LIQUIDITY_USD, MIN_EXPECTED_PROFIT,
    SCAN_INTERVAL_LEADERBOARD, SCAN_INTERVAL_SPORTSBOOK, SCAN_INTERVAL_TWITTER,
    SCAN_INTERVAL_NEW_MARKETS, SEEN_OPPORTUNITIES_FILE, ENABLE_WALLET_ALERTS
)

# Blockchain scanner interval (15 minutes)
SCAN_INTERVAL_BLOCKCHAIN = 900

# Longshot scanner interval (10 minutes)
SCAN_INTERVAL_LONGSHOT = 600

# Scalp scanner interval (5 minutes) - Forward testing near-resolution strategy
SCAN_INTERVAL_SCALP = 300

# Weather bucket scanner interval (10 minutes) - 0xf2e346ab bucket arbitrage
SCAN_INTERVAL_WEATHER_BUCKET = 600

# Paper trading allocations - $1000 per strategy
STRATEGY_BUDGET = 1000.0  # Max allocation per strategy
LONGSHOT_BET_SIZE = 50.0  # Per longshot bet
WEATHER_BUCKET_BET_PER_BRACKET = 100.0  # Per bracket in weather arb

load_dotenv()


def log(msg: str):
    print(msg, flush=True)


def convert_to_reverse_types(
    address: str,
    activity: list,
    leaderboard_profit: float,
    account_age_days: float
) -> tuple:
    """
    Convert raw API activity data to types expected by StrategyReverser.

    Returns: (trades, wallet_profile, wallet_analysis)
    """
    trades = []
    for a in activity:
        try:
            ts = a.get("timestamp")
            if isinstance(ts, (int, float)):
                ts = datetime.fromtimestamp(ts)
            elif isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            else:
                ts = datetime.now()

            trade = ReverseTrade(
                timestamp=ts,
                market_id=a.get("slug", a.get("market_id", "unknown")),
                market_title=a.get("title", "Unknown"),
                outcome=a.get("outcome", "unknown"),
                side=a.get("side", "buy").upper(),
                shares=float(a.get("size", 0) or 0),
                price=float(a.get("price", 0) or 0),
                value=float(a.get("usdcSize", 0) or 0),
                market_type="binary",
            )
            trades.append(trade)
        except Exception:
            continue

    wallet_profile = ReverseWalletProfile(
        address=address,
        total_trades=len(trades),
        active_days=int(account_age_days),
        creation_date=datetime.now() - timedelta(days=account_age_days),
        total_pnl=leaderboard_profit,
        current_balance=0.0,  # Not available from leaderboard
    )

    # Calculate basic analysis metrics
    sizes = [t.value for t in trades if t.value > 0]
    avg_trade_size = sum(sizes) / len(sizes) if sizes else 0

    # Get unique market categories
    markets = list(set(t.market_title for t in trades))[:10]

    # Calculate win rate from trades (simplified)
    buy_count = sum(1 for t in trades if t.side == "BUY")
    win_rate = 0.0
    if leaderboard_profit > 0 and len(trades) > 0:
        # Rough estimate: if profitable, assume some win rate
        win_rate = 0.6 + min(0.35, leaderboard_profit / 100000)

    wallet_analysis = ReverseWalletAnalysis(
        wallet=wallet_profile,
        primary_markets=markets,
        avg_trade_size=avg_trade_size,
        avg_holding_period=timedelta(hours=1),  # Default estimate
        win_rate=win_rate,
        peak_exposure=0.5,  # Default estimate
        trading_hours=list(range(24)),  # Active all hours
        patterns={},
    )

    return trades, wallet_profile, wallet_analysis


# Configuration
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

# Velocity thresholds
MIN_VELOCITY = float(os.getenv("MIN_VELOCITY", "300"))  # $/day
MAX_ACCOUNT_AGE_DAYS = int(os.getenv("MAX_ACCOUNT_AGE_DAYS", "30"))
MIN_TRADES_WEEK = int(os.getenv("MIN_TRADES_WEEK", "30"))
MIN_LEADERBOARD_PROFIT = float(os.getenv("MIN_LEADERBOARD_PROFIT", "1000"))

SEEN_WALLETS_FILE = Path("./data/seen_wallets.json")

# Strategy classifications
STRATEGY_BINANCE_SIGNAL = "BINANCE_SIGNAL"  # Directional trading based on Binance price moves
STRATEGY_SPREAD_CAPTURE = "SPREAD_CAPTURE"  # Buy YES+NO < $1, profit on resolution
STRATEGY_SPORTS = "SPORTS"
STRATEGY_POLITICAL = "POLITICAL"
STRATEGY_MARKET_MAKER = "MARKET_MAKER"
STRATEGY_MIXED = "MIXED"
STRATEGY_UNKNOWN = "UNKNOWN"
STRATEGY_NEW_MARKET_SNIPER = "NEW_MARKET_SNIPER"  # Early entry on mispriced new markets

# Resolution time in MINUTES per strategy
# Lower = faster capital turnover = more compounding = more profit
STRATEGY_RESOLUTION_MINUTES = {
    STRATEGY_BINANCE_SIGNAL: 15,      # 15-min crypto markets - 96 cycles/day!
    STRATEGY_SPREAD_CAPTURE: 15,      # 15-min crypto markets - 96 cycles/day!
    STRATEGY_SPORTS: 180,             # 3 hours avg (games, matches)
    STRATEGY_MARKET_MAKER: 60,        # Varies, estimate 1 hour
    STRATEGY_MIXED: 120,              # 2 hours avg
    STRATEGY_POLITICAL: 43200,        # 30 days avg (elections)
    STRATEGY_UNKNOWN: 1440,           # 1 day avg (conservative)
    STRATEGY_NEW_MARKET_SNIPER: 1440, # Variable - holds until resolution (days)
}

# Compounding potential per day (higher = faster profit)
# Formula: 1440 minutes/day / resolution_minutes
def get_daily_compounds(strategy: str) -> float:
    """How many times capital can compound per day."""
    resolution = STRATEGY_RESOLUTION_MINUTES.get(strategy, 1440)
    return 1440 / resolution

# Minimum replicability score to trigger alert
MIN_REPLICABILITY_SCORE = 6

# Minimum monthly ROI % to consider worth building
MIN_MONTHLY_ROI_PCT = 20

# Fast-resolution strategies to PRIORITIZE (15-min markets = maximum compounding)
FAST_RESOLUTION_STRATEGIES = {STRATEGY_BINANCE_SIGNAL, STRATEGY_SPREAD_CAPTURE}

# Medium-resolution strategies (hours to days - still reasonable turnover)
MEDIUM_RESOLUTION_STRATEGIES = {STRATEGY_SPORTS, STRATEGY_MARKET_MAKER}

# Slow-resolution strategies to SKIP entirely (take weeks/months to resolve)
SLOW_RESOLUTION_STRATEGIES = {STRATEGY_POLITICAL}

# ONLY fast strategies (15-min crypto)? Set False to include sports too
FAST_ONLY_MODE = False  # Set True to only show 15-min crypto strategies

STRATEGY_EMOJI = {
    STRATEGY_BINANCE_SIGNAL: "[BIN]",
    STRATEGY_SPREAD_CAPTURE: "[SPR]",
    STRATEGY_SPORTS: "[SPT]",
    STRATEGY_POLITICAL: "[POL]",
    STRATEGY_MARKET_MAKER: "[MM]",
    STRATEGY_MIXED: "[MIX]",
    STRATEGY_UNKNOWN: "[?]",
}

# Saturation history file for tracking competition over time
SATURATION_HISTORY_FILE = Path("./data/saturation_history.json")


def load_seen_wallets() -> set:
    if SEEN_WALLETS_FILE.exists():
        try:
            with open(SEEN_WALLETS_FILE) as f:
                return set(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
    return set()


def save_seen_wallets(wallets: set):
    SEEN_WALLETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_WALLETS_FILE, "w") as f:
        json.dump(list(wallets), f)


def load_saturation_history() -> dict:
    """Load saturation history for trend tracking."""
    if SATURATION_HISTORY_FILE.exists():
        try:
            with open(SATURATION_HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_saturation_history(history: dict):
    """Save saturation history."""
    SATURATION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SATURATION_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def load_seen_opportunities() -> set:
    """Load previously seen opportunities to avoid duplicates."""
    try:
        path = Path(SEEN_OPPORTUNITIES_FILE)
        if path.exists():
            with open(path) as f:
                return set(json.load(f))
    except (json.JSONDecodeError, IOError):
        pass
    return set()


def save_seen_opportunities(opps: set):
    """Save seen opportunities."""
    try:
        path = Path(SEEN_OPPORTUNITIES_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(list(opps), f)
    except Exception as e:
        log(f"Error saving seen opportunities: {e}")


def _detect_new_market_sniper(activity: list) -> tuple[bool, float, str]:
    """
    Detect NEW_MARKET_SNIPER pattern:
    - Enters markets very early (concentrated first trades)
    - Entry prices show extreme mispricing (<$0.15 or >$0.85)
    - Few trades per market (buy and hold)

    Returns: (is_pattern, confidence, explanation)
    """
    if not activity or len(activity) < 5:
        return False, 0.0, ""

    # Group trades by market
    market_trades = {}
    for t in activity:
        market = t.get("slug") or t.get("market_id", "unknown")
        if market not in market_trades:
            market_trades[market] = []
        market_trades[market].append(t)

    # Analyze for sniper pattern
    sniper_markets = 0
    total_markets = len(market_trades)
    extreme_prices = []

    for market, trades in market_trades.items():
        # Few trades per market = buy and hold (sniper behavior)
        if len(trades) > 10:
            continue  # Too many trades, not sniper

        # Check for extreme entry prices
        buy_trades = [t for t in trades if t.get("side") == "buy"]
        for t in buy_trades:
            price = float(t.get("price", 0.5) or 0.5)
            # Extreme mispricing: <15 cents or >85 cents
            if price < 0.15 or price > 0.85:
                extreme_prices.append(price)
                sniper_markets += 1
                break

    if total_markets == 0:
        return False, 0.0, ""

    sniper_ratio = sniper_markets / total_markets
    avg_extreme_price = sum(extreme_prices) / len(extreme_prices) if extreme_prices else 0.5

    # Calculate confidence
    confidence = 0.0
    if sniper_ratio > 0.3:
        confidence += 0.3
    if sniper_ratio > 0.5:
        confidence += 0.2
    if avg_extreme_price < 0.10 or avg_extreme_price > 0.90:
        confidence += 0.3

    is_pattern = confidence >= 0.5 and sniper_ratio >= 0.3

    explanation = (
        f"New market sniper - enters at extreme prices (avg ${avg_extreme_price:.2f}). "
        f"{sniper_ratio:.0%} of markets show sniper pattern. Buy-and-hold until resolution."
    )

    return is_pattern, min(0.95, confidence), explanation


def analyze_strategy_deep(activity: list) -> dict:
    """
    Extract strategy characteristics WITHOUT assuming what it is.
    Let the data tell us what they're doing.

    This is strategy-agnostic analysis - we extract metrics first,
    then try to match against known patterns.
    """
    if not activity or len(activity) < 10:
        return {"likely_strategy": STRATEGY_UNKNOWN, "confidence": 0}

    # === CORE: Determine ARB vs DIRECTIONAL ===
    # Group by market and check if buying both sides
    market_outcomes = {}
    yes_buys = 0
    no_buys = 0

    for t in activity:
        title = t.get("title", "")
        outcome = t.get("outcome", "").lower()
        side = t.get("side", "").upper()

        if title not in market_outcomes:
            market_outcomes[title] = {"yes": 0, "no": 0}

        if "yes" in outcome or side == "BUY":
            yes_buys += 1
            market_outcomes[title]["yes"] += 1
        else:
            no_buys += 1
            market_outcomes[title]["no"] += 1

    # Count markets with both sides vs one side
    both_sides = sum(1 for m in market_outcomes.values() if m["yes"] > 0 and m["no"] > 0)
    one_side = sum(1 for m in market_outcomes.values() if (m["yes"] > 0) != (m["no"] > 0))

    is_arb_pattern = both_sides > one_side * 0.5  # More than half markets have both sides
    yes_no_ratio = yes_buys / (no_buys + 1)

    # Top markets traded
    market_volumes = {}
    for t in activity:
        title = t.get("title", "Unknown")[:50]
        size = float(t.get("usdcSize", 0) or 0)
        market_volumes[title] = market_volumes.get(title, 0) + size

    top_markets = sorted(market_volumes.items(), key=lambda x: -x[1])[:5]

    # Filter to crypto 15-min markets
    crypto_keywords = ["Up or Down", "Bitcoin", "Ethereum", "Solana", "XRP", "BTC", "ETH", "SOL"]
    crypto_15m_trades = []
    other_trades = []

    for trade in activity:
        title = trade.get("title", "")
        is_crypto_15m = any(kw.lower() in title.lower() for kw in crypto_keywords) and "15" in title
        if is_crypto_15m:
            crypto_15m_trades.append(trade)
        else:
            other_trades.append(trade)

    crypto_15m_pct = len(crypto_15m_trades) / len(activity) if activity else 0

    # === CORE METRIC: Combined YES+NO average price ===
    # This is THE key differentiator:
    # - > $1.00 = DIRECTIONAL (Binance signal) - they're betting on direction
    # - < $1.00 = SPREAD CAPTURE - they're buying YES+NO to lock in profit

    yes_prices = []
    no_prices = []
    up_prices = []
    down_prices = []

    for trade in crypto_15m_trades:
        side = trade.get("side", "").upper()
        outcome = trade.get("outcome", "").lower()
        price = float(trade.get("price", 0) or 0)
        title = trade.get("title", "").lower()

        if price <= 0 or price > 1:
            continue

        # Determine if this is YES/NO and Up/Down
        if "yes" in outcome or side == "BUY":
            yes_prices.append(price)
            if "up" in title:
                up_prices.append(price)
            elif "down" in title:
                down_prices.append(price)
        elif "no" in outcome or side == "SELL":
            no_prices.append(price)

    # Calculate combined average
    # If they're buying both YES and NO in same markets, add them
    combined_avg = 0.0
    if yes_prices and no_prices:
        combined_avg = (sum(yes_prices) / len(yes_prices)) + (sum(no_prices) / len(no_prices))
    elif yes_prices:
        combined_avg = sum(yes_prices) / len(yes_prices)

    # === Direction bias ===
    # 0.5 = balanced (spread capture), >0.5 = biased toward one side (directional)
    total_directional = len(up_prices) + len(down_prices)
    direction_bias = 0.5
    if total_directional > 0:
        direction_bias = max(len(up_prices), len(down_prices)) / total_directional

    # === Entry price ranges ===
    entry_prices = {
        "up": (min(up_prices) if up_prices else 0, max(up_prices) if up_prices else 0),
        "down": (min(down_prices) if down_prices else 0, max(down_prices) if down_prices else 0),
    }

    # === Trade sizing ===
    sizes = [float(t.get("usdcSize", 0) or 0) for t in activity]
    avg_trade_size = sum(sizes) / len(sizes) if sizes else 0

    # === Trade frequency ===
    timestamps = [float(t.get("timestamp", 0)) for t in activity if t.get("timestamp")]
    if len(timestamps) >= 2:
        time_span_hours = (max(timestamps) - min(timestamps)) / 3600
        trades_per_hour = len(timestamps) / time_span_hours if time_span_hours > 0 else 0
    else:
        trades_per_hour = 0

    # === Timing pattern ===
    # "throughout" = trades spread across time window
    # "at_resolution" = trades clustered near market resolution
    # "burst" = sporadic high-activity periods
    timing_pattern = "throughout"  # Default

    # === Market concentration ===
    markets = set(t.get("slug", "") or t.get("market_id", "") for t in activity)
    unique_markets = len(markets)
    market_concentration = len(crypto_15m_trades) / len(activity) if activity else 0

    # === Classify strategy based on metrics ===
    likely_strategy = STRATEGY_UNKNOWN
    confidence = 0.0
    edge_explanation = ""

    # BINANCE_SIGNAL: High crypto 15m focus (arb OR directional)
    # Combined avg > $1 = arb pattern, otherwise directional betting
    if crypto_15m_pct > 0.5:
        likely_strategy = STRATEGY_BINANCE_SIGNAL
        if combined_avg > 1.0:
            confidence = min(0.5 + (combined_avg - 1.0) * 2 + crypto_15m_pct * 0.3, 0.95)
            edge_explanation = "Binance signal arb - buying both sides > $1"
        else:
            confidence = min(0.4 + crypto_15m_pct * 0.5, 0.90)
            edge_explanation = "Binance signal directional - betting on price direction"

    # SPREAD_CAPTURE: Combined avg < $1, buying both sides (non-crypto markets)
    elif combined_avg > 0 and combined_avg < 1.0 and yes_prices and no_prices and is_arb_pattern:
        likely_strategy = STRATEGY_SPREAD_CAPTURE
        confidence = min(0.5 + (1.0 - combined_avg) * 2, 0.95)
        edge_explanation = "Buy YES+NO < $1, guaranteed profit on resolution"

    # Check for other patterns (sports, political)
    if likely_strategy == STRATEGY_UNKNOWN:
        sports_keywords = ["NFL", "NBA", "MLB", "NHL", "Game", "Match", "Win", "Super Bowl", "vs.", "Spread"]
        political_keywords = ["President", "Election", "Trump", "Biden", "Congress"]

        sports_count = sum(1 for t in activity if any(k.lower() in t.get("title", "").lower() for k in sports_keywords))
        political_count = sum(1 for t in activity if any(k.lower() in t.get("title", "").lower() for k in political_keywords))

        if sports_count / len(activity) > 0.3:
            likely_strategy = STRATEGY_SPORTS
            confidence = min(sports_count / len(activity) + 0.3, 0.95)
            if is_arb_pattern:
                edge_explanation = "Sports arbitrage - buying both outcomes"
            else:
                edge_explanation = f"Sports betting - picking winners (YES/NO ratio: {yes_no_ratio:.1f})"
        elif political_count / len(activity) > 0.5:
            likely_strategy = STRATEGY_POLITICAL
            confidence = political_count / len(activity)

    # Check for NEW_MARKET_SNIPER pattern (extreme entry prices, buy-and-hold)
    if likely_strategy == STRATEGY_UNKNOWN:
        is_sniper, sniper_conf, sniper_explanation = _detect_new_market_sniper(activity)
        if is_sniper and sniper_conf > confidence:
            likely_strategy = STRATEGY_NEW_MARKET_SNIPER
            confidence = sniper_conf
            edge_explanation = sniper_explanation

    # If still unknown but has clear pattern
    if likely_strategy == STRATEGY_UNKNOWN and len(activity) >= 20:
        if is_arb_pattern:
            edge_explanation = "Unknown arbitrage pattern - buying both sides"
        elif yes_no_ratio > 2:
            edge_explanation = f"Directional betting - heavy YES bias ({yes_no_ratio:.1f}:1)"
        elif yes_no_ratio < 0.5:
            edge_explanation = f"Directional betting - heavy NO bias (1:{1/yes_no_ratio:.1f})"

    return {
        # Core metrics
        "combined_yes_no_avg": round(combined_avg, 3),
        "direction_bias": round(direction_bias, 2),

        # Entry patterns
        "entry_price_ranges": entry_prices,

        # Timing patterns
        "trades_per_hour": round(trades_per_hour, 1),
        "timing_pattern": timing_pattern,

        # Market focus
        "markets": list(markets)[:10],  # Top 10
        "top_markets": top_markets,  # Top 5 by volume
        "market_concentration": round(market_concentration, 2),
        "crypto_15m_pct": round(crypto_15m_pct, 2),

        # Position sizing
        "avg_trade_size": round(avg_trade_size, 2),

        # Trading pattern
        "is_arb_pattern": is_arb_pattern,
        "yes_no_ratio": round(yes_no_ratio, 2),
        "markets_both_sides": both_sides,
        "markets_one_side": one_side,

        # Classification
        "likely_strategy": likely_strategy,
        "confidence": round(confidence, 2),
        "edge_explanation": edge_explanation,
    }


def check_recency(activity: list, max_inactive_hours: int = 168) -> tuple[bool, float]:
    """
    Check if wallet is still active.

    Returns:
        (is_active, hours_since_last_trade)
    """
    if not activity:
        return False, float('inf')

    timestamps = [float(t.get("timestamp", 0)) for t in activity if t.get("timestamp")]
    if not timestamps:
        return False, float('inf')

    last_trade = max(timestamps)
    now = datetime.now().timestamp()
    hours_since = (now - last_trade) / 3600

    return hours_since <= max_inactive_hours, hours_since


def analyze_profit_potential(
    wallet_profit: float,
    account_age_days: float,
    strategy_params: dict,
    saturation: dict
) -> dict:
    """
    The ultimate question: Will WE make money if we replicate this?
    """
    # Their performance
    their_daily_profit = wallet_profit / account_age_days if account_age_days > 0 else 0

    # Estimate OUR profit potential
    # Account for saturation (more bots = less edge)
    wallet_count = saturation.get("wallet_count", 1)
    saturation_factor = 1.0 / (1 + wallet_count * 0.1)

    # Account for our execution (assume 80% as efficient)
    execution_factor = 0.8

    # Estimated daily profit for us
    our_daily_estimate = their_daily_profit * saturation_factor * execution_factor

    # Capital requirements based on avg trade size
    avg_size = strategy_params.get("avg_trade_size", 5)
    min_capital = max(avg_size * 20, 500)  # At least $500, or 20 concurrent positions

    # ROI calculation
    daily_roi = our_daily_estimate / min_capital if min_capital > 0 else 0
    monthly_roi = daily_roi * 30

    # Determine verdict
    verdict = "BUILD" if monthly_roi * 100 >= MIN_MONTHLY_ROI_PCT else "SKIP"

    # Edge durability based on saturation
    if wallet_count < 3:
        edge_durability = "HIGH"
    elif wallet_count < 6:
        edge_durability = "MEDIUM"
    else:
        edge_durability = "LOW"

    return {
        # Their proven numbers
        "their_total_profit": round(wallet_profit, 2),
        "their_daily_profit": round(their_daily_profit, 2),

        # Our estimates
        "our_daily_estimate": round(our_daily_estimate, 2),
        "our_monthly_estimate": round(our_daily_estimate * 30, 2),

        # Investment metrics
        "min_capital_required": round(min_capital, 0),
        "daily_roi_pct": round(daily_roi * 100, 1),
        "monthly_roi_pct": round(monthly_roi * 100, 1),

        # Risk assessment
        "saturation_risk": saturation.get("trend", "unknown"),
        "edge_durability": edge_durability,

        # Bottom line
        "verdict": verdict,
    }


def calculate_replicability(strategy_params: dict, saturation: dict, profit: dict) -> int:
    """
    Score how easy/worth it is to replicate (1-10).
    Higher = more attractive to replicate.
    """
    score = 10

    # Profit potential (most important!)
    monthly_roi = profit.get("monthly_roi_pct", 0)
    if monthly_roi < 10:
        score -= 4  # Not worth the effort
    elif monthly_roi < 20:
        score -= 2

    # Strategy complexity penalty
    strategy = strategy_params.get("likely_strategy", STRATEGY_UNKNOWN)
    if strategy == STRATEGY_BINANCE_SIGNAL:
        score -= 1  # Need Binance WS integration
    elif strategy == STRATEGY_UNKNOWN:
        score -= 3  # Can't replicate what we don't understand

    # Capital requirement penalty
    min_capital = profit.get("min_capital_required", 0)
    if min_capital > 5000:
        score -= 2
    elif min_capital > 2000:
        score -= 1

    # Saturation penalty (IMPORTANT)
    wallet_count = saturation.get("wallet_count", 0)
    if wallet_count > 5:
        score -= 2
    elif wallet_count > 2:
        score -= 1

    if saturation.get("trend") == "increasing":
        score -= 1  # Getting crowded

    # Timing requirement penalty
    if strategy_params.get("timing_pattern") == "immediate":
        score -= 2  # Need low latency

    return max(1, min(10, score))


# =============================================================================
# Strategy Reports - Aggregate wallets by strategy to answer "what actually works"
# =============================================================================

STRATEGY_EXPLANATIONS = {
    STRATEGY_BINANCE_SIGNAL: {
        "edge": "Exploit price lag between Binance spot and Polymarket 15-min markets",
        "how": "When Binance BTC moves 2%+, PM 15-min markets lag by 30-120 seconds. Buy direction before PM catches up.",
        "requirements": "Binance WebSocket feed, PM API, <5s execution",
        "risk": "LOW if execution is fast, HIGH if slow (price already moved)",
    },
    STRATEGY_SPREAD_CAPTURE: {
        "edge": "Buy YES + NO when combined price < $1, guaranteed profit at resolution",
        "how": "Find markets where YES @ $0.45 + NO @ $0.50 = $0.95. Buy both, get $1 at resolution.",
        "requirements": "PM API, capital to hold positions until resolution",
        "risk": "VERY LOW - profit is guaranteed if you can execute both sides",
    },
    STRATEGY_SPORTS: {
        "edge": "PM sports prices lag Vegas/sportsbook lines by hours",
        "how": "Compare PM to DraftKings/FanDuel. When PM is 5%+ off, take the edge.",
        "requirements": "Sportsbook API or odds feeds, PM API",
        "risk": "MEDIUM - sports outcomes are uncertain, edge is in the odds",
    },
    STRATEGY_POLITICAL: {
        "edge": "Information advantage on political events (polls, news)",
        "how": "React faster than market to polls, news, policy announcements",
        "requirements": "News feeds, polling data, fast manual or automated trading",
        "risk": "MEDIUM-HIGH - requires genuine information edge",
    },
    STRATEGY_NEW_MARKET_SNIPER: {
        "edge": "New markets often mispriced at extreme odds (5-15 cents)",
        "how": "Monitor for new markets, buy at extreme prices before market corrects",
        "requirements": "PM API polling for new markets, fast execution",
        "risk": "MEDIUM - some extreme prices are correct, most aren't",
    },
    STRATEGY_UNKNOWN: {
        "edge": "Unknown - needs manual analysis",
        "how": "Review wallet trades to understand the pattern",
        "requirements": "Manual research",
        "risk": "UNKNOWN",
    },
}


def generate_strategy_report(wallets: list[dict]) -> list[str]:
    """
    Aggregate wallets by strategy and generate actionable reports.

    Returns a list of Telegram messages (one per strategy with enough data).
    """
    if not wallets:
        return []

    # Group wallets by strategy
    by_strategy = {}
    for w in wallets:
        strat = w.get("strategy_params", {}).get("likely_strategy", STRATEGY_UNKNOWN)
        if strat not in by_strategy:
            by_strategy[strat] = []
        by_strategy[strat].append(w)

    reports = []

    for strategy, strat_wallets in by_strategy.items():
        # Skip if too few wallets or unknown strategy
        if len(strat_wallets) < 2 and strategy != STRATEGY_BINANCE_SIGNAL:
            continue

        # Aggregate metrics
        total_profit = sum(w.get("profit_analysis", {}).get("their_total_profit", 0) for w in strat_wallets)
        avg_roi = sum(w.get("profit_analysis", {}).get("monthly_roi_pct", 0) for w in strat_wallets) / len(strat_wallets)
        avg_score = sum(w.get("replicability_score", 0) for w in strat_wallets) / len(strat_wallets)
        build_count = sum(1 for w in strat_wallets if w.get("profit_analysis", {}).get("verdict") == "BUILD")

        # Get common top markets
        all_markets = []
        for w in strat_wallets:
            top = w.get("strategy_params", {}).get("top_markets", [])
            all_markets.extend([m[0] for m in top[:3]])  # Top 3 from each wallet

        market_counts = {}
        for m in all_markets:
            market_counts[m] = market_counts.get(m, 0) + 1
        common_markets = sorted(market_counts.items(), key=lambda x: -x[1])[:3]

        # Get strategy explanation
        explanation = STRATEGY_EXPLANATIONS.get(strategy, STRATEGY_EXPLANATIONS[STRATEGY_UNKNOWN])

        # Calculate saturation/competition
        wallet_count = len(strat_wallets)
        if wallet_count >= 10:
            saturation = "HIGH (10+ wallets)"
            edge_status = "DECLINING"
        elif wallet_count >= 5:
            saturation = "MODERATE (5-9 wallets)"
            edge_status = "STABLE"
        else:
            saturation = "LOW (<5 wallets)"
            edge_status = "STRONG"

        # Determine overall verdict
        if build_count >= len(strat_wallets) * 0.6 and avg_score >= 7:
            verdict = "BUILD BOT"
            verdict_reason = "High success rate, replicable"
        elif build_count >= len(strat_wallets) * 0.4:
            verdict = "MONITOR"
            verdict_reason = "Promising but needs more validation"
        else:
            verdict = "SKIP"
            verdict_reason = "Low replicability or saturated"

        # Resolution speed
        resolution_mins = STRATEGY_RESOLUTION_MINUTES.get(strategy, 60 * 24)
        if resolution_mins <= 15:
            speed = "FAST (15 min)"
        elif resolution_mins <= 180:
            speed = "MEDIUM (hours)"
        else:
            speed = "SLOW (days)"

        # Format report
        strategy_name = {
            STRATEGY_BINANCE_SIGNAL: "Binance 15-min Arbitrage",
            STRATEGY_SPREAD_CAPTURE: "Spread Capture (YES+NO)",
            STRATEGY_SPORTS: "Sports Betting Edge",
            STRATEGY_POLITICAL: "Political Markets",
            STRATEGY_NEW_MARKET_SNIPER: "New Market Sniping",
            STRATEGY_UNKNOWN: "Unknown Strategy",
        }.get(strategy, strategy)

        report = f"""STRATEGY REPORT: {strategy_name}

THE EDGE
{explanation['edge']}

HOW IT WORKS
{explanation['how']}

PROOF ({wallet_count} wallets)
Combined profit: ${total_profit:,.0f}
Avg monthly ROI: {avg_roi:.0f}%
Replicability: {avg_score:.0f}/10
Resolution: {speed}

COMPETITION
Saturation: {saturation}
Edge status: {edge_status}

REQUIREMENTS
{explanation['requirements']}
Risk: {explanation['risk']}

VERDICT: {verdict}
{verdict_reason}"""

        # Add common markets if available
        if common_markets:
            markets_str = "\n".join([f"  - {m[0][:40]}..." for m in common_markets])
            report += f"\n\nTOP MARKETS:\n{markets_str}"

        reports.append(report)

    return reports


def calculate_priority_score(strategy_params: dict, profit: dict) -> float:
    """
    Calculate overall priority score for sorting.
    Higher = should be shown first (fast profit opportunities).

    Formula: (compounding_potential * monthly_roi) / 100

    This prioritizes:
    1. Fast resolution (more compounding)
    2. High ROI
    """
    strategy = strategy_params.get("likely_strategy", STRATEGY_UNKNOWN)
    daily_compounds = get_daily_compounds(strategy)
    monthly_roi = profit.get("monthly_roi_pct", 0)

    # Base priority from compounding * ROI
    priority = (daily_compounds * monthly_roi) / 100

    # Bonus for fast-resolution strategies (15-min markets)
    if strategy in FAST_RESOLUTION_STRATEGIES:
        priority *= 2  # Double priority for 15-min markets

    return round(priority, 2)


async def send_telegram(message: str, is_wallet_alert: bool = False):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[TG] Not configured")
        return

    if is_wallet_alert and not ENABLE_WALLET_ALERTS:
        log("[TG] Wallet alerts disabled (ENABLE_WALLET_ALERTS=false)")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                log("[TG] Sent")
            else:
                log(f"[TG] Failed: {resp.status_code}")
    except Exception as e:
        log(f"[TG] Error: {e}")


def format_new_market_alert(opp: NewMarketOpportunity) -> str:
    """Format alert for newly detected market with mispricing."""
    prices_str = " / ".join(f"{o}: ${p:.2f}" for o, p in zip(opp.outcomes, opp.prices))

    return f"""NEW MARKET DETECTED

{opp.title}

PRICES
{prices_str}
Total: ${sum(opp.prices):.2f}

SIGNAL
Mispricing score: {opp.mispricing_score:.0%}
{opp.recommendation}

https://polymarket.com/event/{opp.slug}"""


def format_alert(wallet: dict) -> str:
    """Format compact profit-focused alert message."""
    strat = wallet.get("strategy_params", {})
    profit = wallet.get("profit_analysis", {})
    saturation = wallet.get("saturation", {})
    source = wallet.get("source", "leaderboard")

    strategy_name = strat.get("likely_strategy", "UNKNOWN")

    # Source tag
    source_tag = "X.COM" if source == "twitter" else "STRATEGY"

    # Speed indicator
    resolution_mins = wallet.get("resolution_mins", 1440)
    if resolution_mins <= 15:
        speed = "15min"
    elif resolution_mins <= 60:
        speed = "1hr"
    elif resolution_mins <= 180:
        speed = "3hr"
    else:
        speed = f"{resolution_mins // 60}h"

    # Format profit in k/M
    total_profit = wallet.get('total_profit', 0)
    if total_profit >= 1_000_000:
        profit_str = f"${total_profit / 1_000_000:.1f}M"
    elif total_profit >= 1_000:
        profit_str = f"${total_profit / 1_000:.0f}k"
    else:
        profit_str = f"${total_profit:.0f}"

    monthly_est = profit.get('our_monthly_estimate', 0)
    if monthly_est >= 1_000:
        monthly_str = f"${monthly_est / 1_000:.1f}k"
    else:
        monthly_str = f"${monthly_est:.0f}"

    capital = profit.get('min_capital_required', 0)
    if capital >= 1_000:
        capital_str = f"${capital / 1_000:.0f}k"
    else:
        capital_str = f"${capital:.0f}"

    # Build compact message
    address = wallet['address']
    pattern = "Arb" if strat.get('is_arb_pattern') else "Directional"
    wallet_count = saturation.get('wallet_count', 0)
    trend = saturation.get('trend', 'unknown')
    account_age = wallet.get('account_age_days', 0)

    # Extract rules from blueprint if available
    blueprint = wallet.get("blueprint")
    rules_section = ""
    if blueprint:
        entry_rules = []
        for r in blueprint.entry_rules[:3]:  # Top 3 entry rules
            entry_rules.append(f"  - {r.condition}: {r.value} ({r.confidence:.0%})")
        exit_rules = []
        for r in blueprint.exit_rules[:2]:  # Top 2 exit rules
            exit_rules.append(f"  - {r.condition}: {r.value} ({r.confidence:.0%})")

        if entry_rules or exit_rules:
            rules_section = "\n\nRULES EXTRACTED:"
            if entry_rules:
                rules_section += "\nEntry:\n" + "\n".join(entry_rules)
            if exit_rules:
                rules_section += "\nExit:\n" + "\n".join(exit_rules)

    msg = f"""{source_tag}: {strategy_name}

{profit_str} profit | {account_age}d old | {speed} res
${strat.get('avg_trade_size', 0):.0f}/trade | {pattern}

Est: {monthly_str}/mo @ {capital_str} ({profit.get('monthly_roi_pct', 0):.0f}% ROI)
Competition: {wallet_count} wallets ({trend}){rules_section}

polymarket.com/profile/{address[:8]}...{address[-4:]}"""

    return msg


def format_sportsbook_alert(opp: SportsbookOpportunity, validation: ValidationResult) -> str:
    """Format verified sportsbook opportunity alert."""
    # Format liquidity
    liq = validation.liquidity_usd
    if liq >= 1_000:
        liq_str = f"${liq / 1_000:.0f}k"
    else:
        liq_str = f"${liq:.0f}"

    # Calculate ROI
    roi_pct = (validation.expected_profit / 500) * 100 if validation.expected_profit > 0 else 0

    # Format date compactly
    res_date = opp.resolution_time.strftime('%b %d')

    msg = f"""EDGE: {opp.action} {opp.outcome} @ {opp.pm_price:.0%} (fair: {opp.sb_price:.0%})

{opp.edge_pct:+.0f}% edge | {liq_str} liq | {validation.slippage_pct:.1f}% slip
$500 -> ${validation.expected_profit:.0f} profit ({roi_pct:.0f}% ROI)

{opp.event_title} | {opp.sport} | {res_date}

polymarket.com/event/{opp.market_slug}"""

    return msg


async def analyze_wallet(
    scanner: WalletScanner,
    address: str,
    leaderboard_profit: float,
    leaderboard: list,
    saturation_history: dict
) -> dict | None:
    """
    Full due diligence on a wallet:
    1. Check recency (skip if inactive >7 days)
    2. Deep strategy analysis (strategy-agnostic)
    3. Saturation analysis (find competitors)
    4. Profit potential (estimate OUR ROI)
    5. Replicability score

    Only returns if replicability >= MIN_REPLICABILITY_SCORE
    """
    try:
        # Check cache first
        activity = get_cached_activity(address)
        if activity is None:
            url = f"{scanner.BASE_URL}/activity"
            activity = await scanner._request("GET", url, {"user": address, "limit": 500})
            if activity:
                set_cached_activity(address, activity)

        if not activity or len(activity) < 10:
            return None

        # === 1. RECENCY CHECK ===
        is_active, hours_since_trade = check_recency(activity, max_inactive_hours=168)
        if not is_active:
            log(f"  Skip {address[:12]}... (inactive {hours_since_trade:.0f}h)")
            return None

        # Calculate basic metrics
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

        # === 2. DEEP STRATEGY ANALYSIS ===
        strategy_params = analyze_strategy_deep(activity)
        strategy_name = strategy_params["likely_strategy"]

        # Resolution-based filtering
        if FAST_ONLY_MODE:
            # Strict mode: ONLY 15-min crypto strategies (96 compounds/day)
            if strategy_name not in FAST_RESOLUTION_STRATEGIES:
                log(f"  Skip {address[:12]}... (not fast: {strategy_name})")
                return None
        else:
            # Normal mode: Skip SLOW strategies (political), allow fast + medium
            allowed = FAST_RESOLUTION_STRATEGIES | MEDIUM_RESOLUTION_STRATEGIES | {STRATEGY_UNKNOWN}
            if strategy_name in SLOW_RESOLUTION_STRATEGIES:
                log(f"  Skip {address[:12]}... (too slow: {strategy_name})")
                return None

        # === 3. SATURATION ANALYSIS ===
        saturation = await find_similar_wallets(
            scanner,
            address,
            strategy_params,
            leaderboard,
            max_wallets_to_check=30
        )

        # Update saturation trend
        strategy_name = strategy_params["likely_strategy"]
        trend = update_saturation_trend(
            saturation_history,
            strategy_name,
            saturation["wallet_count"],
            saturation["total_competing_capital"]
        )
        saturation["trend"] = trend

        # === 4. PROFIT POTENTIAL ANALYSIS ===
        profit_analysis = analyze_profit_potential(
            leaderboard_profit,
            account_age_days,
            strategy_params,
            saturation
        )

        # === 5. REPLICABILITY SCORE ===
        replicability_score = calculate_replicability(
            strategy_params,
            saturation,
            profit_analysis
        )

        # Only return if meets threshold
        if replicability_score < MIN_REPLICABILITY_SCORE:
            log(f"  Skip {address[:12]}... (replicability {replicability_score}/10 < {MIN_REPLICABILITY_SCORE})")
            return None

        # === 6. REVERSE ENGINEERING - Extract actual trading rules ===
        try:
            trades, wallet_profile, wallet_analysis = convert_to_reverse_types(
                address, activity, leaderboard_profit, account_age_days
            )
            reverser = StrategyReverser(min_confidence=0.6, min_evidence=5)
            blueprint = reverser.reverse_engineer(wallet_profile, trades, wallet_analysis)

            # Validate blueprint has quality rules
            entry_confidence = max([r.confidence for r in blueprint.entry_rules], default=0)
            total_rules = len(blueprint.entry_rules) + len(blueprint.exit_rules)

            if entry_confidence < 0.5 or total_rules < 2:
                log(f"  Skip {address[:12]}... (weak rules: {total_rules} rules, {entry_confidence:.0%} confidence)")
                return None

            log(f"  Reverse engineered: {len(blueprint.entry_rules)} entry, {len(blueprint.exit_rules)} exit rules")
        except Exception as e:
            log(f"  Skip {address[:12]}... (reverse engineering failed: {e})")
            return None

        # === 7. PRIORITY SCORE (for sorting by fast profit potential) ===
        priority_score = calculate_priority_score(strategy_params, profit_analysis)

        # Get resolution info for display
        strategy_name = strategy_params["likely_strategy"]
        resolution_mins = STRATEGY_RESOLUTION_MINUTES.get(strategy_name, 1440)
        daily_compounds = get_daily_compounds(strategy_name)
        is_fast = strategy_name in FAST_RESOLUTION_STRATEGIES

        return {
            "address": address,
            "account_age_days": account_age_days,
            "velocity": velocity,
            "trades_this_week": trades_this_week,
            "total_profit": leaderboard_profit,
            "hours_since_trade": hours_since_trade,

            # New comprehensive analysis
            "strategy_params": strategy_params,
            "saturation": saturation,
            "profit_analysis": profit_analysis,
            "replicability_score": replicability_score,

            # Reverse engineered blueprint
            "blueprint": blueprint,

            # Priority for sorting (fast profit first)
            "priority_score": priority_score,
            "resolution_mins": resolution_mins,
            "daily_compounds": daily_compounds,
            "is_fast_resolution": is_fast,
        }

    except Exception as e:
        log(f"  Error analyzing {address[:12]}: {e}")
        return None


async def run_leaderboard_scan(saturation_history: dict) -> list[dict]:
    """Scan leaderboard for profitable, replicable strategies."""
    log(f"[LEADERBOARD] Scanning...")

    async with WalletScanner() as scanner:
        log("  Fetching leaderboards...")

        leaderboard_all = await scanner.fetch_leaderboard(limit=200, period="all")
        await asyncio.sleep(0.5)
        leaderboard_week = await scanner.fetch_leaderboard(limit=200, period="week")

        # Combine leaderboards for candidate selection
        all_candidates = {}
        for p in leaderboard_all:
            if p.profit >= MIN_LEADERBOARD_PROFIT:
                all_candidates[p.address] = p
        for p in leaderboard_week:
            if p.address not in all_candidates and p.profit >= MIN_LEADERBOARD_PROFIT / 2:
                all_candidates[p.address] = p

        # Also need full leaderboard for saturation analysis
        full_leaderboard = list(leaderboard_all) + [p for p in leaderboard_week if p.address not in {x.address for x in leaderboard_all}]

        log(f"  {len(all_candidates)} candidates")

        sorted_candidates = sorted(all_candidates.values(), key=lambda x: x.profit, reverse=True)[:100]

        # Parallel analysis with semaphore for rate limiting
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_WALLETS)

        async def analyze_with_limit(candidate):
            async with semaphore:
                return await analyze_wallet(
                    scanner,
                    candidate.address,
                    candidate.profit,
                    full_leaderboard,
                    saturation_history
                )

        # Run all analyses in parallel
        log(f"  Analyzing {len(sorted_candidates)} wallets in parallel (max {MAX_CONCURRENT_WALLETS} concurrent)...")
        all_results = await asyncio.gather(*[analyze_with_limit(c) for c in sorted_candidates], return_exceptions=True)

        # Filter and log results
        results = []
        for candidate, result in zip(sorted_candidates, all_results):
            if isinstance(result, Exception):
                continue  # Skip failed analyses
            if result:
                strat = result["strategy_params"]["likely_strategy"]
                profit = result["profit_analysis"]
                score = result["replicability_score"]
                priority = result["priority_score"]
                fast = "[FAST]" if result["is_fast_resolution"] else ""
                log(f"  + {strat}: {candidate.address[:12]}... "
                    f"ROI={profit['monthly_roi_pct']:.0f}%/mo, "
                    f"score={score}/10, "
                    f"priority={priority}, "
                    f"{fast}")
                results.append(result)

        # Sort by priority (highest first = fastest profit potential)
        results.sort(key=lambda x: x["priority_score"], reverse=True)

        # Log summary by speed
        fast_count = sum(1 for r in results if r["is_fast_resolution"])
        slow_count = len(results) - fast_count

        log(f"[LEADERBOARD] Checked {len(sorted_candidates)}, found {len(results)} profitable strategies")
        log(f"  -> {fast_count} FAST (15-min), {slow_count} slower")
        return results


async def run_sportsbook_scan(validator: EdgeValidator) -> list[tuple[SportsbookOpportunity, ValidationResult]]:
    """Scan sportsbooks for PM mispricings and validate."""
    log(f"[SPORTSBOOK] Scanning...")

    validated_opps = []

    try:
        async with SportsbookComparator() as comparator:
            opportunities = await comparator.scan_all()

            log(f"[SPORTSBOOK] Found {len(opportunities)} raw opportunities")

            for opp in opportunities:
                # Paper trade ALL raw edges for win rate tracking (regardless of validation)
                edge_pct = abs(opp.sb_price - opp.pm_price) * 100
                if edge_pct >= 3.0:  # Minimum 3% edge
                    try:
                        portfolio = load_portfolio()
                        paper_trade_sports_edge(
                            portfolio=portfolio,
                            market_slug=opp.market_slug,
                            team=opp.outcome,
                            pm_price=opp.pm_price,
                            vegas_prob=opp.sb_price
                        )
                        save_portfolio(portfolio)
                        log(f"[PAPER] Tracked: {opp.outcome} {opp.action} @ {opp.pm_price:.1%} (edge={edge_pct:+.1f}%)")
                    except Exception as pt_error:
                        log(f"[PAPER] Error: {pt_error}")

                # Also validate for Telegram alerts (separate from paper tracking)
                validation = await validator.validate_opportunity(
                    market_slug=opp.market_slug,
                    outcome=opp.outcome,
                    pm_price=opp.pm_price,
                    fair_value=opp.sb_price,
                    order_size_usd=500
                )

                if validation.is_valid:
                    log(f"[SPORTSBOOK] VALID: {opp.outcome} {opp.action} @ {opp.pm_price:.1%} "
                        f"(edge={validation.edge_pct:+.1f}%, profit=${validation.expected_profit:.2f})")
                    validated_opps.append((opp, validation))

    except Exception as e:
        log(f"[SPORTSBOOK] Error: {e}")

    log(f"[SPORTSBOOK] {len(validated_opps)} validated opportunities")
    return validated_opps


async def run_twitter_scan(saturation_history: dict, seen_wallets: set) -> list[dict]:
    """Scan X.com for wallet addresses and analyze them through existing pipeline."""
    log(f"[TWITTER] Scanning for wallets...")

    results = []

    try:
        async with TwitterScanner() as scanner:
            signals = await scanner.scan_all()
            log(f"[TWITTER] Found {len(signals)} signals")

            # Extract unique wallet addresses
            wallets_found = set()
            for signal in signals:
                if signal.wallet_address:
                    wallets_found.add(signal.wallet_address.lower())

            log(f"[TWITTER] Found {len(wallets_found)} unique wallets")

            if not wallets_found:
                return results

            # Analyze each wallet through existing pipeline
            async with WalletScanner() as wallet_scanner:
                # Fetch leaderboard for saturation analysis
                leaderboard = await wallet_scanner.fetch_leaderboard(limit=100, period="week")

                for address in wallets_found:
                    if address in seen_wallets:
                        log(f"[TWITTER] Skipping {address[:12]}... (already seen)")
                        continue

                    # Get wallet profit from profile
                    try:
                        profile = await wallet_scanner.get_wallet_profile(address)
                        if not profile:
                            log(f"[TWITTER] Skipping {address[:12]}... (no profile)")
                            continue
                        if profile.profit < 500:  # Min $500 profit
                            log(f"[TWITTER] Skipping {address[:12]}... (profit ${profile.profit:.0f} < $500)")
                            continue
                        wallet_profit = profile.profit
                    except Exception as e:
                        log(f"[TWITTER] Error fetching profile {address[:12]}: {e}")
                        continue

                    # Run through existing wallet analysis pipeline
                    result = await analyze_wallet(
                        wallet_scanner,
                        address,
                        wallet_profit,
                        leaderboard,
                        saturation_history
                    )

                    if result:
                        result["source"] = "twitter"
                        log(f"[TWITTER] PROFITABLE: {address[:12]}... "
                            f"ROI={result['profit_analysis']['monthly_roi_pct']:.0f}%/mo, "
                            f"score={result['replicability_score']}/10")
                        results.append(result)

                    await asyncio.sleep(0.5)  # Rate limiting

    except Exception as e:
        log(f"[TWITTER] Error: {e}")
        import traceback
        traceback.print_exc()

    log(f"[TWITTER] {len(results)} profitable wallets found")
    return results


async def run_blockchain_scan() -> list:
    """Scan Polygon blockchain for smart money wallets."""
    log(f"[BLOCKCHAIN] Scanning for smart money...")

    results = []

    try:
        scanner = BlockchainScanner(POLYGON_RPC_URL)

        # Find wallets meeting smart money criteria
        smart_wallets = await scanner.find_smart_money()

        for wallet in smart_wallets:
            log(f"[BLOCKCHAIN] FOUND: {wallet.address[:12]}... "
                f"${wallet.portfolio_value_usd:,.0f}, {wallet.win_rate:.0%} WR, "
                f"{wallet.growth_30d_pct:+.0f}% 30d")
            results.append(wallet)

        await scanner.close()

    except Exception as e:
        log(f"[BLOCKCHAIN] Error: {e}")
        import traceback
        traceback.print_exc()

    log(f"[BLOCKCHAIN] {len(results)} smart money wallets found")
    return results


async def run_longshot_scan() -> list[LongshotOpportunity]:
    """Scan for planktonXD-style long-shot opportunities."""
    log(f"[LONGSHOT] Scanning for <5¢ opportunities...")

    results = []

    try:
        scanner = LongshotScanner()

        # Get near-term opportunities (resolving within 7 days)
        opps = await scanner.get_top_opportunities(limit=30)

        for opp in opps:
            cents = opp.price * 100
            log(f"[LONGSHOT] {cents:.1f}¢ → {opp.potential_return:.0f}x | {opp.outcome} | "
                f"{opp.days_until_resolution}d | ${opp.liquidity:,.0f} | [{opp.category}]")
            results.append(opp)

            # Paper trade top longshots with 10% portfolio limit
            if len(results) <= 5 and opp.price <= 0.01:  # Top 5 at <1¢
                try:
                    portfolio = load_portfolio()

                    # Calculate current longshot exposure
                    LONGSHOT_LIMIT = STRATEGY_BUDGET  # $1000 per strategy
                    longshot_exposure = sum(
                        p.get("cost_basis", 0) for p in portfolio.positions
                        if p.get("category") == "longshot" and p.get("status") == "open"
                    )

                    bet_size = LONGSHOT_BET_SIZE  # $50 per longshot

                    # Check if we're at the limit
                    if longshot_exposure >= LONGSHOT_LIMIT:
                        log(f"[PAPER] SKIP LONGSHOT: At limit (${longshot_exposure:.0f}/${LONGSHOT_LIMIT:.0f})")
                        continue

                    # Cap bet to stay within limit
                    remaining_budget = LONGSHOT_LIMIT - longshot_exposure
                    bet_size = min(bet_size, remaining_budget)

                    if portfolio.cash >= bet_size and bet_size >= 5:
                        shares = bet_size / opp.price
                        position = {
                            "market_slug": opp.question[:50],  # Use question as slug
                            "outcome": opp.outcome,
                            "entry_price": opp.price,
                            "shares": shares,
                            "cost_basis": bet_size,
                            "entry_time": datetime.now().isoformat(),
                            "edge_pct": opp.potential_return * 100,  # Store potential return
                            "kelly_fraction": 0.10,  # 10% allocation
                            "category": "longshot",
                            "fair_value": 0.0,  # Unknown
                            "potential_payout": shares,  # $1 per share if wins
                            "status": "open",
                            "resolution_value": None,
                            "pnl": None
                        }
                        portfolio.positions.append(position)
                        portfolio.cash -= bet_size
                        save_portfolio(portfolio)
                        log(f"[PAPER] LONGSHOT: ${bet_size} on {opp.outcome} @ {cents:.1f}¢ ({opp.potential_return:.0f}x potential)")
                except Exception as e:
                    log(f"[PAPER] Longshot error: {e}")

        await scanner.close()

    except Exception as e:
        log(f"[LONGSHOT] Error: {e}")
        import traceback
        traceback.print_exc()

    log(f"[LONGSHOT] Found {len(results)} long-shot opportunities")
    return results


async def run_weather_bucket_scan() -> list[BucketArbitrageOpportunity]:
    """Scan for 0xf2e346ab-style weather bucket arbitrage opportunities."""
    log(f"[WEATHER-BUCKET] Scanning for bucket arbitrage...")

    results = []

    try:
        scanner = WeatherBucketScanner()
        opps = await scanner.scan()

        for opp in opps:
            # Calculate actual ROI (edge / cost)
            if opp.arb_type == "SUM_UNDER":
                actual_roi = opp.edge / opp.total_cost if opp.total_cost > 0 else 0
            else:  # SUM_OVER - buying all NOs
                n = len(opp.brackets_to_buy)
                payout = (n - 1)  # All but one NO wins
                actual_roi = (payout - opp.total_cost) / opp.total_cost if opp.total_cost > 0 else 0

            log(f"[WEATHER-BUCKET] {opp.event.city}: {opp.arb_type} | "
                f"Edge={opp.edge*100:.1f}% | Cost=${opp.total_cost:.2f} | "
                f"ROI={actual_roi*100:.1f}% | Brackets={len(opp.brackets_to_buy)}")
            results.append(opp)

            # Paper trade weather bucket opportunities
            if actual_roi >= 0.01:  # Min 1% ROI
                try:
                    portfolio = load_portfolio()

                    # Calculate bet size ($100 per bracket for $1000 strategy budget)
                    bet_per_bracket = WEATHER_BUCKET_BET_PER_BRACKET
                    total_bet = bet_per_bracket * len(opp.brackets_to_buy)

                    if portfolio.cash >= total_bet:
                        position = {
                            "market_slug": f"weather_{opp.event.city}_{opp.event.date}",
                            "outcome": opp.arb_type,
                            "entry_price": opp.total_cost / len(opp.brackets_to_buy),
                            "shares": len(opp.brackets_to_buy),
                            "cost_basis": total_bet,
                            "entry_time": datetime.now().isoformat(),
                            "edge_pct": actual_roi * 100,
                            "kelly_fraction": 0.05,
                            "category": "weather_bucket",
                            "fair_value": 1.0 / len(opp.brackets_to_buy),
                            "potential_payout": total_bet * (1 + actual_roi),
                            "status": "open",
                            "resolution_value": None,
                            "pnl": None
                        }
                        portfolio.positions.append(position)
                        portfolio.cash -= total_bet
                        save_portfolio(portfolio)
                        log(f"[PAPER] WEATHER BUCKET: ${total_bet:.0f} on {opp.arb_type} @ {opp.event.city} "
                            f"({actual_roi*100:.1f}% ROI)")
                except Exception as e:
                    log(f"[PAPER] Weather bucket error: {e}")

        await scanner.close()

    except Exception as e:
        log(f"[WEATHER-BUCKET] Error: {e}")
        import traceback
        traceback.print_exc()

    log(f"[WEATHER-BUCKET] Found {len(results)} bucket arbitrage opportunities")
    return results


async def daemon_loop():
    log("=" * 60)
    log("  POLY-SCOUT v2: AUTONOMOUS PROFIT AGENT")
    log("=" * 60)
    log("  Goal: Find and validate profitable opportunities")
    log("")
    log("  Active Sources:")
    log("    - Sportsbook comparison (PM vs odds)")
    log("    - New market monitoring (mispricing detection)")
    log("    - Blockchain scan (smart money detection)")
    log("    - Longshot scan (planktonXD strategy - <5c markets)")
    log("    - Weather bucket scan (0xf2e346ab strategy - sum arbitrage)")
    log("")
    log("  Disabled (ENABLE_WALLET_ALERTS=false):")
    log("    - Leaderboard wallets")
    log("    - X.com/Twitter")
    log("")
    log("  Validation:")
    log(f"    - Min edge: {MIN_EDGE_PCT}%")
    log(f"    - Min liquidity: ${MIN_LIQUIDITY_USD:,}")
    log(f"    - Min profit: ${MIN_EXPECTED_PROFIT}")
    log("")
    log("  Scan intervals:")
    log(f"    - Leaderboard: {SCAN_INTERVAL_LEADERBOARD // 60} min")
    log(f"    - Sportsbook: {SCAN_INTERVAL_SPORTSBOOK // 60} min")
    log(f"    - Twitter: {SCAN_INTERVAL_TWITTER // 60} min")
    log(f"    - Blockchain: {SCAN_INTERVAL_BLOCKCHAIN // 60} min")
    log(f"    - Longshot: {SCAN_INTERVAL_LONGSHOT // 60} min")
    log(f"    - Weather Bucket: {SCAN_INTERVAL_WEATHER_BUCKET // 60} min")
    log(f"    - New Markets: {SCAN_INTERVAL_NEW_MARKETS}s")
    log(f"    - Scalp: {SCAN_INTERVAL_SCALP // 60} min")
    log("")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 60)

    seen_wallets = load_seen_wallets()
    seen_opportunities = load_seen_opportunities()
    saturation_history = load_saturation_history()
    log(f"Loaded {len(seen_wallets)} seen wallets, {len(seen_opportunities)} seen opportunities")

    await send_telegram("[POLY-SCOUT v2 STARTED]\n\nAutonomous profit hunting active.\n\nSources: Sportsbook + New Markets + Blockchain\nValidation: Edge > 3%, Liquidity > $1k")

    # Track last scan times
    last_leaderboard_scan = 0
    last_sportsbook_scan = 0
    last_twitter_scan = 0
    last_blockchain_scan = 0
    last_longshot_scan = 0
    last_new_market_scan = 0
    last_scalp_scan = 0
    last_weather_bucket_scan = 0

    # Create validator for all sources
    validator = EdgeValidator()

    # Create new market monitor
    new_market_monitor = NewMarketMonitor()

    while True:
        try:
            now = datetime.now().timestamp()
            alerts_sent = 0

            # === PARALLEL SCAN EXECUTION ===
            # Collect all due scans and run them concurrently
            async def scan_sportsbook():
                nonlocal last_sportsbook_scan, alerts_sent
                if now - last_sportsbook_scan >= SCAN_INTERVAL_SPORTSBOOK:
                    sportsbook_opps = await run_sportsbook_scan(validator)
                    for opp, validation in sportsbook_opps:
                        opp_id = f"sb:{opp.market_slug}:{opp.outcome}"
                        if opp_id not in seen_opportunities:
                            await send_telegram(format_sportsbook_alert(opp, validation))
                            seen_opportunities.add(opp_id)
                            alerts_sent += 1
                    save_seen_opportunities(seen_opportunities)
                    last_sportsbook_scan = now

            async def scan_new_markets():
                nonlocal last_new_market_scan
                if now - last_new_market_scan >= SCAN_INTERVAL_NEW_MARKETS:
                    try:
                        await new_market_monitor.scan_for_new_markets()
                    except Exception as e:
                        log(f"[NEW MARKETS] Error: {e}")
                    last_new_market_scan = now

            async def scan_scalp():
                nonlocal last_scalp_scan
                if now - last_scalp_scan >= SCAN_INTERVAL_SCALP:
                    try:
                        scalp_scan_once()
                    except Exception as e:
                        log(f"[SCALP] Scan error: {e}")
                    last_scalp_scan = now

            async def scan_longshot():
                nonlocal last_longshot_scan, alerts_sent
                if now - last_longshot_scan >= SCAN_INTERVAL_LONGSHOT:
                    try:
                        longshot_opps = await run_longshot_scan()
                        if longshot_opps:
                            await send_longshot_alert(longshot_opps)
                            alerts_sent += 1
                    except Exception as e:
                        log(f"[LONGSHOT] Scan error: {e}")
                    last_longshot_scan = now

            async def scan_weather_bucket():
                nonlocal last_weather_bucket_scan
                if now - last_weather_bucket_scan >= SCAN_INTERVAL_WEATHER_BUCKET:
                    try:
                        await run_weather_bucket_scan()
                    except Exception as e:
                        log(f"[WEATHER-BUCKET] Scan error: {e}")
                    last_weather_bucket_scan = now

            async def scan_blockchain():
                nonlocal last_blockchain_scan, alerts_sent
                if now - last_blockchain_scan >= SCAN_INTERVAL_BLOCKCHAIN:
                    try:
                        # Add 5-minute timeout to prevent blocking
                        blockchain_wallets = await asyncio.wait_for(
                            run_blockchain_scan(),
                            timeout=300  # 5 minute timeout
                        )
                        for wallet in blockchain_wallets:
                            await send_telegram(wallet.to_telegram_message(), is_wallet_alert=False)
                            alerts_sent += 1
                    except asyncio.TimeoutError:
                        log(f"[BLOCKCHAIN] Scan timed out after 5 minutes")
                    except Exception as e:
                        log(f"[BLOCKCHAIN] Scan error: {e}")
                    last_blockchain_scan = now

            async def scan_leaderboard():
                nonlocal last_leaderboard_scan, alerts_sent
                if now - last_leaderboard_scan >= SCAN_INTERVAL_LEADERBOARD:
                    results = await run_leaderboard_scan(saturation_history)
                    save_saturation_history(saturation_history)
                    new_wallets = [w for w in results if w["address"] not in seen_wallets]
                    if new_wallets:
                        log(f"[ALERT] {len(new_wallets)} NEW profitable strategy(ies)!")
                        for wallet in new_wallets:
                            await send_telegram(format_alert(wallet), is_wallet_alert=True)
                            seen_wallets.add(wallet["address"])
                            alerts_sent += 1
                        save_seen_wallets(seen_wallets)
                    strategy_reports = generate_strategy_report(results)
                    if strategy_reports:
                        log(f"[STRATEGY] Sending {len(strategy_reports)} strategy reports")
                        for report in strategy_reports:
                            await send_telegram(report, is_wallet_alert=True)
                            alerts_sent += 1
                    last_leaderboard_scan = now

            async def scan_twitter():
                nonlocal last_twitter_scan, alerts_sent
                if now - last_twitter_scan >= SCAN_INTERVAL_TWITTER:
                    twitter_wallets = await run_twitter_scan(saturation_history, seen_wallets)
                    for wallet in twitter_wallets:
                        if wallet["address"] not in seen_wallets:
                            await send_telegram(format_alert(wallet), is_wallet_alert=True)
                            seen_wallets.add(wallet["address"])
                            alerts_sent += 1
                    save_seen_wallets(seen_wallets)
                    last_twitter_scan = now

            # Run ALL scans in parallel - fast scans won't be blocked by slow ones
            log("[PARALLEL] Running all due scans concurrently...")
            await asyncio.gather(
                scan_sportsbook(),
                scan_new_markets(),
                scan_scalp(),
                scan_longshot(),
                scan_weather_bucket(),
                scan_blockchain(),
                scan_leaderboard(),
                scan_twitter(),
                return_exceptions=True  # Don't fail all if one fails
            )

            # Summary
            if alerts_sent > 0:
                log(f"[SUMMARY] Sent {alerts_sent} alerts")
            else:
                log(f"[SUMMARY] No new opportunities")

        except Exception as e:
            log(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        # Calculate time to next scan
        next_scans = []
        if last_leaderboard_scan > 0:
            next_scans.append(("Leaderboard", SCAN_INTERVAL_LEADERBOARD - (datetime.now().timestamp() - last_leaderboard_scan)))
        if last_sportsbook_scan > 0:
            next_scans.append(("Sportsbook", SCAN_INTERVAL_SPORTSBOOK - (datetime.now().timestamp() - last_sportsbook_scan)))
        if last_twitter_scan > 0:
            next_scans.append(("Twitter", SCAN_INTERVAL_TWITTER - (datetime.now().timestamp() - last_twitter_scan)))
        if last_blockchain_scan > 0:
            next_scans.append(("Blockchain", SCAN_INTERVAL_BLOCKCHAIN - (datetime.now().timestamp() - last_blockchain_scan)))
        if last_longshot_scan > 0:
            next_scans.append(("Longshot", SCAN_INTERVAL_LONGSHOT - (datetime.now().timestamp() - last_longshot_scan)))
        if last_new_market_scan > 0:
            next_scans.append(("New Markets", SCAN_INTERVAL_NEW_MARKETS - (datetime.now().timestamp() - last_new_market_scan)))
        if last_scalp_scan > 0:
            next_scans.append(("Scalp", SCAN_INTERVAL_SCALP - (datetime.now().timestamp() - last_scalp_scan)))
        if last_weather_bucket_scan > 0:
            next_scans.append(("Weather Bucket", SCAN_INTERVAL_WEATHER_BUCKET - (datetime.now().timestamp() - last_weather_bucket_scan)))

        # Wait until next scan is due
        if next_scans:
            next_scan_time = min(max(0, t[1]) for t in next_scans)
            log(f"Next scan in {int(next_scan_time)}s...")
            await asyncio.sleep(max(30, next_scan_time))  # At least 30s between loops
        else:
            await asyncio.sleep(60)


def main():
    try:
        asyncio.run(daemon_loop())
    except KeyboardInterrupt:
        log("Stopped.")


if __name__ == "__main__":
    main()
