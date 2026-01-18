"""
Signal detection module for identifying anomalous wallet behavior.

This module detects patterns that indicate a wallet has found an edge in prediction
markets, such as profit spikes, statistically improbable win rates, and consistent
success. Used to identify alpha traders worth tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
import math

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# Type hints for external models (will be imported from other modules)
# These are placeholders - adjust to match actual data models
@dataclass
class Trade:
    """Placeholder for Trade model. Should match actual schema."""
    timestamp: datetime
    profit: float
    outcome: str  # 'win' or 'loss'
    market_id: str
    market_category: Optional[str] = None
    amount: float = 0.0


@dataclass
class WalletProfile:
    """Placeholder for WalletProfile model. Should match actual schema."""
    address: str
    first_seen: datetime
    total_profit: float
    total_trades: int
    win_rate: float
    avg_trade_size: float
    markets_traded: int


@dataclass
class Signal:
    """
    Represents a detected anomaly or edge signal.

    Attributes:
        signal_type: Type of signal detected (e.g., PROFIT_SPIKE, WIN_RATE_ANOMALY)
        strength: Signal strength from 0.0 (weak) to 1.0 (very strong)
        description: Human-readable description of what was detected
        evidence: Dictionary of supporting data and metrics
        timestamp: When the signal was detected
    """
    signal_type: str
    strength: float
    description: str
    evidence: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate signal strength is in valid range."""
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"Signal strength must be between 0.0 and 1.0, got {self.strength}")


class SignalDetector:
    """
    Detects anomalous wallet behavior indicating potential edge discovery.

    This class implements multiple signal detection methods that identify patterns
    characteristic of traders who have found an exploitable edge in the market.
    """

    # Signal type constants
    PROFIT_SPIKE = "PROFIT_SPIKE"
    WIN_RATE_ANOMALY = "WIN_RATE_ANOMALY"
    RAPID_GROWTH = "RAPID_GROWTH"
    MARKET_SPECIALIST = "MARKET_SPECIALIST"
    FREQUENCY_SPIKE = "FREQUENCY_SPIKE"
    CONSISTENT_EDGE = "CONSISTENT_EDGE"

    # Default thresholds
    DEFAULT_PROFIT_SPIKE_MULTIPLIER = 3.0
    DEFAULT_WIN_RATE_THRESHOLD = 0.90
    DEFAULT_WIN_RATE_MIN_TRADES = 100
    DEFAULT_NEW_WALLET_DAYS = 60
    DEFAULT_NEW_WALLET_MIN_PROFIT = 10000.0
    DEFAULT_SPECIALIST_THRESHOLD = 0.80
    DEFAULT_FREQUENCY_MULTIPLIER = 5.0
    DEFAULT_CONSISTENT_DAYS = 7

    def __init__(self):
        """Initialize the signal detector."""
        pass

    def detect_all_signals(
        self,
        wallet: WalletProfile,
        trades: list[Trade]
    ) -> list[Signal]:
        """
        Run all signal detection methods on a wallet and its trades.

        Args:
            wallet: Wallet profile with aggregate statistics
            trades: List of trades sorted by timestamp (newest first or oldest first)

        Returns:
            List of detected signals, sorted by strength (strongest first)
        """
        signals = []

        # Sort trades by timestamp to ensure consistent processing
        sorted_trades = sorted(trades, key=lambda t: t.timestamp)

        # Detect various signal types
        signal = self.profit_spike_signal(sorted_trades)
        if signal:
            signals.append(signal)

        signal = self.win_rate_anomaly_signal(wallet.win_rate, wallet.total_trades)
        if signal:
            signals.append(signal)

        signal = self.new_wallet_success_signal(wallet.first_seen, wallet.total_profit)
        if signal:
            signals.append(signal)

        # Calculate market distribution for concentration signal
        market_distribution = self._calculate_market_distribution(sorted_trades)
        signal = self.concentration_signal(market_distribution)
        if signal:
            signals.append(signal)

        signal = self.velocity_signal(sorted_trades)
        if signal:
            signals.append(signal)

        signal = self.consistent_edge_signal(sorted_trades)
        if signal:
            signals.append(signal)

        # Sort by strength (strongest first)
        signals.sort(key=lambda s: s.strength, reverse=True)

        return signals

    def profit_spike_signal(
        self,
        trades: list[Trade],
        threshold_multiplier: float = DEFAULT_PROFIT_SPIKE_MULTIPLIER
    ) -> Optional[Signal]:
        """
        Detect if 7-day profit significantly exceeds 30-day average.

        A sudden profit spike suggests the trader discovered a new edge or exploit.

        Args:
            trades: List of trades sorted by timestamp
            threshold_multiplier: How many times the average constitutes a spike

        Returns:
            Signal if spike detected, None otherwise
        """
        if len(trades) < 10:
            return None

        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # Calculate profits in different windows
        recent_profit = sum(t.profit for t in trades if t.timestamp >= seven_days_ago)
        thirty_day_profit = sum(t.profit for t in trades if t.timestamp >= thirty_days_ago)

        # Calculate 30-day daily average (excluding last 7 days)
        days_23_to_30 = [t for t in trades
                         if thirty_days_ago <= t.timestamp < seven_days_ago]

        if not days_23_to_30:
            return None

        avg_23_day_profit = sum(t.profit for t in days_23_to_30) / 23.0
        expected_7_day_profit = avg_23_day_profit * 7.0

        if expected_7_day_profit <= 0:
            expected_7_day_profit = 1.0  # Avoid division by zero

        spike_ratio = recent_profit / expected_7_day_profit

        if spike_ratio >= threshold_multiplier:
            # Strength scales with how much it exceeds threshold (cap at 1.0)
            strength = min(1.0, (spike_ratio - threshold_multiplier) / (threshold_multiplier * 2) + 0.7)

            return Signal(
                signal_type=self.PROFIT_SPIKE,
                strength=strength,
                description=f"7-day profit ${recent_profit:.2f} is {spike_ratio:.1f}x the 30-day average",
                evidence={
                    "recent_7d_profit": recent_profit,
                    "expected_7d_profit": expected_7_day_profit,
                    "spike_ratio": spike_ratio,
                    "threshold": threshold_multiplier,
                    "thirty_day_total": thirty_day_profit
                }
            )

        return None

    def win_rate_anomaly_signal(
        self,
        win_rate: float,
        trade_count: int,
        min_trades: int = DEFAULT_WIN_RATE_MIN_TRADES,
        threshold: float = DEFAULT_WIN_RATE_THRESHOLD
    ) -> Optional[Signal]:
        """
        Detect statistically improbable win rates.

        In prediction markets with fair odds, maintaining 90%+ win rate over many
        trades is extremely unlikely without an edge. Uses binomial test.

        Args:
            win_rate: Win rate as decimal (e.g., 0.92 for 92%)
            trade_count: Total number of trades
            min_trades: Minimum trades needed for statistical significance
            threshold: Win rate threshold for anomaly detection

        Returns:
            Signal if anomalous win rate detected, None otherwise
        """
        if trade_count < min_trades or win_rate < threshold:
            return None

        # Expected win rate for fair betting is ~50% (0.5)
        # Calculate probability of observing this win rate by chance
        wins = int(win_rate * trade_count)

        if SCIPY_AVAILABLE:
            # Use exact binomial test
            p_value = scipy_stats.binom_test(
                wins,
                trade_count,
                0.5,
                alternative='greater'
            )
        else:
            # Use normal approximation if scipy not available
            # Standard error = sqrt(n * p * (1-p))
            expected_wins = trade_count * 0.5
            std_error = math.sqrt(trade_count * 0.5 * 0.5)
            z_score = (wins - expected_wins) / std_error

            # Approximate p-value from z-score (one-tailed)
            # For large z-scores, p-value is very small
            p_value = 0.5 * math.erfc(z_score / math.sqrt(2))

        # Very small p-value indicates statistical anomaly
        if p_value < 0.01:  # 1% significance level
            # Strength based on how extreme the p-value is
            strength = min(1.0, 0.5 - math.log10(p_value) / 10)

            return Signal(
                signal_type=self.WIN_RATE_ANOMALY,
                strength=strength,
                description=f"{win_rate*100:.1f}% win rate over {trade_count} trades (p={p_value:.2e})",
                evidence={
                    "win_rate": win_rate,
                    "trade_count": trade_count,
                    "wins": wins,
                    "p_value": p_value,
                    "threshold": threshold,
                    "min_trades": min_trades
                }
            )

        return None

    def new_wallet_success_signal(
        self,
        first_seen: datetime,
        profit: float,
        max_age_days: int = DEFAULT_NEW_WALLET_DAYS,
        min_profit: float = DEFAULT_NEW_WALLET_MIN_PROFIT
    ) -> Optional[Signal]:
        """
        Detect new wallets with rapid profit growth.

        A wallet that's less than 60 days old but has already made $10k+ suggests
        the trader started with an edge rather than learned over time.

        Args:
            first_seen: When the wallet first appeared
            profit: Total profit accumulated
            max_age_days: Maximum age to be considered "new"
            min_profit: Minimum profit threshold for signal

        Returns:
            Signal if rapid growth detected, None otherwise
        """
        age_days = (datetime.utcnow() - first_seen).days

        if age_days >= max_age_days or profit < min_profit:
            return None

        # Daily profit rate
        daily_profit = profit / max(age_days, 1)

        # Strength based on profit magnitude and recency
        # Higher profit and newer wallet = stronger signal
        profit_score = min(1.0, profit / (min_profit * 5))
        recency_score = 1.0 - (age_days / max_age_days)
        strength = (profit_score + recency_score) / 2

        return Signal(
            signal_type=self.RAPID_GROWTH,
            strength=strength,
            description=f"${profit:.2f} profit in {age_days} days (${daily_profit:.2f}/day)",
            evidence={
                "age_days": age_days,
                "total_profit": profit,
                "daily_profit": daily_profit,
                "max_age_days": max_age_days,
                "min_profit_threshold": min_profit
            }
        )

    def concentration_signal(
        self,
        market_distribution: dict[str, float],
        threshold: float = DEFAULT_SPECIALIST_THRESHOLD
    ) -> Optional[Signal]:
        """
        Detect if trader specializes heavily in specific market category.

        High concentration (80%+ trades in one category) suggests domain expertise
        or category-specific edge.

        Args:
            market_distribution: Dict mapping category -> proportion of trades
            threshold: Minimum concentration to trigger signal

        Returns:
            Signal if specialist pattern detected, None otherwise
        """
        if not market_distribution:
            return None

        # Find maximum concentration
        max_category = max(market_distribution.items(), key=lambda x: x[1])
        category, concentration = max_category

        if concentration < threshold:
            return None

        # Strength increases with concentration above threshold
        excess_concentration = concentration - threshold
        strength = min(1.0, 0.5 + excess_concentration * 2.5)

        return Signal(
            signal_type=self.MARKET_SPECIALIST,
            strength=strength,
            description=f"{concentration*100:.1f}% of trades in '{category}' category",
            evidence={
                "primary_category": category,
                "concentration": concentration,
                "distribution": market_distribution,
                "threshold": threshold
            }
        )

    def velocity_signal(
        self,
        trades: list[Trade],
        lookback_days: int = 30,
        threshold_multiplier: float = DEFAULT_FREQUENCY_MULTIPLIER
    ) -> Optional[Signal]:
        """
        Detect sudden increase in trading frequency.

        A 5x+ spike in trading velocity suggests the trader found a new opportunity
        or edge they're aggressively exploiting.

        Args:
            trades: List of trades sorted by timestamp
            lookback_days: Days to look back for baseline
            threshold_multiplier: Multiplier for frequency spike detection

        Returns:
            Signal if velocity spike detected, None otherwise
        """
        if len(trades) < 20:
            return None

        now = datetime.utcnow()
        recent_cutoff = now - timedelta(days=7)
        baseline_cutoff = now - timedelta(days=lookback_days)

        # Recent trades (last 7 days)
        recent_trades = [t for t in trades if t.timestamp >= recent_cutoff]

        # Baseline trades (days 7-30)
        baseline_trades = [t for t in trades
                          if baseline_cutoff <= t.timestamp < recent_cutoff]

        if not baseline_trades or not recent_trades:
            return None

        # Calculate trades per day
        recent_per_day = len(recent_trades) / 7.0
        baseline_per_day = len(baseline_trades) / (lookback_days - 7.0)

        if baseline_per_day == 0:
            return None

        velocity_ratio = recent_per_day / baseline_per_day

        if velocity_ratio >= threshold_multiplier:
            # Strength based on magnitude of increase
            strength = min(1.0, 0.5 + (velocity_ratio - threshold_multiplier) / (threshold_multiplier * 2))

            return Signal(
                signal_type=self.FREQUENCY_SPIKE,
                strength=strength,
                description=f"Trading velocity increased {velocity_ratio:.1f}x ({recent_per_day:.1f} trades/day)",
                evidence={
                    "recent_trades_per_day": recent_per_day,
                    "baseline_trades_per_day": baseline_per_day,
                    "velocity_ratio": velocity_ratio,
                    "threshold": threshold_multiplier,
                    "recent_count": len(recent_trades),
                    "baseline_count": len(baseline_trades)
                }
            )

        return None

    def consistent_edge_signal(
        self,
        trades: list[Trade],
        min_days: int = DEFAULT_CONSISTENT_DAYS
    ) -> Optional[Signal]:
        """
        Detect consistent daily profits over extended period.

        Positive profit every single day for 7+ days is extremely rare in gambling
        but expected when exploiting an edge.

        Args:
            trades: List of trades sorted by timestamp
            min_days: Minimum consecutive profitable days required

        Returns:
            Signal if consistent edge detected, None otherwise
        """
        if not trades:
            return None

        # Group trades by day
        daily_profits = defaultdict(float)
        for trade in trades:
            day = trade.timestamp.date()
            daily_profits[day] += trade.profit

        if len(daily_profits) < min_days:
            return None

        # Find longest consecutive profitable streak
        sorted_days = sorted(daily_profits.keys())
        max_streak = 0
        current_streak = 0
        streak_start_date = None
        streak_end_date = None
        temp_start = None

        for i, day in enumerate(sorted_days):
            if daily_profits[day] > 0:
                if current_streak == 0:
                    temp_start = day
                current_streak += 1

                if current_streak > max_streak:
                    max_streak = current_streak
                    streak_start_date = temp_start
                    streak_end_date = day
            else:
                current_streak = 0

        if max_streak >= min_days:
            # Calculate total profit during streak
            streak_profit = sum(
                profit for day, profit in daily_profits.items()
                if streak_start_date <= day <= streak_end_date
            )

            # Strength increases with streak length
            strength = min(1.0, 0.5 + (max_streak - min_days) / 14.0)

            return Signal(
                signal_type=self.CONSISTENT_EDGE,
                strength=strength,
                description=f"{max_streak} consecutive profitable days (${streak_profit:.2f} total)",
                evidence={
                    "streak_length": max_streak,
                    "streak_profit": streak_profit,
                    "streak_start": streak_start_date.isoformat() if streak_start_date else None,
                    "streak_end": streak_end_date.isoformat() if streak_end_date else None,
                    "min_days_threshold": min_days,
                    "total_days_tracked": len(daily_profits)
                }
            )

        return None

    def calculate_alpha_score(self, signals: list[Signal]) -> float:
        """
        Calculate composite alpha score from multiple signals.

        Combines signal strengths with weights based on reliability. Returns overall
        likelihood (0.0-1.0) that this wallet has found a genuine edge.

        Signal reliability weights (based on how predictive each signal is):
        - WIN_RATE_ANOMALY: 0.25 (strong statistical evidence)
        - CONSISTENT_EDGE: 0.20 (hard to fake)
        - PROFIT_SPIKE: 0.20 (indicates recent discovery)
        - RAPID_GROWTH: 0.15 (could be luck but suggestive)
        - FREQUENCY_SPIKE: 0.10 (might be chasing losses)
        - MARKET_SPECIALIST: 0.10 (could indicate focus or limitation)

        Args:
            signals: List of detected signals

        Returns:
            Composite alpha score from 0.0 (no edge) to 1.0 (strong edge)
        """
        if not signals:
            return 0.0

        # Reliability weights for each signal type
        weights = {
            self.WIN_RATE_ANOMALY: 0.25,
            self.CONSISTENT_EDGE: 0.20,
            self.PROFIT_SPIKE: 0.20,
            self.RAPID_GROWTH: 0.15,
            self.FREQUENCY_SPIKE: 0.10,
            self.MARKET_SPECIALIST: 0.10,
        }

        # Calculate weighted sum
        total_weight = 0.0
        weighted_score = 0.0

        for signal in signals:
            weight = weights.get(signal.signal_type, 0.05)  # Default weight for unknown types
            weighted_score += signal.strength * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        # Normalize by actual weights used
        base_score = weighted_score / total_weight

        # Bonus for multiple signals (diversification of evidence)
        # Having 3+ different signal types increases confidence
        unique_signal_types = len(set(s.signal_type for s in signals))
        diversity_bonus = min(0.15, (unique_signal_types - 1) * 0.05)

        # Final score capped at 1.0
        alpha_score = min(1.0, base_score + diversity_bonus)

        return alpha_score

    def _calculate_market_distribution(self, trades: list[Trade]) -> dict[str, float]:
        """
        Calculate distribution of trades across market categories.

        Args:
            trades: List of trades

        Returns:
            Dictionary mapping category to proportion of trades
        """
        if not trades:
            return {}

        category_counts = defaultdict(int)
        total = 0

        for trade in trades:
            category = trade.market_category or "unknown"
            category_counts[category] += 1
            total += 1

        # Convert counts to proportions
        distribution = {
            category: count / total
            for category, count in category_counts.items()
        }

        return distribution
