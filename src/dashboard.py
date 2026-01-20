"""
Paper Trading Dashboard for poly-scout.

A simple web dashboard to monitor paper trading performance.

Usage:
    python -m src.dashboard              # Run on port 8080
    python -m src.dashboard --port 5000  # Custom port
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from flask import Flask, render_template_string, jsonify

from src.config import GAMMA_API_BASE


PAPER_PORTFOLIO_FILE = "./data/paper_portfolio.json"

app = Flask(__name__)


def load_portfolio() -> dict:
    """Load portfolio from disk."""
    try:
        path = Path(PAPER_PORTFOLIO_FILE)
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "starting_balance": 10000.0,
        "current_balance": 10000.0,
        "positions": [],
        "closed_positions": [],
        "total_pnl": 0.0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
    }


async def fetch_current_prices(positions: list) -> dict:
    """Fetch current prices for open positions."""
    prices = {}
    async with httpx.AsyncClient(timeout=30) as client:
        # Group by slug to minimize API calls
        slugs = set(pos["slug"] for pos in positions)

        for slug in list(slugs)[:50]:  # Limit to 50 to avoid rate limits
            try:
                url = f"{GAMMA_API_BASE}/events?slug={slug}"
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                events = resp.json()
                if not events:
                    continue

                event = events[0]
                for market in event.get("markets", []):
                    outcomes = market.get("outcomes", [])
                    prices_str = market.get("outcomePrices", "[]")
                    try:
                        price_list = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
                        price_list = [float(p) for p in price_list]
                    except Exception:
                        continue

                    for i, outcome in enumerate(outcomes):
                        if i < len(price_list):
                            key = f"{slug}:{outcome.upper()}"
                            prices[key] = price_list[i]
            except Exception:
                continue

    return prices


def get_portfolio_with_prices() -> dict:
    """Get portfolio with current prices and unrealized P&L."""
    portfolio = load_portfolio()

    # Calculate unrealized P&L (sync version - estimates)
    open_positions = portfolio.get("positions", [])
    total_invested = sum(pos.get("amount_invested", 0) for pos in open_positions)

    return {
        "portfolio": portfolio,
        "total_invested": total_invested,
        "timestamp": datetime.now().isoformat(),
    }


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Paper Trading Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.5;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #58a6ff;
            margin-bottom: 20px;
            font-size: 1.8rem;
        }
        h2 {
            color: #8b949e;
            margin: 20px 0 10px;
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }
        .stat-label {
            color: #8b949e;
            font-size: 0.85rem;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: 600;
        }
        .stat-value.positive { color: #3fb950; }
        .stat-value.negative { color: #f85149; }
        .stat-value.neutral { color: #58a6ff; }
        .positions-table {
            width: 100%;
            border-collapse: collapse;
            background: #161b22;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 30px;
        }
        .positions-table th,
        .positions-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }
        .positions-table th {
            background: #21262d;
            color: #8b949e;
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        .positions-table tr:hover {
            background: #1f2428;
        }
        .positions-table td:nth-child(1) {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .badge-yes { background: #238636; color: #fff; }
        .badge-no { background: #da3633; color: #fff; }
        .badge-won { background: #238636; color: #fff; }
        .badge-lost { background: #da3633; color: #fff; }
        .badge-profit { background: #1f6feb; color: #fff; }
        .refresh-info {
            text-align: center;
            color: #8b949e;
            font-size: 0.85rem;
            margin-top: 20px;
        }
        .pnl-positive { color: #3fb950; }
        .pnl-negative { color: #f85149; }
        .mobile-scroll {
            overflow-x: auto;
        }
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .stat-value {
                font-size: 1.4rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 Paper Trading Dashboard</h1>

        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <div class="stat-label">Starting Balance</div>
                <div class="stat-value neutral" id="starting-balance">$10,000.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Current Balance</div>
                <div class="stat-value neutral" id="current-balance">$0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Invested</div>
                <div class="stat-value neutral" id="total-invested">$0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Realized P&L</div>
                <div class="stat-value" id="total-pnl">$0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Return</div>
                <div class="stat-value" id="return-pct">0.0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value neutral" id="win-rate">0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Open Positions</div>
                <div class="stat-value neutral" id="open-count">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value neutral" id="total-trades">0</div>
            </div>
        </div>

        <h2>Open Positions (<span id="open-positions-count">0</span>)</h2>
        <div class="mobile-scroll">
            <table class="positions-table">
                <thead>
                    <tr>
                        <th>Market</th>
                        <th>Side</th>
                        <th>Entry</th>
                        <th>Shares</th>
                        <th>Invested</th>
                        <th>Kelly %</th>
                    </tr>
                </thead>
                <tbody id="open-positions">
                </tbody>
            </table>
        </div>

        <h2>Recent Closed Trades (<span id="closed-count">0</span>)</h2>
        <div class="mobile-scroll">
            <table class="positions-table">
                <thead>
                    <tr>
                        <th>Market</th>
                        <th>Side</th>
                        <th>Entry</th>
                        <th>Exit</th>
                        <th>P&L</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody id="closed-positions">
                </tbody>
            </table>
        </div>

        <div class="refresh-info">
            Auto-refreshes every 30 seconds | Last update: <span id="last-update">-</span>
        </div>
    </div>

    <script>
        function formatCurrency(value) {
            const num = parseFloat(value) || 0;
            const prefix = num >= 0 ? '$' : '-$';
            return prefix + Math.abs(num).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }

        function formatPct(value) {
            const num = parseFloat(value) || 0;
            const prefix = num >= 0 ? '+' : '';
            return prefix + num.toFixed(1) + '%';
        }

        function updateDashboard(data) {
            const p = data.portfolio;

            // Update stats
            document.getElementById('starting-balance').textContent = formatCurrency(p.starting_balance);
            document.getElementById('current-balance').textContent = formatCurrency(p.current_balance);
            document.getElementById('total-invested').textContent = formatCurrency(data.total_invested);

            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = formatCurrency(p.total_pnl);
            pnlEl.className = 'stat-value ' + (p.total_pnl >= 0 ? 'positive' : 'negative');

            const returnPct = (p.total_pnl / p.starting_balance) * 100;
            const returnEl = document.getElementById('return-pct');
            returnEl.textContent = formatPct(returnPct);
            returnEl.className = 'stat-value ' + (returnPct >= 0 ? 'positive' : 'negative');

            const winRate = p.wins + p.losses > 0 ? (p.wins / (p.wins + p.losses)) * 100 : 0;
            document.getElementById('win-rate').textContent = winRate.toFixed(0) + '%';
            document.getElementById('open-count').textContent = p.positions.length;
            document.getElementById('total-trades').textContent = p.total_trades;

            // Update open positions
            document.getElementById('open-positions-count').textContent = p.positions.length;
            const openTbody = document.getElementById('open-positions');
            openTbody.innerHTML = p.positions.slice(0, 50).map(pos => `
                <tr>
                    <td title="${pos.title}">${pos.title.substring(0, 50)}${pos.title.length > 50 ? '...' : ''}</td>
                    <td><span class="badge badge-${pos.outcome.toLowerCase()}">${pos.outcome}</span></td>
                    <td>$${pos.entry_price.toFixed(3)}</td>
                    <td>${pos.shares.toFixed(1)}</td>
                    <td>$${pos.amount_invested.toFixed(2)}</td>
                    <td>${((pos.kelly_fraction || 0) * 100).toFixed(1)}%</td>
                </tr>
            `).join('');

            // Update closed positions (most recent first)
            const closed = (p.closed_positions || []).slice(-20).reverse();
            document.getElementById('closed-count').textContent = p.closed_positions.length;
            const closedTbody = document.getElementById('closed-positions');
            closedTbody.innerHTML = closed.map(pos => {
                const pnlClass = pos.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
                let statusBadge = 'badge-lost';
                let statusText = 'LOST';
                if (pos.status === 'won') {
                    statusBadge = 'badge-won';
                    statusText = 'WON';
                } else if (pos.status && pos.status.startsWith('profit')) {
                    statusBadge = 'badge-profit';
                    statusText = pos.status.toUpperCase().replace('_', ' ');
                }
                return `
                    <tr>
                        <td title="${pos.title}">${pos.title.substring(0, 40)}${pos.title.length > 40 ? '...' : ''}</td>
                        <td><span class="badge badge-${pos.outcome.toLowerCase()}">${pos.outcome}</span></td>
                        <td>$${pos.entry_price.toFixed(3)}</td>
                        <td>$${(pos.exit_price || 0).toFixed(3)}</td>
                        <td class="${pnlClass}">${formatCurrency(pos.pnl)}</td>
                        <td><span class="badge ${statusBadge}">${statusText}</span></td>
                    </tr>
                `;
            }).join('');

            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }

        async function fetchData() {
            try {
                const resp = await fetch('/api/portfolio');
                const data = await resp.json();
                updateDashboard(data);
            } catch (err) {
                console.error('Failed to fetch data:', err);
            }
        }

        // Initial load
        fetchData();

        // Auto-refresh every 30 seconds
        setInterval(fetchData, 30000);
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    """Serve the dashboard page."""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/portfolio')
def api_portfolio():
    """API endpoint for portfolio data."""
    return jsonify(get_portfolio_with_prices())


def main():
    parser = argparse.ArgumentParser(description="Paper Trading Dashboard")
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to run on (default: 8080)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )

    args = parser.parse_args()

    print(f"Starting Paper Trading Dashboard on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
