"""
Test script for analyze_profit_potential() and calculate_replicability() functions.
"""

import sys
sys.path.insert(0, 'C:\\Projects\\poly-scout')

from src.daemon import analyze_profit_potential, calculate_replicability

# Test Case 1: High-performing crypto arb strategy
print("=" * 60)
print("Test Case 1: High-performing crypto arb strategy")
print("=" * 60)

wallet_data_1 = {
    "total_profit": 5000,
    "account_age_days": 20
}

strategy_params_1 = {
    "strategy": "CRYPTO_ARB",
    "avg_trade_size": 150,
    "timing_pattern": "throughout"
}

saturation_1 = {
    "wallet_count": 3,
    "trend": "stable",
    "total_capital": 150000
}

profit_analysis_1 = analyze_profit_potential(wallet_data_1, strategy_params_1, saturation_1)

print("\nProfit Analysis:")
print(f"  Their total profit: ${profit_analysis_1['their_total_profit']:,.2f}")
print(f"  Their daily profit: ${profit_analysis_1['their_daily_profit']:,.2f}")
print(f"  Our daily estimate: ${profit_analysis_1['our_daily_estimate']:,.2f}")
print(f"  Our monthly estimate: ${profit_analysis_1['our_monthly_estimate']:,.2f}")
print(f"  Min capital required: ${profit_analysis_1['min_capital_required']:,.2f}")
print(f"  Daily ROI: {profit_analysis_1['daily_roi_pct']:.2f}%")
print(f"  Monthly ROI: {profit_analysis_1['monthly_roi_pct']:.2f}%")
print(f"  Saturation risk: {profit_analysis_1['saturation_risk']}")
print(f"  Edge durability: {profit_analysis_1['edge_durability']}")
print(f"  Verdict: {profit_analysis_1['verdict']}")
print(f"  Confidence: {profit_analysis_1['confidence']:.1f}%")

replicability_score_1 = calculate_replicability(strategy_params_1, saturation_1, profit_analysis_1)
print(f"\nReplicability Score: {replicability_score_1}/10")

# Test Case 2: Saturated market with high competition
print("\n" + "=" * 60)
print("Test Case 2: Saturated market (high competition)")
print("=" * 60)

wallet_data_2 = {
    "total_profit": 2000,
    "account_age_days": 15
}

strategy_params_2 = {
    "strategy": "CRYPTO_ARB",
    "avg_trade_size": 200,
    "timing_pattern": "immediate"  # Needs fast execution
}

saturation_2 = {
    "wallet_count": 8,  # Many competitors
    "trend": "increasing",  # Getting more crowded
    "total_capital": 500000
}

profit_analysis_2 = analyze_profit_potential(wallet_data_2, strategy_params_2, saturation_2)

print("\nProfit Analysis:")
print(f"  Their total profit: ${profit_analysis_2['their_total_profit']:,.2f}")
print(f"  Their daily profit: ${profit_analysis_2['their_daily_profit']:,.2f}")
print(f"  Our daily estimate: ${profit_analysis_2['our_daily_estimate']:,.2f}")
print(f"  Our monthly estimate: ${profit_analysis_2['our_monthly_estimate']:,.2f}")
print(f"  Min capital required: ${profit_analysis_2['min_capital_required']:,.2f}")
print(f"  Daily ROI: {profit_analysis_2['daily_roi_pct']:.2f}%")
print(f"  Monthly ROI: {profit_analysis_2['monthly_roi_pct']:.2f}%")
print(f"  Saturation risk: {profit_analysis_2['saturation_risk']}")
print(f"  Edge durability: {profit_analysis_2['edge_durability']}")
print(f"  Verdict: {profit_analysis_2['verdict']}")
print(f"  Confidence: {profit_analysis_2['confidence']:.1f}%")

replicability_score_2 = calculate_replicability(strategy_params_2, saturation_2, profit_analysis_2)
print(f"\nReplicability Score: {replicability_score_2}/10")

# Test Case 3: Unknown strategy (novel pattern)
print("\n" + "=" * 60)
print("Test Case 3: Unknown strategy with low profit")
print("=" * 60)

wallet_data_3 = {
    "total_profit": 800,
    "account_age_days": 25
}

strategy_params_3 = {
    "strategy": "UNKNOWN",
    "avg_trade_size": 500,  # Large trades
    "timing_pattern": "burst"
}

saturation_3 = {
    "wallet_count": 1,  # Unique strategy
    "trend": "stable",
    "total_capital": 10000
}

profit_analysis_3 = analyze_profit_potential(wallet_data_3, strategy_params_3, saturation_3)

print("\nProfit Analysis:")
print(f"  Their total profit: ${profit_analysis_3['their_total_profit']:,.2f}")
print(f"  Their daily profit: ${profit_analysis_3['their_daily_profit']:,.2f}")
print(f"  Our daily estimate: ${profit_analysis_3['our_daily_estimate']:,.2f}")
print(f"  Our monthly estimate: ${profit_analysis_3['our_monthly_estimate']:,.2f}")
print(f"  Min capital required: ${profit_analysis_3['min_capital_required']:,.2f}")
print(f"  Daily ROI: {profit_analysis_3['daily_roi_pct']:.2f}%")
print(f"  Monthly ROI: {profit_analysis_3['monthly_roi_pct']:.2f}%")
print(f"  Saturation risk: {profit_analysis_3['saturation_risk']}")
print(f"  Edge durability: {profit_analysis_3['edge_durability']}")
print(f"  Verdict: {profit_analysis_3['verdict']}")
print(f"  Confidence: {profit_analysis_3['confidence']:.1f}%")

replicability_score_3 = calculate_replicability(strategy_params_3, saturation_3, profit_analysis_3)
print(f"\nReplicability Score: {replicability_score_3}/10")

print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print(f"Test Case 1 (Good crypto arb): {profit_analysis_1['verdict']} - Score {replicability_score_1}/10")
print(f"Test Case 2 (Saturated market): {profit_analysis_2['verdict']} - Score {replicability_score_2}/10")
print(f"Test Case 3 (Unknown, low profit): {profit_analysis_3['verdict']} - Score {replicability_score_3}/10")
print("\nAll tests completed successfully!")
