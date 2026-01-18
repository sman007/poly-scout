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

from src.scanner import WalletScanner, WalletProfile, find_similar_wallets, update_saturation_trend

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
STRATEGY_BINANCE_SIGNAL = "BINANCE_SIGNAL"  # Directional trading based on Binance price moves
STRATEGY_SPREAD_CAPTURE = "SPREAD_CAPTURE"  # Buy YES+NO < $1, profit on resolution
STRATEGY_SPORTS = "SPORTS"
STRATEGY_POLITICAL = "POLITICAL"
STRATEGY_MARKET_MAKER = "MARKET_MAKER"
STRATEGY_MIXED = "MIXED"
STRATEGY_UNKNOWN = "UNKNOWN"

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
SATURATION_HISTORY_FILE = Path("/root/poly-scout/data/saturation_history.json")


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


def load_saturation_history() -> dict:
    """Load saturation history for trend tracking."""
    if SATURATION_HISTORY_FILE.exists():
        try:
            with open(SATURATION_HISTORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_saturation_history(history: dict):
    """Save saturation history."""
    SATURATION_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SATURATION_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


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

    # BINANCE_SIGNAL: Combined avg > $1, high crypto 15m focus, directional
    if combined_avg > 1.0 and crypto_15m_pct > 0.5:
        likely_strategy = STRATEGY_BINANCE_SIGNAL
        confidence = min(0.5 + (combined_avg - 1.0) * 2 + crypto_15m_pct * 0.3, 0.95)
        edge_explanation = "Binance price moves before Polymarket odds adjust"

    # SPREAD_CAPTURE: Combined avg < $1, buying both sides
    elif combined_avg > 0 and combined_avg < 1.0 and yes_prices and no_prices:
        likely_strategy = STRATEGY_SPREAD_CAPTURE
        confidence = min(0.5 + (1.0 - combined_avg) * 2, 0.95)
        edge_explanation = "Buy YES+NO < $1, guaranteed profit on resolution"

    # Check for other patterns (sports, political)
    elif crypto_15m_pct < 0.3:
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


async def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("[TG] Not configured")
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


def format_alert(wallet: dict) -> str:
    """Format profit-focused alert message."""
    strat = wallet.get("strategy_params", {})
    profit = wallet.get("profit_analysis", {})
    saturation = wallet.get("saturation", {})
    replicability = wallet.get("replicability_score", 0)
    priority = wallet.get("priority_score", 0)
    resolution_mins = wallet.get("resolution_mins", 1440)
    daily_compounds = wallet.get("daily_compounds", 1)
    is_fast = wallet.get("is_fast_resolution", False)

    strategy_name = strat.get("likely_strategy", "UNKNOWN")
    emoji = STRATEGY_EMOJI.get(strategy_name, "")

    # Speed indicator
    if is_fast:
        speed_tag = "[FAST PROFIT]"
        resolution_str = f"{resolution_mins} min"
    elif resolution_mins < 60:
        speed_tag = "[QUICK]"
        resolution_str = f"{resolution_mins} min"
    elif resolution_mins < 1440:
        speed_tag = ""
        resolution_str = f"{resolution_mins // 60}h"
    else:
        speed_tag = "[SLOW]"
        resolution_str = f"{resolution_mins // 1440}d"

    verdict_emoji = "+" if profit.get("verdict") == "BUILD" else "-"

    # Format top markets
    top_markets = strat.get('top_markets', [])
    top_markets_str = "\n".join([f"  - ${v:,.0f}: {k}" for k, v in top_markets[:3]]) if top_markets else "  (none)"

    # Trading pattern
    is_arb = strat.get('is_arb_pattern', False)
    yes_no = strat.get('yes_no_ratio', 1)
    pattern = "ARB (both sides)" if is_arb else f"DIRECTIONAL (YES/NO: {yes_no:.1f})"

    msg = f"""{speed_tag} PROFITABLE STRATEGY

SPEED (capital turnover)
Resolution: {resolution_str}
Compounds: {daily_compounds:.0f}x/day
Priority: {priority}

PROFIT
Their daily: ${profit.get('their_daily_profit', 0):,.0f}/day
Our estimate: ${profit.get('our_daily_estimate', 0):,.0f}/day
Monthly: ${profit.get('our_monthly_estimate', 0):,.0f}
Verdict: {profit.get('verdict', 'SKIP')} {verdict_emoji}

STRATEGY
Type: {emoji} {strategy_name}
Pattern: {pattern}
Edge: {strat.get('edge_explanation', 'Unknown')}

TOP MARKETS
{top_markets_str}

PARAMETERS
- Avg size: ${strat.get('avg_trade_size', 0):.0f}
- Frequency: {strat.get('trades_per_hour', 0):.0f}/hour
- Capital needed: ~${profit.get('min_capital_required', 0):,.0f}
- Monthly ROI: {profit.get('monthly_roi_pct', 0):.0f}%

SATURATION
- Competitors: {saturation.get('wallet_count', 0)}
- Trend: {saturation.get('trend', 'unknown').upper()}

SOURCE
{wallet['address'][:16]}...
${wallet['total_profit']:,.0f} profit | {wallet.get('hours_since_trade', 0):.0f}h ago | {replicability}/10

https://polymarket.com/profile/{wallet['address']}"""

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
        url = f"{scanner.BASE_URL}/activity"
        activity = await scanner._request("GET", url, {"user": address, "limit": 500})

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

        # === 6. PRIORITY SCORE (for sorting by fast profit potential) ===
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

            # Priority for sorting (fast profit first)
            "priority_score": priority_score,
            "resolution_mins": resolution_mins,
            "daily_compounds": daily_compounds,
            "is_fast_resolution": is_fast,
        }

    except Exception as e:
        log(f"  Error analyzing {address[:12]}: {e}")
        return None


async def run_scan(saturation_history: dict) -> list[dict]:
    """Scan for profitable, replicable strategies."""
    log(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning...")

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

        results = []
        checked = 0

        sorted_candidates = sorted(all_candidates.values(), key=lambda x: x.profit, reverse=True)

        for candidate in sorted_candidates[:100]:
            checked += 1

            result = await analyze_wallet(
                scanner,
                candidate.address,
                candidate.profit,
                full_leaderboard,
                saturation_history
            )

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

            await asyncio.sleep(0.5)

        # Sort by priority (highest first = fastest profit potential)
        results.sort(key=lambda x: x["priority_score"], reverse=True)

        # Log summary by speed
        fast_count = sum(1 for r in results if r["is_fast_resolution"])
        slow_count = len(results) - fast_count

        log(f"  Checked {checked}, found {len(results)} profitable strategies")
        log(f"  -> {fast_count} FAST (15-min), {slow_count} slower")
        return results


async def daemon_loop():
    log("=" * 60)
    log("  POLY-SCOUT: PROFIT HUNTER")
    log("=" * 60)
    log("  Goal: Find profitable, replicable trading strategies")
    log("")
    log("  Filters:")
    log(f"    - Account <= {MAX_ACCOUNT_AGE_DAYS} days old")
    log(f"    - Velocity >= ${MIN_VELOCITY:,.0f}/day")
    log(f"    - Trades/week >= {MIN_TRADES_WEEK}")
    log(f"    - Replicability >= {MIN_REPLICABILITY_SCORE}/10")
    log(f"    - Monthly ROI >= {MIN_MONTHLY_ROI_PCT}%")
    log("")
    log("  Strategies detected:")
    for strategy, emoji in STRATEGY_EMOJI.items():
        log(f"    - {emoji} {strategy}")
    log("")
    log(f"  Scan interval: {SCAN_INTERVAL_MINUTES} min")
    log(f"  Telegram: {'YES' if TELEGRAM_BOT_TOKEN else 'NO'}")
    log("=" * 60)

    seen_wallets = load_seen_wallets()
    saturation_history = load_saturation_history()
    log(f"Loaded {len(seen_wallets)} seen wallets, {len(saturation_history)} saturation records")

    await send_telegram("[POLY-SCOUT STARTED]\n\nHunting for profitable strategies...\nFilters: ROI >= 20%/mo, Replicability >= 6/10")

    while True:
        try:
            results = await run_scan(saturation_history)

            # Save saturation history after each scan
            save_saturation_history(saturation_history)

            new_wallets = [w for w in results if w["address"] not in seen_wallets]

            if new_wallets:
                log(f"[ALERT] {len(new_wallets)} NEW profitable strategy(ies)!")
                for wallet in new_wallets:
                    await send_telegram(format_alert(wallet))
                    seen_wallets.add(wallet["address"])
                save_seen_wallets(seen_wallets)
            else:
                log(f"No new strategies ({len(results)} passed filters, already seen or below threshold)")

        except Exception as e:
            log(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        log(f"Next scan in {SCAN_INTERVAL_MINUTES} min...")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)


def main():
    try:
        asyncio.run(daemon_loop())
    except KeyboardInterrupt:
        log("Stopped.")


if __name__ == "__main__":
    main()
