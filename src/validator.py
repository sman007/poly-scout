"""
Edge validator for poly-scout.

Validates that opportunities are real and executable:
- Checks order book liquidity
- Calculates slippage
- Verifies edge against external sources
- Calculates net profit after fees
"""

import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

import httpx

from src.config import (
    CLOB_API_BASE, GAMMA_API_BASE,
    MIN_EDGE_PCT, MIN_LIQUIDITY_USD, MAX_SLIPPAGE_PCT, MIN_EXPECTED_PROFIT
)


def log(msg: str):
    print(f"[VALIDATOR] {msg}", flush=True)


@dataclass
class ValidationResult:
    """Result of validating an opportunity."""
    is_valid: bool
    edge_pct: float
    liquidity_usd: float
    slippage_pct: float
    expected_profit: float
    entry_price: float
    effective_price: float
    fees_usd: float
    failure_reason: Optional[str] = None


class EdgeValidator:
    """Validate that opportunities are real and executable."""

    # Polymarket fee structure
    TAKER_FEE_PCT = 0.02  # 2% taker fee on profit

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    async def get_order_book(self, token_id: str) -> Optional[dict]:
        """Get order book for a market from CLOB API."""
        try:
            url = f"{CLOB_API_BASE}/book"
            params = {"token_id": token_id}
            resp = await self.client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log(f"Order book error: {e}")
        return None

    async def get_market_info(self, condition_id: str) -> Optional[dict]:
        """Get market info from CLOB API."""
        try:
            url = f"{CLOB_API_BASE}/markets/{condition_id}"
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log(f"Market info error: {e}")
        return None

    def calculate_liquidity(self, book: dict, side: str) -> float:
        """Calculate total liquidity available on a side."""
        orders = book.get("bids" if side == "BUY" else "asks", [])
        total = 0.0
        for order in orders:
            price = float(order.get("price", 0))
            size = float(order.get("size", 0))
            total += price * size
        return total

    def calculate_slippage(self, book: dict, side: str, order_size_usd: float) -> tuple[float, float]:
        """
        Calculate slippage for an order.

        Returns:
            (effective_price, slippage_pct)
        """
        orders = book.get("bids" if side == "SELL" else "asks", [])

        if not orders:
            return 0.0, 100.0

        # Sort orders by price (best first)
        if side == "BUY":
            orders = sorted(orders, key=lambda x: float(x.get("price", 0)))
        else:
            orders = sorted(orders, key=lambda x: -float(x.get("price", 0)))

        filled = 0.0
        total_cost = 0.0
        best_price = float(orders[0].get("price", 0)) if orders else 0

        for order in orders:
            price = float(order.get("price", 0))
            size = float(order.get("size", 0))
            order_value = price * size

            if filled + order_value >= order_size_usd:
                # Partial fill of this order
                remaining = order_size_usd - filled
                total_cost += remaining
                filled = order_size_usd
                break
            else:
                filled += order_value
                total_cost += order_value

        if filled < order_size_usd:
            # Not enough liquidity
            return 0.0, 100.0

        effective_price = total_cost / order_size_usd
        slippage_pct = abs(effective_price - best_price) / best_price * 100 if best_price else 0

        return effective_price, slippage_pct

    def calculate_expected_profit(
        self,
        order_size_usd: float,
        entry_price: float,
        fair_value: float,
        side: str
    ) -> tuple[float, float]:
        """
        Calculate expected profit and fees.

        Returns:
            (expected_profit, fees)
        """
        if side == "BUY":
            # Buying underpriced: profit = (fair_value - entry_price) * shares
            shares = order_size_usd / entry_price
            gross_profit = (fair_value - entry_price) * shares
        else:
            # Selling overpriced: profit = (entry_price - fair_value) * shares
            shares = order_size_usd / (1 - entry_price)  # Selling NO
            gross_profit = (entry_price - fair_value) * shares

        # Calculate fees (2% on profit)
        fees = max(0, gross_profit * self.TAKER_FEE_PCT)
        net_profit = gross_profit - fees

        return net_profit, fees

    async def validate_opportunity(
        self,
        market_slug: str,
        outcome: str,
        pm_price: float,
        fair_value: float,
        order_size_usd: float = 500
    ) -> ValidationResult:
        """
        Validate an opportunity is real and executable.

        Args:
            market_slug: PM event slug
            outcome: Outcome name (e.g., "Hawks")
            pm_price: Current PM price
            fair_value: Fair value (e.g., from sportsbook)
            order_size_usd: Size of order to place

        Returns:
            ValidationResult with all metrics
        """
        # Determine action
        edge_pct = (fair_value - pm_price) * 100
        action = "BUY" if edge_pct > 0 else "SELL"

        # Get market info to find token_id
        try:
            url = f"{GAMMA_API_BASE}/events?slug={market_slug}"
            resp = await self.client.get(url)
            if resp.status_code != 200:
                return ValidationResult(
                    is_valid=False,
                    edge_pct=edge_pct,
                    liquidity_usd=0,
                    slippage_pct=0,
                    expected_profit=0,
                    entry_price=pm_price,
                    effective_price=pm_price,
                    fees_usd=0,
                    failure_reason="Could not fetch market"
                )

            event = resp.json()[0] if resp.json() else None
            if not event:
                return ValidationResult(
                    is_valid=False, edge_pct=edge_pct, liquidity_usd=0, slippage_pct=0,
                    expected_profit=0, entry_price=pm_price, effective_price=pm_price,
                    fees_usd=0, failure_reason="Market not found"
                )

            # Find the right market/token
            token_id = None
            for m in event.get("markets", []):
                outcomes = m.get("outcomes", "[]")
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)
                if outcome in outcomes:
                    # Get clobTokenIds
                    clob_ids = m.get("clobTokenIds", "[]")
                    if isinstance(clob_ids, str):
                        clob_ids = json.loads(clob_ids)
                    idx = outcomes.index(outcome)
                    if idx < len(clob_ids):
                        token_id = clob_ids[idx]
                    break

            if not token_id:
                # Can't get order book, estimate based on volume
                volume = float(event.get("volume", 0))
                estimated_liquidity = volume * 0.01  # Rough estimate

                profit, fees = self.calculate_expected_profit(
                    order_size_usd, pm_price, fair_value, action
                )

                return ValidationResult(
                    is_valid=abs(edge_pct) >= MIN_EDGE_PCT and profit >= MIN_EXPECTED_PROFIT,
                    edge_pct=edge_pct,
                    liquidity_usd=estimated_liquidity,
                    slippage_pct=0.5,  # Estimate
                    expected_profit=profit,
                    entry_price=pm_price,
                    effective_price=pm_price,
                    fees_usd=fees,
                    failure_reason=None if profit >= MIN_EXPECTED_PROFIT else "Profit too low"
                )

            # Get order book
            book = await self.get_order_book(token_id)
            if not book:
                return ValidationResult(
                    is_valid=False, edge_pct=edge_pct, liquidity_usd=0, slippage_pct=0,
                    expected_profit=0, entry_price=pm_price, effective_price=pm_price,
                    fees_usd=0, failure_reason="Could not fetch order book"
                )

            # Calculate liquidity
            liquidity = self.calculate_liquidity(book, action)

            # Calculate slippage
            effective_price, slippage_pct = self.calculate_slippage(book, action, order_size_usd)

            if effective_price == 0:
                return ValidationResult(
                    is_valid=False, edge_pct=edge_pct, liquidity_usd=liquidity,
                    slippage_pct=100, expected_profit=0, entry_price=pm_price,
                    effective_price=pm_price, fees_usd=0,
                    failure_reason="Insufficient liquidity"
                )

            # Calculate profit with actual entry price
            profit, fees = self.calculate_expected_profit(
                order_size_usd, effective_price, fair_value, action
            )

            # Validate all criteria
            is_valid = (
                abs(edge_pct) >= MIN_EDGE_PCT and
                liquidity >= MIN_LIQUIDITY_USD and
                slippage_pct <= MAX_SLIPPAGE_PCT and
                profit >= MIN_EXPECTED_PROFIT
            )

            failure_reason = None
            if not is_valid:
                if abs(edge_pct) < MIN_EDGE_PCT:
                    failure_reason = f"Edge too small ({edge_pct:.1f}% < {MIN_EDGE_PCT}%)"
                elif liquidity < MIN_LIQUIDITY_USD:
                    failure_reason = f"Liquidity too low (${liquidity:.0f} < ${MIN_LIQUIDITY_USD})"
                elif slippage_pct > MAX_SLIPPAGE_PCT:
                    failure_reason = f"Slippage too high ({slippage_pct:.1f}% > {MAX_SLIPPAGE_PCT}%)"
                elif profit < MIN_EXPECTED_PROFIT:
                    failure_reason = f"Profit too low (${profit:.2f} < ${MIN_EXPECTED_PROFIT})"

            return ValidationResult(
                is_valid=is_valid,
                edge_pct=edge_pct,
                liquidity_usd=liquidity,
                slippage_pct=slippage_pct,
                expected_profit=profit,
                entry_price=pm_price,
                effective_price=effective_price,
                fees_usd=fees,
                failure_reason=failure_reason
            )

        except Exception as e:
            log(f"Validation error: {e}")
            return ValidationResult(
                is_valid=False, edge_pct=edge_pct, liquidity_usd=0, slippage_pct=0,
                expected_profit=0, entry_price=pm_price, effective_price=pm_price,
                fees_usd=0, failure_reason=str(e)
            )


async def main():
    """Test the validator."""
    async with EdgeValidator() as validator:
        # Test with a known market
        result = await validator.validate_opportunity(
            market_slug="nba-mil-atl-2026-01-19",
            outcome="Hawks",
            pm_price=0.555,
            fair_value=0.583,
            order_size_usd=500
        )

        print(f"\nValidation Result:")
        print(f"  Valid: {result.is_valid}")
        print(f"  Edge: {result.edge_pct:+.1f}%")
        print(f"  Liquidity: ${result.liquidity_usd:,.0f}")
        print(f"  Slippage: {result.slippage_pct:.2f}%")
        print(f"  Entry: {result.entry_price:.1%} -> Effective: {result.effective_price:.1%}")
        print(f"  Expected profit: ${result.expected_profit:.2f}")
        print(f"  Fees: ${result.fees_usd:.2f}")
        if result.failure_reason:
            print(f"  Reason: {result.failure_reason}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
