"""
Polymarket Strategy Reverse Engineering Module

This module analyzes successful wallet trading patterns and reverse-engineers
their strategies into actionable blueprints that can be replicated.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, timedelta
import json
from collections import Counter, defaultdict
import statistics


class StrategyType(Enum):
    """Types of trading strategies detected"""
    ARBITRAGE_BINARY = "arbitrage_binary"  # YES+NO pairing on binary markets
    ARBITRAGE_MULTI = "arbitrage_multi"  # All outcomes in multi-outcome markets
    MARKET_MAKER = "market_maker"  # Spread capture with inventory management
    DIRECTIONAL = "directional"  # Prediction-based position taking
    SNIPER = "sniper"  # Event-triggered rapid trading
    HYBRID = "hybrid"  # Mixed strategy


class RuleType(Enum):
    """Types of rules extracted from trading patterns"""
    ENTRY_CONDITION = "entry_condition"
    EXIT_CONDITION = "exit_condition"
    SIZING_RULE = "sizing_rule"
    MARKET_FILTER = "market_filter"


@dataclass
class Rule:
    """
    A single rule extracted from trading patterns

    Attributes:
        condition: Human-readable condition (e.g., "sum(YES+NO) < 0.99")
        value: Specific value or threshold (e.g., 0.99)
        confidence: 0-1 score indicating how consistently this rule is followed
        evidence_count: Number of trades supporting this rule
        rule_type: Category of rule
        metadata: Additional context
    """
    condition: str
    value: Any
    confidence: float
    evidence_count: int
    rule_type: RuleType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        if self.evidence_count < 0:
            raise ValueError("Evidence count must be non-negative")


@dataclass
class StrategyBlueprint:
    """
    Complete reverse-engineered strategy specification

    Attributes:
        name: Strategy identifier
        strategy_type: Primary strategy classification
        entry_rules: Conditions for entering positions
        exit_rules: Conditions for exiting positions
        sizing_rules: Position sizing methodology
        market_filters: Market selection criteria
        estimated_edge: Expected profit per trade or per period
        capital_required: Minimum capital to replicate
        replicability_score: 0-1 score of how easy to replicate
        timeframe: Typical holding period
        trade_frequency: Expected trades per day
        win_rate: Historical success rate
        risk_profile: Risk characteristics
        additional_notes: Freeform observations
    """
    name: str
    strategy_type: StrategyType
    entry_rules: List[Rule]
    exit_rules: List[Rule]
    sizing_rules: List[Rule]
    market_filters: List[Rule]
    estimated_edge: Dict[str, float]  # e.g., {"per_trade_pct": 2.5, "daily_pnl": 150}
    capital_required: float
    replicability_score: float
    timeframe: str = "unknown"
    trade_frequency: float = 0.0
    win_rate: float = 0.0
    risk_profile: str = "unknown"
    additional_notes: str = ""

    def __post_init__(self):
        if not 0 <= self.replicability_score <= 1:
            raise ValueError("Replicability score must be between 0 and 1")


@dataclass
class Trade:
    """
    Simplified trade record for analysis
    """
    timestamp: datetime
    market_id: str
    market_title: str
    outcome: str  # YES/NO or candidate name
    side: str  # BUY/SELL
    shares: float
    price: float
    value: float  # shares * price
    market_type: str = "binary"  # binary or multi
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WalletProfile:
    """
    Wallet identification and basic stats
    """
    address: str
    total_trades: int
    active_days: int
    creation_date: datetime
    total_pnl: float
    current_balance: float


@dataclass
class WalletAnalysis:
    """
    Analyzed patterns from wallet history
    """
    wallet: WalletProfile
    primary_markets: List[str]  # Market types/categories traded
    avg_trade_size: float
    avg_holding_period: timedelta
    win_rate: float
    peak_exposure: float  # Max % of capital in positions
    trading_hours: List[int]  # Hours of day most active (0-23)
    patterns: Dict[str, Any] = field(default_factory=dict)


class StrategyReverser:
    """
    Main class for reverse-engineering trading strategies from wallet data
    """

    def __init__(self, min_confidence: float = 0.7, min_evidence: int = 10):
        """
        Initialize the strategy reverser

        Args:
            min_confidence: Minimum confidence threshold for rules
            min_evidence: Minimum evidence count for rules
        """
        self.min_confidence = min_confidence
        self.min_evidence = min_evidence

    def reverse_engineer(
        self,
        wallet: WalletProfile,
        trades: List[Trade],
        analysis: WalletAnalysis
    ) -> StrategyBlueprint:
        """
        Main entry point: reverse engineer complete strategy from wallet data

        Args:
            wallet: Wallet profile information
            trades: Complete trade history
            analysis: Pre-computed analysis of wallet patterns

        Returns:
            Complete strategy blueprint
        """
        # Classify strategy type
        strategy_type = self._classify_strategy(trades, analysis)

        # Extract rule sets
        entry_rules = self.extract_entry_rules(trades, strategy_type)
        exit_rules = self.extract_exit_rules(trades, strategy_type)
        sizing_rules = self.extract_sizing_rules(trades, strategy_type)
        market_filters = self.extract_market_selection(trades, strategy_type)

        # Calculate performance metrics
        estimated_edge = self._calculate_edge(trades, analysis)
        capital_required = self._estimate_capital_required(trades, analysis)
        replicability = self._calculate_replicability(
            entry_rules, exit_rules, sizing_rules, market_filters
        )

        # Build blueprint
        blueprint = StrategyBlueprint(
            name=f"{wallet.address[:10]}_strategy",
            strategy_type=strategy_type,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            sizing_rules=sizing_rules,
            market_filters=market_filters,
            estimated_edge=estimated_edge,
            capital_required=capital_required,
            replicability_score=replicability,
            timeframe=self._estimate_timeframe(trades, analysis),
            trade_frequency=wallet.total_trades / max(wallet.active_days, 1),
            win_rate=analysis.win_rate,
            risk_profile=self._assess_risk_profile(strategy_type, trades, analysis),
            additional_notes=self._generate_notes(strategy_type, trades, analysis)
        )

        return blueprint

    def extract_entry_rules(
        self,
        trades: List[Trade],
        strategy_type: Optional[StrategyType] = None
    ) -> List[Rule]:
        """
        Extract rules for when/why the trader enters positions

        Args:
            trades: Trade history
            strategy_type: Detected strategy type (for focused extraction)

        Returns:
            List of entry condition rules
        """
        if strategy_type is None:
            strategy_type = self._classify_strategy(trades, None)

        rules = []

        if strategy_type == StrategyType.ARBITRAGE_BINARY:
            rules.extend(self._extract_binary_arb_entry(trades))
        elif strategy_type == StrategyType.ARBITRAGE_MULTI:
            rules.extend(self._extract_multi_arb_entry(trades))
        elif strategy_type == StrategyType.MARKET_MAKER:
            rules.extend(self._extract_mm_entry(trades))
        elif strategy_type == StrategyType.DIRECTIONAL:
            rules.extend(self._extract_directional_entry(trades))
        elif strategy_type == StrategyType.SNIPER:
            rules.extend(self._extract_sniper_entry(trades))

        # Filter by confidence and evidence
        return [r for r in rules if r.confidence >= self.min_confidence
                and r.evidence_count >= self.min_evidence]

    def extract_exit_rules(
        self,
        trades: List[Trade],
        strategy_type: Optional[StrategyType] = None
    ) -> List[Rule]:
        """
        Extract rules for when/why the trader exits positions

        Args:
            trades: Trade history
            strategy_type: Detected strategy type

        Returns:
            List of exit condition rules
        """
        if strategy_type is None:
            strategy_type = self._classify_strategy(trades, None)

        rules = []

        # Group trades by market to find entry/exit pairs
        market_positions = self._group_trades_by_market(trades)

        if strategy_type in [StrategyType.ARBITRAGE_BINARY, StrategyType.ARBITRAGE_MULTI]:
            # Arbitrage typically holds to resolution
            hold_to_resolution = sum(
                1 for market_trades in market_positions.values()
                if len([t for t in market_trades if t.side == "SELL"]) == 0
            )

            if hold_to_resolution / max(len(market_positions), 1) > 0.8:
                rules.append(Rule(
                    condition="Hold to market resolution",
                    value="resolution",
                    confidence=hold_to_resolution / len(market_positions),
                    evidence_count=hold_to_resolution,
                    rule_type=RuleType.EXIT_CONDITION,
                    metadata={"type": "arbitrage_hold"}
                ))
        else:
            # Analyze holding periods
            holding_periods = []
            profit_targets = []
            stop_losses = []

            for market_trades in market_positions.values():
                buys = [t for t in market_trades if t.side == "BUY"]
                sells = [t for t in market_trades if t.side == "SELL"]

                for buy in buys:
                    matching_sells = [s for s in sells if s.timestamp > buy.timestamp]
                    if matching_sells:
                        sell = min(matching_sells, key=lambda x: x.timestamp)
                        holding_periods.append((sell.timestamp - buy.timestamp).total_seconds())

                        # Calculate profit
                        profit_pct = (sell.price - buy.price) / buy.price * 100
                        if profit_pct > 0:
                            profit_targets.append(profit_pct)
                        else:
                            stop_losses.append(abs(profit_pct))

            if holding_periods:
                avg_hold = statistics.mean(holding_periods)
                rules.append(Rule(
                    condition=f"Exit after {avg_hold/3600:.1f} hours average",
                    value=avg_hold,
                    confidence=0.8,
                    evidence_count=len(holding_periods),
                    rule_type=RuleType.EXIT_CONDITION,
                    metadata={"unit": "seconds", "type": "time_based"}
                ))

            if profit_targets:
                avg_target = statistics.mean(profit_targets)
                rules.append(Rule(
                    condition=f"Take profit at ~{avg_target:.1f}% gain",
                    value=avg_target,
                    confidence=0.7,
                    evidence_count=len(profit_targets),
                    rule_type=RuleType.EXIT_CONDITION,
                    metadata={"unit": "percent", "type": "profit_target"}
                ))

            if stop_losses:
                avg_stop = statistics.mean(stop_losses)
                rules.append(Rule(
                    condition=f"Stop loss at ~{avg_stop:.1f}% loss",
                    value=-avg_stop,
                    confidence=0.7,
                    evidence_count=len(stop_losses),
                    rule_type=RuleType.EXIT_CONDITION,
                    metadata={"unit": "percent", "type": "stop_loss"}
                ))

        return [r for r in rules if r.confidence >= self.min_confidence
                and r.evidence_count >= self.min_evidence]

    def extract_sizing_rules(
        self,
        trades: List[Trade],
        strategy_type: Optional[StrategyType] = None
    ) -> List[Rule]:
        """
        Extract position sizing methodology

        Args:
            trades: Trade history
            strategy_type: Detected strategy type

        Returns:
            List of sizing rules
        """
        if not trades:
            return []

        rules = []

        # Analyze trade values ($ amount per trade)
        trade_values = [t.value for t in trades if t.side == "BUY"]

        if trade_values:
            avg_size = statistics.mean(trade_values)
            median_size = statistics.median(trade_values)
            stdev_size = statistics.stdev(trade_values) if len(trade_values) > 1 else 0

            # Check if sizing is fixed or dynamic
            cv = stdev_size / avg_size if avg_size > 0 else 0  # Coefficient of variation

            if cv < 0.2:  # Low variation = fixed size
                rules.append(Rule(
                    condition=f"Fixed position size ~${avg_size:.0f}",
                    value=avg_size,
                    confidence=1 - cv,
                    evidence_count=len(trade_values),
                    rule_type=RuleType.SIZING_RULE,
                    metadata={"type": "fixed", "median": median_size}
                ))
            else:  # Dynamic sizing
                rules.append(Rule(
                    condition=f"Dynamic sizing: ${median_size:.0f} typical (${min(trade_values):.0f}-${max(trade_values):.0f} range)",
                    value=median_size,
                    confidence=0.7,
                    evidence_count=len(trade_values),
                    rule_type=RuleType.SIZING_RULE,
                    metadata={
                        "type": "dynamic",
                        "min": min(trade_values),
                        "max": max(trade_values),
                        "std": stdev_size
                    }
                ))

        # Check for scaling patterns over time
        if len(trades) > 100:
            early_trades = trades[:len(trades)//3]
            late_trades = trades[-len(trades)//3:]

            early_avg = statistics.mean([t.value for t in early_trades if t.side == "BUY"])
            late_avg = statistics.mean([t.value for t in late_trades if t.side == "BUY"])

            if late_avg > early_avg * 1.5:  # 50% increase suggests compounding
                rules.append(Rule(
                    condition="Compound profits (position size grows over time)",
                    value=late_avg / early_avg,
                    confidence=0.85,
                    evidence_count=len(trades),
                    rule_type=RuleType.SIZING_RULE,
                    metadata={
                        "early_avg": early_avg,
                        "late_avg": late_avg,
                        "growth_factor": late_avg / early_avg
                    }
                ))

        # Check for max exposure limits
        # Group concurrent positions
        max_concurrent_value = self._calculate_max_concurrent_exposure(trades)
        if max_concurrent_value > 0:
            rules.append(Rule(
                condition=f"Maximum concurrent exposure ~${max_concurrent_value:.0f}",
                value=max_concurrent_value,
                confidence=0.8,
                evidence_count=len(trades),
                rule_type=RuleType.SIZING_RULE,
                metadata={"type": "max_exposure"}
            ))

        return rules

    def extract_market_selection(
        self,
        trades: List[Trade],
        strategy_type: Optional[StrategyType] = None
    ) -> List[Rule]:
        """
        Extract criteria for which markets the trader selects

        Args:
            trades: Trade history
            strategy_type: Detected strategy type

        Returns:
            List of market selection rules
        """
        if not trades:
            return []

        rules = []

        # Analyze market titles for keywords
        market_keywords = Counter()
        market_types = Counter()

        for trade in trades:
            # Extract keywords from market title
            title_lower = trade.market_title.lower()
            keywords = title_lower.split()

            for keyword in keywords:
                if len(keyword) > 3:  # Skip short words
                    market_keywords[keyword] += 1

            market_types[trade.market_type] += 1

        # Most common market themes
        top_keywords = market_keywords.most_common(10)
        if top_keywords:
            most_common = top_keywords[0]
            if most_common[1] / len(trades) > 0.3:  # Appears in 30%+ of trades
                rules.append(Rule(
                    condition=f"Focus on '{most_common[0]}' markets",
                    value=most_common[0],
                    confidence=most_common[1] / len(trades),
                    evidence_count=most_common[1],
                    rule_type=RuleType.MARKET_FILTER,
                    metadata={"top_keywords": dict(top_keywords[:5])}
                ))

        # Binary vs multi-outcome preference
        for market_type, count in market_types.items():
            confidence = count / len(trades)
            if confidence > 0.7:
                rules.append(Rule(
                    condition=f"Trade {market_type} outcome markets",
                    value=market_type,
                    confidence=confidence,
                    evidence_count=count,
                    rule_type=RuleType.MARKET_FILTER,
                    metadata={"market_type_distribution": dict(market_types)}
                ))

        # Check for timeframe preferences (if metadata contains this)
        timeframes = Counter()
        for trade in trades:
            if "timeframe" in trade.metadata:
                timeframes[trade.metadata["timeframe"]] += 1

        if timeframes:
            for timeframe, count in timeframes.most_common(3):
                confidence = count / len(trades)
                if confidence > 0.5:
                    rules.append(Rule(
                        condition=f"Prefer {timeframe} markets",
                        value=timeframe,
                        confidence=confidence,
                        evidence_count=count,
                        rule_type=RuleType.MARKET_FILTER,
                        metadata={"timeframe_distribution": dict(timeframes)}
                    ))

        return rules

    def generate_pseudocode(self, blueprint: StrategyBlueprint) -> str:
        """
        Generate human-readable pseudocode description of the strategy

        Args:
            blueprint: Strategy blueprint

        Returns:
            Formatted pseudocode string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"STRATEGY: {blueprint.name}")
        lines.append(f"TYPE: {blueprint.strategy_type.value}")
        lines.append(f"REPLICABILITY: {blueprint.replicability_score:.1%}")
        lines.append("=" * 80)
        lines.append("")

        lines.append("# INITIALIZATION")
        lines.append(f"capital = ${blueprint.capital_required:,.0f}")
        lines.append(f"expected_trades_per_day = {blueprint.trade_frequency:.0f}")
        lines.append(f"expected_win_rate = {blueprint.win_rate:.1%}")
        lines.append("")

        if blueprint.market_filters:
            lines.append("# MARKET SELECTION")
            lines.append("while True:")
            lines.append("    markets = get_all_active_markets()")
            lines.append("    filtered_markets = []")
            lines.append("    for market in markets:")
            for rule in blueprint.market_filters:
                lines.append(f"        if {rule.condition}:  # confidence: {rule.confidence:.1%}")
                lines.append("            filtered_markets.append(market)")
            lines.append("")

        if blueprint.entry_rules:
            lines.append("    # ENTRY LOGIC")
            lines.append("    for market in filtered_markets:")
            lines.append("        opportunity = analyze_market(market)")
            lines.append("        ")
            for i, rule in enumerate(blueprint.entry_rules):
                prefix = "if" if i == 0 else "and"
                lines.append(f"        {prefix} {rule.condition}:  # confidence: {rule.confidence:.1%}")
            lines.append("            # Calculate position size")

            if blueprint.sizing_rules:
                for rule in blueprint.sizing_rules:
                    lines.append(f"            # {rule.condition}")
                lines.append(f"            size = calculate_size(capital, opportunity)")
            else:
                lines.append("            size = default_size")

            lines.append("            ")
            lines.append("            # Execute trade")
            lines.append("            enter_position(market, size)")
            lines.append("")

        if blueprint.exit_rules:
            lines.append("    # EXIT LOGIC")
            lines.append("    for position in open_positions:")
            for i, rule in enumerate(blueprint.exit_rules):
                prefix = "if" if i == 0 else "elif"
                lines.append(f"        {prefix} {rule.condition}:  # confidence: {rule.confidence:.1%}")
                lines.append("            close_position(position)")
            lines.append("")

        lines.append("    sleep(check_interval)")
        lines.append("")

        lines.append("# EXPECTED PERFORMANCE")
        for key, value in blueprint.estimated_edge.items():
            lines.append(f"# {key}: {value}")
        lines.append(f"# Risk Profile: {blueprint.risk_profile}")
        lines.append(f"# Typical Timeframe: {blueprint.timeframe}")
        lines.append("")

        if blueprint.additional_notes:
            lines.append("# NOTES")
            for note_line in blueprint.additional_notes.split("\n"):
                lines.append(f"# {note_line}")

        lines.append("=" * 80)

        return "\n".join(lines)

    # Helper methods

    def _classify_strategy(
        self,
        trades: List[Trade],
        analysis: Optional[WalletAnalysis]
    ) -> StrategyType:
        """Classify the primary strategy type based on trade patterns"""
        if not trades:
            return StrategyType.HYBRID

        # Check for arbitrage patterns
        market_positions = self._group_trades_by_market(trades)

        # Binary arbitrage: paired YES/NO positions
        binary_arb_count = 0
        for market_trades in market_positions.values():
            outcomes = {t.outcome for t in market_trades if t.side == "BUY"}
            if "YES" in outcomes and "NO" in outcomes:
                binary_arb_count += 1

        if binary_arb_count / max(len(market_positions), 1) > 0.7:
            return StrategyType.ARBITRAGE_BINARY

        # Multi-outcome arbitrage: buying all outcomes
        multi_arb_count = 0
        for market_id, market_trades in market_positions.items():
            if market_trades and market_trades[0].market_type == "multi":
                unique_outcomes = {t.outcome for t in market_trades if t.side == "BUY"}
                # If buying 3+ different outcomes, likely multi-arb
                if len(unique_outcomes) >= 3:
                    multi_arb_count += 1

        if multi_arb_count / max(len(market_positions), 1) > 0.5:
            return StrategyType.ARBITRAGE_MULTI

        # Market maker: high trade frequency, small spreads
        if analysis and analysis.win_rate > 0.90 and len(trades) / max(analysis.wallet.active_days, 1) > 100:
            return StrategyType.MARKET_MAKER

        # Sniper: very fast entry/exit
        if analysis and analysis.avg_holding_period < timedelta(hours=1):
            return StrategyType.SNIPER

        # Default to directional
        return StrategyType.DIRECTIONAL

    def _extract_binary_arb_entry(self, trades: List[Trade]) -> List[Rule]:
        """Extract entry rules for binary arbitrage"""
        rules = []

        # Find paired YES+NO entries
        market_positions = self._group_trades_by_market(trades)
        paired_entries = []

        for market_trades in market_positions.values():
            buys = [t for t in market_trades if t.side == "BUY"]
            yes_buys = [t for t in buys if t.outcome == "YES"]
            no_buys = [t for t in buys if t.outcome == "NO"]

            # Match YES/NO pairs by timestamp proximity
            for yes_trade in yes_buys:
                for no_trade in no_buys:
                    time_diff = abs((yes_trade.timestamp - no_trade.timestamp).total_seconds())
                    if time_diff < 60:  # Within 1 minute = likely paired
                        combined_cost = yes_trade.price + no_trade.price
                        paired_entries.append({
                            "combined_cost": combined_cost,
                            "yes_price": yes_trade.price,
                            "no_price": no_trade.price,
                            "edge": 1.0 - combined_cost
                        })

        if paired_entries:
            avg_threshold = statistics.mean([p["combined_cost"] for p in paired_entries])
            rules.append(Rule(
                condition=f"sum(best_bid_yes + best_bid_no) < {avg_threshold:.3f}",
                value=avg_threshold,
                confidence=0.9,
                evidence_count=len(paired_entries),
                rule_type=RuleType.ENTRY_CONDITION,
                metadata={
                    "avg_edge": statistics.mean([p["edge"] for p in paired_entries]),
                    "type": "binary_arbitrage"
                }
            ))

            rules.append(Rule(
                condition="Buy equal shares of YES and NO",
                value="paired_hedge",
                confidence=0.95,
                evidence_count=len(paired_entries),
                rule_type=RuleType.ENTRY_CONDITION,
                metadata={"type": "hedging"}
            ))

        return rules

    def _extract_multi_arb_entry(self, trades: List[Trade]) -> List[Rule]:
        """Extract entry rules for multi-outcome arbitrage"""
        rules = []

        # Find markets where multiple outcomes were bought
        market_positions = self._group_trades_by_market(trades)
        multi_entries = []

        for market_trades in market_positions.values():
            if not market_trades or market_trades[0].market_type != "multi":
                continue

            buys = [t for t in market_trades if t.side == "BUY"]
            unique_outcomes = {t.outcome for t in buys}

            if len(unique_outcomes) >= 3:
                # Calculate total cost
                total_cost = sum(t.value for t in buys)
                # Estimate shares (assuming equal)
                shares = min(t.shares for t in buys) if buys else 0
                cost_per_set = total_cost / shares if shares > 0 else 0

                multi_entries.append({
                    "outcomes_count": len(unique_outcomes),
                    "cost_per_set": cost_per_set,
                    "edge": 1.0 - cost_per_set if cost_per_set < 1 else 0
                })

        if multi_entries:
            avg_outcomes = statistics.mean([e["outcomes_count"] for e in multi_entries])
            avg_cost = statistics.mean([e["cost_per_set"] for e in multi_entries])
            avg_edge = statistics.mean([e["edge"] for e in multi_entries])

            rules.append(Rule(
                condition=f"sum(all_outcome_prices) < {avg_cost:.3f}",
                value=avg_cost,
                confidence=0.85,
                evidence_count=len(multi_entries),
                rule_type=RuleType.ENTRY_CONDITION,
                metadata={
                    "avg_outcomes": avg_outcomes,
                    "avg_edge": avg_edge,
                    "type": "multi_arbitrage"
                }
            ))

            rules.append(Rule(
                condition=f"Buy equal shares of all {int(avg_outcomes)} outcomes",
                value=int(avg_outcomes),
                confidence=0.9,
                evidence_count=len(multi_entries),
                rule_type=RuleType.ENTRY_CONDITION,
                metadata={"type": "multi_hedge"}
            ))

        return rules

    def _extract_mm_entry(self, trades: List[Trade]) -> List[Rule]:
        """Extract entry rules for market making"""
        rules = []

        # Analyze spreads and timing
        # This is simplified - real MM analysis would need order book data
        buys = [t for t in trades if t.side == "BUY"]

        if buys:
            avg_price = statistics.mean([t.price for t in buys])

            rules.append(Rule(
                condition=f"Post limit orders at mid ± spread_target",
                value=avg_price,
                confidence=0.7,
                evidence_count=len(buys),
                rule_type=RuleType.ENTRY_CONDITION,
                metadata={"type": "market_making", "avg_entry_price": avg_price}
            ))

        return rules

    def _extract_directional_entry(self, trades: List[Trade]) -> List[Rule]:
        """Extract entry rules for directional trading"""
        rules = []

        # Analyze entry prices and outcomes
        buys = [t for t in trades if t.side == "BUY"]

        if buys:
            yes_buys = [t for t in buys if t.outcome == "YES"]
            no_buys = [t for t in buys if t.outcome == "NO"]

            if yes_buys:
                avg_yes_price = statistics.mean([t.price for t in yes_buys])
                rules.append(Rule(
                    condition=f"Buy YES when undervalued (avg entry: {avg_yes_price:.2f})",
                    value=avg_yes_price,
                    confidence=0.6,
                    evidence_count=len(yes_buys),
                    rule_type=RuleType.ENTRY_CONDITION,
                    metadata={"direction": "bullish"}
                ))

            if no_buys:
                avg_no_price = statistics.mean([t.price for t in no_buys])
                rules.append(Rule(
                    condition=f"Buy NO when overvalued (avg entry: {avg_no_price:.2f})",
                    value=avg_no_price,
                    confidence=0.6,
                    evidence_count=len(no_buys),
                    rule_type=RuleType.ENTRY_CONDITION,
                    metadata={"direction": "bearish"}
                ))

        return rules

    def _extract_sniper_entry(self, trades: List[Trade]) -> List[Rule]:
        """Extract entry rules for sniping/event-driven trading"""
        rules = []

        # Analyze entry timing
        if len(trades) > 1:
            # Look for clustering of trades (suggests event triggers)
            trade_times = sorted([t.timestamp for t in trades])
            time_gaps = [(trade_times[i+1] - trade_times[i]).total_seconds()
                        for i in range(len(trade_times)-1)]

            # Find rapid sequences (gap < 10 seconds)
            rapid_sequences = sum(1 for gap in time_gaps if gap < 10)

            if rapid_sequences / len(time_gaps) > 0.3:
                rules.append(Rule(
                    condition="Trigger on rapid market events (< 10s response time)",
                    value=10,
                    confidence=0.75,
                    evidence_count=rapid_sequences,
                    rule_type=RuleType.ENTRY_CONDITION,
                    metadata={"type": "event_triggered"}
                ))

        return rules

    def _group_trades_by_market(self, trades: List[Trade]) -> Dict[str, List[Trade]]:
        """Group trades by market ID"""
        groups = defaultdict(list)
        for trade in trades:
            groups[trade.market_id].append(trade)
        return dict(groups)

    def _calculate_max_concurrent_exposure(self, trades: List[Trade]) -> float:
        """Calculate maximum concurrent position exposure"""
        if not trades:
            return 0

        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda t: t.timestamp)

        # Simulate running exposure
        max_exposure = 0
        current_exposure = 0

        for trade in sorted_trades:
            if trade.side == "BUY":
                current_exposure += trade.value
            else:
                current_exposure -= trade.value

            max_exposure = max(max_exposure, current_exposure)

        return max_exposure

    def _calculate_edge(self, trades: List[Trade], analysis: WalletAnalysis) -> Dict[str, float]:
        """Calculate estimated edge metrics"""
        edge = {}

        if trades and analysis.wallet.active_days > 0:
            daily_pnl = analysis.wallet.total_pnl / analysis.wallet.active_days
            edge["daily_pnl"] = round(daily_pnl, 2)

            # Estimate per-trade profit
            if analysis.wallet.total_trades > 0:
                per_trade = analysis.wallet.total_pnl / analysis.wallet.total_trades
                edge["per_trade_pnl"] = round(per_trade, 2)

                # Calculate as percentage of avg trade size
                if analysis.avg_trade_size > 0:
                    edge["per_trade_pct"] = round(per_trade / analysis.avg_trade_size * 100, 2)

        return edge

    def _estimate_capital_required(self, trades: List[Trade], analysis: WalletAnalysis) -> float:
        """Estimate minimum capital required to replicate strategy"""
        if not trades:
            return 0

        # Base on max concurrent exposure + buffer
        max_exposure = self._calculate_max_concurrent_exposure(trades)

        # Add 50% buffer for volatility and opportunities
        required = max_exposure * 1.5

        # Minimum $1000
        return max(required, 1000)

    def _calculate_replicability(
        self,
        entry_rules: List[Rule],
        exit_rules: List[Rule],
        sizing_rules: List[Rule],
        market_filters: List[Rule]
    ) -> float:
        """
        Calculate how easy it is to replicate this strategy

        High replicability = clear, simple rules with high confidence
        Low replicability = complex, opaque, or low-confidence patterns
        """
        scores = []

        # Score based on rule clarity
        all_rules = entry_rules + exit_rules + sizing_rules + market_filters

        if not all_rules:
            return 0.3  # Unknown strategy

        # Average confidence across all rules
        avg_confidence = statistics.mean([r.confidence for r in all_rules])
        scores.append(avg_confidence)

        # Completeness: do we have all rule types?
        rule_types_present = {r.rule_type for r in all_rules}
        completeness = len(rule_types_present) / len(RuleType)
        scores.append(completeness)

        # Evidence strength: higher evidence = more replicable
        total_evidence = sum(r.evidence_count for r in all_rules)
        evidence_score = min(total_evidence / 1000, 1.0)  # Cap at 1000
        scores.append(evidence_score)

        # Simplicity: fewer rules = easier to replicate
        simplicity = max(0, 1 - len(all_rules) / 20)  # 20+ rules is complex
        scores.append(simplicity * 0.5)  # Lower weight

        return statistics.mean(scores)

    def _estimate_timeframe(self, trades: List[Trade], analysis: WalletAnalysis) -> str:
        """Estimate typical holding period"""
        if not analysis:
            return "unknown"

        period = analysis.avg_holding_period

        if period < timedelta(minutes=30):
            return "< 30 minutes"
        elif period < timedelta(hours=2):
            return "< 2 hours"
        elif period < timedelta(days=1):
            return "< 1 day"
        elif period < timedelta(days=7):
            return "< 1 week"
        elif period < timedelta(days=30):
            return "< 1 month"
        else:
            return "> 1 month"

    def _assess_risk_profile(
        self,
        strategy_type: StrategyType,
        trades: List[Trade],
        analysis: WalletAnalysis
    ) -> str:
        """Assess overall risk profile"""
        if strategy_type in [StrategyType.ARBITRAGE_BINARY, StrategyType.ARBITRAGE_MULTI]:
            return "Very Low (hedged arbitrage)"
        elif strategy_type == StrategyType.MARKET_MAKER:
            return "Low (inventory risk only)"
        elif strategy_type == StrategyType.DIRECTIONAL:
            if analysis and analysis.win_rate > 0.7:
                return "Medium (directional with high win rate)"
            else:
                return "High (directional)"
        elif strategy_type == StrategyType.SNIPER:
            return "Medium (timing dependent)"
        else:
            return "Unknown"

    def _generate_notes(
        self,
        strategy_type: StrategyType,
        trades: List[Trade],
        analysis: WalletAnalysis
    ) -> str:
        """Generate additional observations and notes"""
        notes = []

        if strategy_type == StrategyType.ARBITRAGE_BINARY:
            notes.append("Binary arbitrage: Buy YES+NO when sum < $1, hold to resolution")
            notes.append("Risk-free mathematical edge, limited by market inefficiencies")
        elif strategy_type == StrategyType.ARBITRAGE_MULTI:
            notes.append("Multi-outcome arbitrage: Buy all candidates when sum < $1")
            notes.append("Massive edge potential but capital-intensive and long holding periods")

        if analysis:
            if analysis.win_rate > 0.9:
                notes.append(f"Exceptional win rate ({analysis.win_rate:.1%}) suggests systematic edge")

            if analysis.wallet.active_days > 100:
                notes.append(f"Sustained activity over {analysis.wallet.active_days} days indicates robust strategy")

        return "\n".join(notes)


# Utility functions for outputting blueprints

def to_json(blueprint: StrategyBlueprint) -> str:
    """
    Convert blueprint to JSON string

    Args:
        blueprint: Strategy blueprint

    Returns:
        JSON string representation
    """
    # Convert enums and dataclasses to dicts
    def serialize(obj):
        if isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, '__dict__'):
            return {k: serialize(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        else:
            return obj

    return json.dumps(serialize(blueprint), indent=2)


def to_markdown(blueprint: StrategyBlueprint) -> str:
    """
    Generate detailed markdown report of the strategy

    Args:
        blueprint: Strategy blueprint

    Returns:
        Formatted markdown string
    """
    lines = []
    lines.append(f"# Strategy Blueprint: {blueprint.name}")
    lines.append("")
    lines.append(f"**Type:** {blueprint.strategy_type.value}")
    lines.append(f"**Replicability Score:** {blueprint.replicability_score:.1%}")
    lines.append(f"**Capital Required:** ${blueprint.capital_required:,.0f}")
    lines.append("")

    lines.append("## Performance Metrics")
    lines.append("")
    lines.append(f"- **Trade Frequency:** {blueprint.trade_frequency:.0f} trades/day")
    lines.append(f"- **Win Rate:** {blueprint.win_rate:.1%}")
    lines.append(f"- **Typical Timeframe:** {blueprint.timeframe}")
    lines.append(f"- **Risk Profile:** {blueprint.risk_profile}")
    lines.append("")

    lines.append("## Estimated Edge")
    lines.append("")
    for key, value in blueprint.estimated_edge.items():
        lines.append(f"- **{key}:** {value}")
    lines.append("")

    if blueprint.market_filters:
        lines.append("## Market Selection Rules")
        lines.append("")
        for i, rule in enumerate(blueprint.market_filters, 1):
            lines.append(f"{i}. **{rule.condition}**")
            lines.append(f"   - Confidence: {rule.confidence:.1%}")
            lines.append(f"   - Evidence: {rule.evidence_count} trades")
            lines.append("")

    if blueprint.entry_rules:
        lines.append("## Entry Rules")
        lines.append("")
        for i, rule in enumerate(blueprint.entry_rules, 1):
            lines.append(f"{i}. **{rule.condition}**")
            lines.append(f"   - Value: `{rule.value}`")
            lines.append(f"   - Confidence: {rule.confidence:.1%}")
            lines.append(f"   - Evidence: {rule.evidence_count} occurrences")
            lines.append("")

    if blueprint.exit_rules:
        lines.append("## Exit Rules")
        lines.append("")
        for i, rule in enumerate(blueprint.exit_rules, 1):
            lines.append(f"{i}. **{rule.condition}**")
            lines.append(f"   - Value: `{rule.value}`")
            lines.append(f"   - Confidence: {rule.confidence:.1%}")
            lines.append(f"   - Evidence: {rule.evidence_count} occurrences")
            lines.append("")

    if blueprint.sizing_rules:
        lines.append("## Position Sizing Rules")
        lines.append("")
        for i, rule in enumerate(blueprint.sizing_rules, 1):
            lines.append(f"{i}. **{rule.condition}**")
            lines.append(f"   - Value: `{rule.value}`")
            lines.append(f"   - Confidence: {rule.confidence:.1%}")
            lines.append("")

    if blueprint.additional_notes:
        lines.append("## Additional Notes")
        lines.append("")
        lines.append(blueprint.additional_notes)
        lines.append("")

    return "\n".join(lines)


def to_config(blueprint: StrategyBlueprint) -> Dict[str, Any]:
    """
    Convert blueprint to configuration dict suitable for bot implementation

    Args:
        blueprint: Strategy blueprint

    Returns:
        Configuration dictionary
    """
    config = {
        "strategy_name": blueprint.name,
        "strategy_type": blueprint.strategy_type.value,
        "capital": blueprint.capital_required,
        "risk_profile": blueprint.risk_profile,

        "entry_conditions": [
            {
                "condition": rule.condition,
                "threshold": rule.value,
                "required": rule.confidence > 0.8
            }
            for rule in blueprint.entry_rules
        ],

        "exit_conditions": [
            {
                "condition": rule.condition,
                "threshold": rule.value,
                "required": rule.confidence > 0.8
            }
            for rule in blueprint.exit_rules
        ],

        "sizing": {
            "rules": [
                {
                    "description": rule.condition,
                    "value": rule.value,
                    "metadata": rule.metadata
                }
                for rule in blueprint.sizing_rules
            ]
        },

        "market_filters": [
            {
                "filter": rule.condition,
                "value": rule.value,
                "required": rule.confidence > 0.7
            }
            for rule in blueprint.market_filters
        ],

        "expected_performance": {
            "trade_frequency": blueprint.trade_frequency,
            "win_rate": blueprint.win_rate,
            "edge": blueprint.estimated_edge
        }
    }

    return config
