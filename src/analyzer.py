"""
Polymarket trade pattern analysis module.

Analyzes trading patterns from Polymarket wallets to reverse-engineer trading strategies
and identify profitable patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import numpy as np
import pandas as pd
from collections import Counter, defaultdict


class StrategyType(Enum):
    """Classification of trading strategies."""
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    DIRECTIONAL = "directional"
    SNIPER = "sniper"
    UNKNOWN = "unknown"


@dataclass
class Trade:
    """
    Individual trade record from Polymarket.

    Attributes:
        timestamp: When the trade was executed
        market_id: Unique identifier for the market
        side: 'YES' or 'NO' outcome
        size: Trade size in dollars
        price: Price paid (0-1 for probability)
        is_maker: True if maker order, False if taker
        realized_pnl: Profit/loss if position closed (None if still open)
        exit_timestamp: When position was closed (None if still open)
    """
    timestamp: datetime
    market_id: str
    side: str  # 'YES' or 'NO'
    size: float
    price: float
    is_maker: bool
    realized_pnl: Optional[float] = None
    exit_timestamp: Optional[datetime] = None


@dataclass
class TimingAnalysis:
    """
    Analysis of when and how frequently a wallet trades.

    Attributes:
        avg_hold_time: Average time positions are held (seconds)
        trade_frequency: Trades per day
        time_of_day_pattern: Distribution of trades by hour (0-23)
        day_of_week_pattern: Distribution of trades by day (0=Monday, 6=Sunday)
        burst_trading_score: 0-1 score indicating concentration in short bursts
    """
    avg_hold_time: float
    trade_frequency: float
    time_of_day_pattern: dict[int, float]
    day_of_week_pattern: dict[int, float]
    burst_trading_score: float


@dataclass
class SizingAnalysis:
    """
    Analysis of position sizing patterns.

    Attributes:
        avg_size: Average trade size in dollars
        max_size: Maximum trade size observed
        size_variance: Variance in trade sizes
        scaling_pattern: 'fixed', 'kelly', 'martingale', 'progressive', or 'variable'
        size_percentiles: 25th, 50th, 75th, 95th percentile sizes
    """
    avg_size: float
    max_size: float
    size_variance: float
    scaling_pattern: str
    size_percentiles: dict[int, float]


@dataclass
class WalletAnalysis:
    """
    Complete analysis of a wallet's trading strategy.

    Attributes:
        strategy_type: Primary strategy classification
        confidence: Confidence in strategy classification (0-1)
        edge_estimate: Estimated edge in percentage points
        markets: Number of unique markets traded
        timing: Timing pattern analysis
        sizing: Position sizing analysis
        risk_score: Risk level (0-10, higher = riskier)
        replicability_score: How easy to replicate (1-10, higher = easier)
        win_rate: Percentage of profitable trades
        sharpe_ratio: Risk-adjusted returns
        maker_taker_ratio: Ratio of maker to taker orders
        total_volume: Total trading volume
        total_pnl: Total profit/loss
    """
    strategy_type: StrategyType
    confidence: float
    edge_estimate: float
    markets: int
    timing: TimingAnalysis
    sizing: SizingAnalysis
    risk_score: float
    replicability_score: float
    win_rate: float
    sharpe_ratio: float
    maker_taker_ratio: float
    total_volume: float
    total_pnl: float


class TradeAnalyzer:
    """
    Analyzes trade patterns to reverse-engineer trading strategies.

    Uses statistical analysis and heuristics to classify trading strategies,
    identify patterns, and assess risk/replicability.
    """

    def __init__(self, min_trades: int = 10):
        """
        Initialize analyzer.

        Args:
            min_trades: Minimum trades required for reliable analysis
        """
        self.min_trades = min_trades

    def analyze_wallet(self, trades: list[Trade]) -> WalletAnalysis:
        """
        Perform comprehensive analysis of a wallet's trading patterns.

        Args:
            trades: List of trades to analyze

        Returns:
            Complete wallet analysis including strategy classification

        Raises:
            ValueError: If insufficient trades for analysis
        """
        if len(trades) < self.min_trades:
            raise ValueError(
                f"Insufficient trades for analysis: {len(trades)} < {self.min_trades}"
            )

        # Sort trades by timestamp
        trades = sorted(trades, key=lambda t: t.timestamp)

        # Perform component analyses
        strategy_type = self.detect_strategy_type(trades)
        timing = self.analyze_timing_patterns(trades)
        sizing = self.analyze_position_sizing(trades)
        concentration = self.analyze_market_concentration(trades)
        maker_ratio = self.detect_maker_vs_taker(trades)

        # Calculate performance metrics
        closed_trades = [t for t in trades if t.realized_pnl is not None]
        win_rate = self._calculate_win_rate(closed_trades)
        sharpe = self._calculate_sharpe_ratio(trades, closed_trades)
        total_pnl = sum(t.realized_pnl for t in closed_trades)
        total_volume = sum(t.size for t in trades)
        edge = self._estimate_edge(win_rate, trades, strategy_type)

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            sizing, win_rate, concentration, strategy_type
        )

        # Calculate replicability score
        replicability = self._calculate_replicability_score(
            strategy_type, timing, sizing, concentration
        )

        # Determine confidence in strategy classification
        confidence = self._calculate_strategy_confidence(
            trades, strategy_type, win_rate, maker_ratio
        )

        return WalletAnalysis(
            strategy_type=strategy_type,
            confidence=confidence,
            edge_estimate=edge,
            markets=concentration['unique_markets'],
            timing=timing,
            sizing=sizing,
            risk_score=risk_score,
            replicability_score=replicability,
            win_rate=win_rate,
            sharpe_ratio=sharpe,
            maker_taker_ratio=maker_ratio,
            total_volume=total_volume,
            total_pnl=total_pnl
        )

    def detect_strategy_type(self, trades: list[Trade]) -> StrategyType:
        """
        Classify trading strategy based on pattern heuristics.

        Strategy Detection Heuristics:
        - Arbitrage: high win rate (>95%), paired YES/NO trades, short hold times
        - Market making: two-sided orders, inventory rebalancing, maker-heavy
        - Directional: concentrated bets, variable win rate, news-correlated timing
        - Sniper: burst activity at market open/close, specific timing windows

        Args:
            trades: List of trades to classify

        Returns:
            Detected strategy type
        """
        closed_trades = [t for t in trades if t.realized_pnl is not None]
        if len(closed_trades) < 5:
            return StrategyType.UNKNOWN

        win_rate = self._calculate_win_rate(closed_trades)
        maker_ratio = self.detect_maker_vs_taker(trades)
        timing = self.analyze_timing_patterns(trades)
        paired_trades = self._detect_paired_trades(trades)

        # Arbitrage detection
        if (win_rate > 0.95 and
            paired_trades > 0.6 and
            timing.avg_hold_time < 3600):  # < 1 hour
            return StrategyType.ARBITRAGE

        # Market making detection
        two_sided = self._detect_two_sided_trading(trades)
        if maker_ratio > 0.7 and two_sided > 0.5:
            return StrategyType.MARKET_MAKING

        # Sniper detection
        if (timing.burst_trading_score > 0.7 and
            len(set(t.market_id for t in trades)) > 10):
            return StrategyType.SNIPER

        # Directional detection
        concentration = self.analyze_market_concentration(trades)
        if concentration['gini_coefficient'] > 0.5:  # Concentrated positions
            return StrategyType.DIRECTIONAL

        return StrategyType.UNKNOWN

    def analyze_timing_patterns(self, trades: list[Trade]) -> TimingAnalysis:
        """
        Analyze when and how frequently trades occur.

        Args:
            trades: List of trades to analyze

        Returns:
            Timing pattern analysis
        """
        if not trades:
            return TimingAnalysis(0, 0, {}, {}, 0)

        # Calculate average hold time for closed positions
        closed_trades = [t for t in trades if t.exit_timestamp is not None]
        if closed_trades:
            hold_times = [
                (t.exit_timestamp - t.timestamp).total_seconds()
                for t in closed_trades
            ]
            avg_hold_time = np.mean(hold_times)
        else:
            avg_hold_time = 0.0

        # Calculate trade frequency
        time_span = (trades[-1].timestamp - trades[0].timestamp).total_seconds()
        trade_frequency = len(trades) / (time_span / 86400) if time_span > 0 else 0

        # Time of day pattern (normalized)
        hours = [t.timestamp.hour for t in trades]
        hour_counts = Counter(hours)
        total_trades = len(trades)
        time_of_day = {h: hour_counts.get(h, 0) / total_trades for h in range(24)}

        # Day of week pattern (normalized)
        days = [t.timestamp.weekday() for t in trades]
        day_counts = Counter(days)
        day_of_week = {d: day_counts.get(d, 0) / total_trades for d in range(7)}

        # Burst trading score (trades concentrated in short windows)
        burst_score = self._calculate_burst_score(trades)

        return TimingAnalysis(
            avg_hold_time=avg_hold_time,
            trade_frequency=trade_frequency,
            time_of_day_pattern=time_of_day,
            day_of_week_pattern=day_of_week,
            burst_trading_score=burst_score
        )

    def analyze_market_concentration(self, trades: list[Trade]) -> dict:
        """
        Analyze which markets the wallet focuses on.

        Args:
            trades: List of trades to analyze

        Returns:
            Dictionary with concentration metrics:
            - unique_markets: Number of unique markets
            - top_markets: Top 5 markets by volume
            - gini_coefficient: 0-1, higher = more concentrated
            - hhi_index: Herfindahl-Hirschman Index (market concentration)
        """
        if not trades:
            return {
                'unique_markets': 0,
                'top_markets': [],
                'gini_coefficient': 0,
                'hhi_index': 0
            }

        # Calculate volume by market
        market_volumes = defaultdict(float)
        for trade in trades:
            market_volumes[trade.market_id] += trade.size

        unique_markets = len(market_volumes)

        # Top markets
        top_markets = sorted(
            market_volumes.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Calculate Gini coefficient
        volumes = sorted(market_volumes.values())
        n = len(volumes)
        total_volume = sum(volumes)

        if total_volume > 0:
            cumsum = np.cumsum(volumes)
            gini = (2 * sum((i + 1) * v for i, v in enumerate(volumes))) / (n * total_volume) - (n + 1) / n
        else:
            gini = 0

        # Calculate HHI (Herfindahl-Hirschman Index)
        market_shares = [v / total_volume for v in volumes] if total_volume > 0 else []
        hhi = sum(s ** 2 for s in market_shares) * 10000  # Traditional HHI scale

        return {
            'unique_markets': unique_markets,
            'top_markets': top_markets,
            'gini_coefficient': gini,
            'hhi_index': hhi
        }

    def analyze_position_sizing(self, trades: list[Trade]) -> SizingAnalysis:
        """
        Analyze position sizing patterns to detect Kelly, fixed, or scaling strategies.

        Args:
            trades: List of trades to analyze

        Returns:
            Position sizing analysis
        """
        if not trades:
            return SizingAnalysis(0, 0, 0, 'unknown', {})

        sizes = [t.size for t in trades]

        avg_size = np.mean(sizes)
        max_size = np.max(sizes)
        size_variance = np.var(sizes)

        # Calculate percentiles
        percentiles = {
            25: np.percentile(sizes, 25),
            50: np.percentile(sizes, 50),
            75: np.percentile(sizes, 75),
            95: np.percentile(sizes, 95)
        }

        # Detect scaling pattern
        scaling_pattern = self._detect_sizing_pattern(trades, sizes)

        return SizingAnalysis(
            avg_size=avg_size,
            max_size=max_size,
            size_variance=size_variance,
            scaling_pattern=scaling_pattern,
            size_percentiles=percentiles
        )

    def calculate_profit_acceleration(self, trades: list[Trade]) -> float:
        """
        Calculate if profits are growing exponentially.

        Uses exponential regression on cumulative PnL to detect acceleration.

        Args:
            trades: List of trades to analyze

        Returns:
            Acceleration coefficient (>1 means accelerating, <1 means decelerating)
        """
        closed_trades = [t for t in trades if t.realized_pnl is not None]
        if len(closed_trades) < 10:
            return 1.0  # Neutral

        # Calculate cumulative PnL
        cumulative_pnl = np.cumsum([t.realized_pnl for t in closed_trades])

        # Fit exponential model: log(y) = a + b*x
        x = np.arange(len(cumulative_pnl))

        # Add small constant to handle negative/zero values
        y_shifted = cumulative_pnl - np.min(cumulative_pnl) + 1

        # Fit linear regression on log scale
        try:
            log_y = np.log(y_shifted)
            coeffs = np.polyfit(x, log_y, 1)
            acceleration = np.exp(coeffs[0])  # exp(slope) gives growth rate
        except (ValueError, RuntimeWarning):
            acceleration = 1.0

        return float(acceleration)

    def detect_maker_vs_taker(self, trades: list[Trade]) -> float:
        """
        Calculate ratio of maker to taker orders.

        Args:
            trades: List of trades to analyze

        Returns:
            Maker/taker ratio (0 = all taker, 1 = all maker)
        """
        if not trades:
            return 0.0

        maker_count = sum(1 for t in trades if t.is_maker)
        return maker_count / len(trades)

    def _calculate_win_rate(self, closed_trades: list[Trade]) -> float:
        """Calculate percentage of profitable closed trades."""
        if not closed_trades:
            return 0.0

        wins = sum(1 for t in closed_trades if t.realized_pnl > 0)
        return wins / len(closed_trades)

    def _calculate_sharpe_ratio(
        self,
        all_trades: list[Trade],
        closed_trades: list[Trade]
    ) -> float:
        """Calculate Sharpe ratio of returns."""
        if len(closed_trades) < 2:
            return 0.0

        returns = [t.realized_pnl / t.size for t in closed_trades if t.size > 0]
        if not returns:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualized Sharpe (assuming daily trading)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        return float(sharpe)

    def _estimate_edge(
        self,
        win_rate: float,
        trades: list[Trade],
        strategy_type: StrategyType
    ) -> float:
        """Estimate edge in percentage points."""
        closed_trades = [t for t in trades if t.realized_pnl is not None]
        if not closed_trades:
            return 0.0

        # Calculate average profit per dollar risked
        avg_pnl_pct = np.mean([
            t.realized_pnl / t.size for t in closed_trades if t.size > 0
        ])

        # Adjust for strategy type
        if strategy_type == StrategyType.ARBITRAGE:
            # Arbitrage edge is typically small but consistent
            return min(avg_pnl_pct * 100, 5.0)
        elif strategy_type == StrategyType.MARKET_MAKING:
            # Market making edge is spread capture
            return min(avg_pnl_pct * 100, 3.0)
        else:
            # Directional/sniper edge varies more
            return avg_pnl_pct * 100

    def _calculate_risk_score(
        self,
        sizing: SizingAnalysis,
        win_rate: float,
        concentration: dict,
        strategy_type: StrategyType
    ) -> float:
        """
        Calculate risk score 0-10 (higher = riskier).

        Factors:
        - Position size variance
        - Win rate (lower = riskier)
        - Market concentration
        - Strategy type
        """
        risk = 0.0

        # Size variance risk (0-3 points)
        if sizing.avg_size > 0:
            cv = np.sqrt(sizing.size_variance) / sizing.avg_size  # Coefficient of variation
            risk += min(cv * 3, 3)

        # Win rate risk (0-3 points)
        risk += (1 - win_rate) * 3

        # Concentration risk (0-2 points)
        risk += min(concentration['gini_coefficient'] * 2, 2)

        # Strategy-specific risk (0-2 points)
        strategy_risk = {
            StrategyType.ARBITRAGE: 0.5,
            StrategyType.MARKET_MAKING: 1.0,
            StrategyType.DIRECTIONAL: 2.0,
            StrategyType.SNIPER: 1.5,
            StrategyType.UNKNOWN: 2.0
        }
        risk += strategy_risk.get(strategy_type, 2.0)

        return min(risk, 10.0)

    def _calculate_replicability_score(
        self,
        strategy_type: StrategyType,
        timing: TimingAnalysis,
        sizing: SizingAnalysis,
        concentration: dict
    ) -> float:
        """
        Score how easy it is to replicate strategy (1-10, higher = easier).

        Factors:
        - Strategy clarity
        - Consistent patterns
        - Market availability
        - Timing predictability
        """
        score = 5.0  # Start neutral

        # Strategy type replicability
        strategy_scores = {
            StrategyType.ARBITRAGE: 7.0,  # Clear rules but execution-dependent
            StrategyType.MARKET_MAKING: 5.0,  # Requires infrastructure
            StrategyType.DIRECTIONAL: 6.0,  # Easy to copy if you spot the edge
            StrategyType.SNIPER: 8.0,  # Very rule-based
            StrategyType.UNKNOWN: 2.0  # Hard to replicate unknown strategy
        }
        score = strategy_scores.get(strategy_type, 5.0)

        # Consistent sizing is easier to replicate (+1)
        if sizing.avg_size > 0:
            cv = np.sqrt(sizing.size_variance) / sizing.avg_size
            if cv < 0.3:  # Low variance
                score += 1

        # Regular trading schedule is easier to replicate (+1)
        if timing.burst_trading_score < 0.3:  # Regular, not bursty
            score += 1

        # Diverse markets easier to access (+1)
        if concentration['unique_markets'] > 20:
            score += 1

        # Maker orders harder to replicate (-1)
        # This is assessed elsewhere, skip here

        return min(max(score, 1.0), 10.0)

    def _calculate_strategy_confidence(
        self,
        trades: list[Trade],
        strategy_type: StrategyType,
        win_rate: float,
        maker_ratio: float
    ) -> float:
        """Calculate confidence in strategy classification (0-1)."""
        if strategy_type == StrategyType.UNKNOWN:
            return 0.0

        confidence = 0.5  # Base confidence

        # More trades = higher confidence
        if len(trades) > 100:
            confidence += 0.2
        elif len(trades) > 50:
            confidence += 0.1

        # Strong signals increase confidence
        if strategy_type == StrategyType.ARBITRAGE and win_rate > 0.95:
            confidence += 0.2
        elif strategy_type == StrategyType.MARKET_MAKING and maker_ratio > 0.8:
            confidence += 0.2

        return min(confidence, 1.0)

    def _detect_paired_trades(self, trades: list[Trade]) -> float:
        """
        Detect paired YES/NO trades in same markets (arbitrage indicator).

        Returns:
            Ratio of trades that are paired (0-1)
        """
        # Group by market and time window (5 minutes)
        market_trades = defaultdict(list)
        for trade in trades:
            window = int(trade.timestamp.timestamp() / 300)  # 5-min windows
            key = (trade.market_id, window)
            market_trades[key].append(trade)

        paired_count = 0
        for market_window_trades in market_trades.values():
            if len(market_window_trades) >= 2:
                sides = [t.side for t in market_window_trades]
                if 'YES' in sides and 'NO' in sides:
                    paired_count += len(market_window_trades)

        return paired_count / len(trades) if trades else 0.0

    def _detect_two_sided_trading(self, trades: list[Trade]) -> float:
        """
        Detect if trader takes both sides of markets (market making indicator).

        Returns:
            Ratio of markets where both YES and NO were traded (0-1)
        """
        market_sides = defaultdict(set)
        for trade in trades:
            market_sides[trade.market_id].add(trade.side)

        two_sided = sum(1 for sides in market_sides.values() if len(sides) == 2)
        return two_sided / len(market_sides) if market_sides else 0.0

    def _calculate_burst_score(self, trades: list[Trade]) -> float:
        """
        Calculate if trading happens in bursts (sniper indicator).

        Uses coefficient of variation of inter-trade times.

        Returns:
            Burst score 0-1 (higher = more bursty)
        """
        if len(trades) < 3:
            return 0.0

        # Calculate inter-trade times
        timestamps = [t.timestamp.timestamp() for t in trades]
        inter_trade_times = np.diff(timestamps)

        if len(inter_trade_times) == 0:
            return 0.0

        # High CV = bursty (long gaps with short bursts)
        mean_time = np.mean(inter_trade_times)
        if mean_time == 0:
            return 0.0

        cv = np.std(inter_trade_times) / mean_time

        # Normalize to 0-1 (CV > 2 is very bursty)
        burst_score = min(cv / 2, 1.0)

        return float(burst_score)

    def _detect_sizing_pattern(self, trades: list[Trade], sizes: list[float]) -> str:
        """
        Detect position sizing pattern.

        Returns:
            'fixed', 'kelly', 'martingale', 'progressive', or 'variable'
        """
        if len(sizes) < 10:
            return 'variable'

        cv = np.std(sizes) / np.mean(sizes) if np.mean(sizes) > 0 else 0

        # Fixed sizing: low variance
        if cv < 0.2:
            return 'fixed'

        # Check for martingale (doubling after losses)
        closed_trades = [t for t in trades if t.realized_pnl is not None]
        if len(closed_trades) >= 5:
            martingale_score = self._detect_martingale(closed_trades)
            if martingale_score > 0.6:
                return 'martingale'

        # Check for Kelly-like (size proportional to edge * bankroll)
        kelly_score = self._detect_kelly_sizing(trades)
        if kelly_score > 0.6:
            return 'kelly'

        # Check for progressive (increasing over time)
        correlation = np.corrcoef(range(len(sizes)), sizes)[0, 1]
        if correlation > 0.5:
            return 'progressive'

        return 'variable'

    def _detect_martingale(self, closed_trades: list[Trade]) -> float:
        """Detect martingale betting (doubling after losses)."""
        if len(closed_trades) < 3:
            return 0.0

        martingale_count = 0
        for i in range(len(closed_trades) - 1):
            if closed_trades[i].realized_pnl < 0:
                size_ratio = closed_trades[i + 1].size / closed_trades[i].size
                if 1.8 <= size_ratio <= 2.2:  # Approximately doubled
                    martingale_count += 1

        return martingale_count / (len(closed_trades) - 1)

    def _detect_kelly_sizing(self, trades: list[Trade]) -> float:
        """
        Detect Kelly criterion sizing (size proportional to edge).

        Kelly would show correlation between win probability and bet size.
        """
        closed_trades = [t for t in trades if t.realized_pnl is not None]
        if len(closed_trades) < 10:
            return 0.0

        # Calculate rolling win rate and check correlation with position size
        window = 10
        correlations = []

        for i in range(window, len(closed_trades)):
            recent_trades = closed_trades[i-window:i]
            win_rate = sum(1 for t in recent_trades if t.realized_pnl > 0) / window
            current_size = closed_trades[i].size
            correlations.append((win_rate, current_size))

        if len(correlations) < 5:
            return 0.0

        win_rates, sizes = zip(*correlations)
        correlation = np.corrcoef(win_rates, sizes)[0, 1]

        # Return absolute correlation (positive or negative)
        return abs(correlation) if not np.isnan(correlation) else 0.0
