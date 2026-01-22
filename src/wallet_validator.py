"""
Statistical validation for wallet analysis.
Only passes wallets with statistically significant edge.
"""

from dataclasses import dataclass
from typing import Optional, List

# Use scipy if available, fallback to manual calculation
try:
    from scipy.stats import binom_test
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def log(msg: str):
    print(f"[VALIDATOR] {msg}", flush=True)


def _manual_binom_test(successes: int, trials: int, p: float = 0.5) -> float:
    """
    Manual binomial test approximation using normal approximation.
    Returns p-value for one-tailed test (greater than p).
    """
    if trials < 30:
        return 1.0  # Not enough data for normal approximation

    # Normal approximation to binomial
    mean = trials * p
    std = (trials * p * (1 - p)) ** 0.5

    if std == 0:
        return 1.0

    # Z-score
    z = (successes - mean) / std

    # Approximate p-value using complementary error function approximation
    # For z > 0, p-value for greater-than test
    if z <= 0:
        return 1.0

    # Approximation of 1 - CDF(z) for standard normal
    # Using Abramowitz and Stegun approximation
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989423 * (2.718281828 ** (-z * z / 2))
    p_value = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))

    return max(0.0, min(1.0, p_value))


def _manual_variance(values: List[float]) -> float:
    """Calculate variance without numpy."""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)


@dataclass
class ValidationResult:
    is_valid: bool
    win_rate: float
    win_rate_pvalue: float
    consistency_variance: float
    sample_size: int
    confidence_level: str  # "HIGH", "MEDIUM", "LOW", "INSUFFICIENT"
    rejection_reason: Optional[str]


def validate_wallet(positions: list, trades: list) -> ValidationResult:
    """
    Run statistical tests on wallet data.
    Returns validation result with confidence level.

    Tests:
    1. Sample size >= 50 trades
    2. Win rate significantly better than random (p < 0.01)
    3. Consistent performance across time periods (variance < 0.03)
    """
    # Count wins/losses from positions
    wins = sum(1 for p in positions if float(p.get('cashPnl', 0)) > 0)
    losses = sum(1 for p in positions if float(p.get('cashPnl', 0)) < 0)
    total = wins + losses

    # Reject if insufficient sample
    if total < 50:
        return ValidationResult(
            is_valid=False,
            win_rate=wins / total if total > 0 else 0,
            win_rate_pvalue=1.0,
            consistency_variance=1.0,
            sample_size=total,
            confidence_level="INSUFFICIENT",
            rejection_reason=f"Only {total} trades, need 50+"
        )

    # Test 1: Win rate significance (binomial test)
    win_rate = wins / total

    if HAS_SCIPY:
        p_value = binom_test(wins, total, 0.5, alternative='greater')
    else:
        p_value = _manual_binom_test(wins, total, 0.5)

    if p_value > 0.01:  # Not 99% confident
        return ValidationResult(
            is_valid=False,
            win_rate=win_rate,
            win_rate_pvalue=p_value,
            consistency_variance=0,
            sample_size=total,
            confidence_level="LOW",
            rejection_reason=f"Win rate not significant (p={p_value:.4f})"
        )

    # Test 2: Consistency across time periods
    if len(trades) >= 100:
        chunk_size = len(trades) // 4
        win_rates = []
        for i in range(4):
            chunk = trades[i * chunk_size:(i + 1) * chunk_size]
            chunk_wins = sum(1 for t in chunk if float(t.get('profit', 0)) > 0)
            win_rates.append(chunk_wins / len(chunk) if chunk else 0)

        if HAS_NUMPY:
            variance = float(np.var(win_rates))
        else:
            variance = _manual_variance(win_rates)
    else:
        variance = 0.05  # Can't test, assume moderate

    if variance > 0.03:  # >3% variance = inconsistent
        return ValidationResult(
            is_valid=False,
            win_rate=win_rate,
            win_rate_pvalue=p_value,
            consistency_variance=variance,
            sample_size=total,
            confidence_level="LOW",
            rejection_reason=f"Inconsistent performance (var={variance:.4f})"
        )

    # Determine confidence level
    if win_rate > 0.90 and p_value < 0.001 and variance < 0.01:
        confidence = "HIGH"
    elif win_rate > 0.85 and p_value < 0.01 and variance < 0.02:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return ValidationResult(
        is_valid=True,
        win_rate=win_rate,
        win_rate_pvalue=p_value,
        consistency_variance=variance,
        sample_size=total,
        confidence_level=confidence,
        rejection_reason=None
    )


if __name__ == "__main__":
    # Test the validator
    print(f"scipy available: {HAS_SCIPY}")
    print(f"numpy available: {HAS_NUMPY}")

    # Mock data - 90 wins out of 100 trades
    mock_positions = [{"cashPnl": 100}] * 90 + [{"cashPnl": -50}] * 10
    mock_trades = [{"profit": 100}] * 90 + [{"profit": -50}] * 10

    result = validate_wallet(mock_positions, mock_trades)
    print(f"\nValidation Result:")
    print(f"  Valid: {result.is_valid}")
    print(f"  Win Rate: {result.win_rate:.1%}")
    print(f"  P-value: {result.win_rate_pvalue:.6f}")
    print(f"  Consistency: {result.consistency_variance:.4f}")
    print(f"  Confidence: {result.confidence_level}")
    print(f"  Rejection: {result.rejection_reason}")
