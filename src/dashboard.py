"""
Sniper Trading Dashboard for poly-scout.

A web dashboard to monitor sniper trading performance with:
- Score, exposure %, days to resolution tracking
- Selectivity stats (skip counts)
- Mobile responsive design

Usage:
    python -m src.dashboard              # Run on port 8080
    python -m src.dashboard --port 5000  # Custom port
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, jsonify


SNIPER_PORTFOLIO_FILE = "./data/sniper_portfolio.json"

app = Flask(__name__)


def load_portfolio() -> dict:
    """Load portfolio from disk."""
    try:
        path = Path(SNIPER_PORTFOLIO_FILE)
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
        "flips": 0,
        "cuts": 0,
        "resolutions": 0,
    }


def get_portfolio_data() -> dict:
    """Get portfolio with calculated stats."""
    portfolio = load_portfolio()

    # Calculate stats
    positions = portfolio.get("positions", [])
    total_invested = sum(pos.get("amount_invested", 0) for pos in positions)
    starting = portfolio.get("starting_balance", 10000)
    exposure_pct = (total_invested / starting * 100) if starting > 0 else 0

    # Average score
    scores = [pos.get("score", 0) for pos in positions]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Selectivity stats
    selectivity = {
        "skipped_no_end_date": portfolio.get("skipped_no_end_date", 0),
        "skipped_too_far_out": portfolio.get("skipped_too_far_out", 0),
        "skipped_low_score": portfolio.get("skipped_low_score", 0),
        "skipped_exposure_limit": portfolio.get("skipped_exposure_limit", 0),
        "skipped_low_liquidity": portfolio.get("skipped_low_liquidity", 0),
        "skipped_no_exit_liquidity": portfolio.get("skipped_no_exit_liquidity", 0),
        "skipped_stale_book": portfolio.get("skipped_stale_book", 0),
    }
    total_skipped = sum(selectivity.values())

    return {
        "portfolio": portfolio,
        "total_invested": total_invested,
        "exposure_pct": exposure_pct,
        "avg_score": avg_score,
        "selectivity": selectivity,
        "total_skipped": total_skipped,
        "timestamp": datetime.now().isoformat(),
    }


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sniper Dashboard</title>
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
            padding: 12px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #58a6ff;
            margin-bottom: 16px;
            font-size: 1.5rem;
        }
        h2 {
            color: #8b949e;
            margin: 16px 0 8px;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-bottom: 16px;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px;
        }
        .stat-label {
            color: #8b949e;
            font-size: 0.75rem;
            margin-bottom: 4px;
        }
        .stat-value {
            font-size: 1.4rem;
            font-weight: 600;
        }
        .stat-value.positive { color: #3fb950; }
        .stat-value.negative { color: #f85149; }
        .stat-value.neutral { color: #58a6ff; }

        /* Selectivity stats - compact row */
        .selectivity-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 16px;
            font-size: 0.8rem;
        }
        .skip-stat {
            color: #8b949e;
        }
        .skip-stat span {
            color: #f0883e;
            font-weight: 600;
        }

        .positions-table {
            width: 100%;
            border-collapse: collapse;
            background: #161b22;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 16px;
            font-size: 0.85rem;
        }
        .positions-table th,
        .positions-table td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }
        .positions-table th {
            background: #21262d;
            color: #8b949e;
            font-weight: 500;
            font-size: 0.75rem;
            text-transform: uppercase;
        }
        .positions-table tr:hover {
            background: #1f2428;
        }
        .positions-table td:nth-child(1) {
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.7rem;
            font-weight: 500;
        }
        .badge-yes { background: #238636; color: #fff; }
        .badge-no { background: #da3633; color: #fff; }
        .badge-won { background: #238636; color: #fff; }
        .badge-lost { background: #da3633; color: #fff; }
        .badge-flip { background: #1f6feb; color: #fff; }
        .badge-cut { background: #f0883e; color: #fff; }
        .pnl-positive { color: #3fb950; }
        .pnl-negative { color: #f85149; }
        .score-high { color: #3fb950; }
        .score-med { color: #f0883e; }
        .score-low { color: #f85149; }

        .mobile-scroll {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .refresh-info {
            text-align: center;
            color: #8b949e;
            font-size: 0.75rem;
            margin-top: 16px;
        }

        /* Mobile responsive */
        @media (max-width: 768px) {
            body { padding: 8px; }
            h1 { font-size: 1.2rem; margin-bottom: 12px; }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 8px;
            }
            .stat-card { padding: 10px; }
            .stat-value { font-size: 1.2rem; }
            .stat-label { font-size: 0.7rem; }
            .selectivity-row {
                font-size: 0.7rem;
                padding: 8px;
            }
            .positions-table {
                font-size: 0.75rem;
            }
            .positions-table th,
            .positions-table td {
                padding: 8px 6px;
            }
            .positions-table td:nth-child(1) {
                max-width: 120px;
            }
        }

        @media (max-width: 480px) {
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Sniper Dashboard</h1>

        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <div class="stat-label">Balance</div>
                <div class="stat-value neutral" id="current-balance">$10,000</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">P&L</div>
                <div class="stat-value" id="total-pnl">$0.00</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Exposure</div>
                <div class="stat-value neutral" id="exposure">0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Return</div>
                <div class="stat-value" id="return-pct">0.0%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Open</div>
                <div class="stat-value neutral" id="open-count">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Avg Score</div>
                <div class="stat-value neutral" id="avg-score">0.000</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Flips</div>
                <div class="stat-value positive" id="flips">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value neutral" id="win-rate">0%</div>
            </div>
        </div>

        <div class="selectivity-row" id="selectivity">
            <div class="skip-stat">Skipped: <span id="total-skipped">0</span></div>
            <div class="skip-stat">noDate: <span id="skip-nodate">0</span></div>
            <div class="skip-stat">farOut: <span id="skip-far">0</span></div>
            <div class="skip-stat">lowScore: <span id="skip-score">0</span></div>
            <div class="skip-stat">exposure: <span id="skip-exposure">0</span></div>
            <div class="skip-stat">lowLiq: <span id="skip-liq">0</span></div>
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
                        <th>Score</th>
                        <th>Days</th>
                    </tr>
                </thead>
                <tbody id="open-positions">
                </tbody>
            </table>
        </div>

        <h2>Closed Trades (<span id="closed-count">0</span>)</h2>
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
            Auto-refresh: 30s | <span id="last-update">-</span>
        </div>
    </div>

    <script>
        function formatCurrency(value, short = false) {
            const num = parseFloat(value) || 0;
            if (short && Math.abs(num) >= 1000) {
                return (num >= 0 ? '$' : '-$') + (Math.abs(num)/1000).toFixed(1) + 'k';
            }
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

        function getScoreClass(score) {
            if (score >= 0.6) return 'score-high';
            if (score >= 0.4) return 'score-med';
            return 'score-low';
        }

        function updateDashboard(data) {
            const p = data.portfolio;

            // Stats
            document.getElementById('current-balance').textContent = formatCurrency(p.current_balance, true);

            const pnlEl = document.getElementById('total-pnl');
            pnlEl.textContent = formatCurrency(p.total_pnl);
            pnlEl.className = 'stat-value ' + (p.total_pnl >= 0 ? 'positive' : 'negative');

            document.getElementById('exposure').textContent = data.exposure_pct.toFixed(0) + '%';

            const returnPct = (p.total_pnl / p.starting_balance) * 100;
            const returnEl = document.getElementById('return-pct');
            returnEl.textContent = formatPct(returnPct);
            returnEl.className = 'stat-value ' + (returnPct >= 0 ? 'positive' : 'negative');

            document.getElementById('open-count').textContent = p.positions.length;
            document.getElementById('avg-score').textContent = data.avg_score.toFixed(3);
            document.getElementById('flips').textContent = p.flips || 0;

            const totalClosed = (p.wins || 0) + (p.losses || 0) + (p.flips || 0);
            const wins = (p.wins || 0) + (p.flips || 0);
            const winRate = totalClosed > 0 ? (wins / totalClosed) * 100 : 0;
            document.getElementById('win-rate').textContent = winRate.toFixed(0) + '%';

            // Selectivity
            document.getElementById('total-skipped').textContent = data.total_skipped;
            document.getElementById('skip-nodate').textContent = data.selectivity.skipped_no_end_date;
            document.getElementById('skip-far').textContent = data.selectivity.skipped_too_far_out;
            document.getElementById('skip-score').textContent = data.selectivity.skipped_low_score;
            document.getElementById('skip-exposure').textContent = data.selectivity.skipped_exposure_limit;
            document.getElementById('skip-liq').textContent =
                data.selectivity.skipped_low_liquidity + data.selectivity.skipped_no_exit_liquidity;

            // Open positions
            document.getElementById('open-positions-count').textContent = p.positions.length;
            const openTbody = document.getElementById('open-positions');
            openTbody.innerHTML = p.positions.slice(0, 100).map(pos => {
                const score = pos.score || 0;
                const days = pos.days_to_resolution;
                const daysStr = days !== null && days !== undefined ? days + 'd' : '?';
                return `
                    <tr>
                        <td title="${pos.title}">${pos.title.substring(0, 35)}${pos.title.length > 35 ? '...' : ''}</td>
                        <td><span class="badge badge-${(pos.outcome || '').toLowerCase().includes('yes') ? 'yes' : 'no'}">${pos.outcome}</span></td>
                        <td>$${pos.entry_price.toFixed(3)}</td>
                        <td>${pos.shares.toFixed(0)}</td>
                        <td>$${pos.amount_invested.toFixed(0)}</td>
                        <td class="${getScoreClass(score)}">${score.toFixed(3)}</td>
                        <td>${daysStr}</td>
                    </tr>
                `;
            }).join('');

            // Closed positions (most recent first)
            const closed = (p.closed_positions || []).slice(-30).reverse();
            document.getElementById('closed-count').textContent = (p.closed_positions || []).length;
            const closedTbody = document.getElementById('closed-positions');
            closedTbody.innerHTML = closed.map(pos => {
                const pnlClass = pos.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
                let badgeClass = 'badge-lost';
                let statusText = 'LOST';
                const status = pos.status || '';

                if (status.includes('won') || status === 'won') {
                    badgeClass = 'badge-won';
                    statusText = 'WON';
                } else if (status.includes('flip')) {
                    badgeClass = 'badge-flip';
                    statusText = 'FLIP';
                } else if (status.includes('cut')) {
                    badgeClass = 'badge-cut';
                    statusText = 'CUT';
                } else if (status.includes('lost')) {
                    badgeClass = 'badge-lost';
                    statusText = 'LOST';
                }

                return `
                    <tr>
                        <td title="${pos.title}">${pos.title.substring(0, 30)}${pos.title.length > 30 ? '...' : ''}</td>
                        <td><span class="badge badge-${(pos.outcome || '').toLowerCase().includes('yes') ? 'yes' : 'no'}">${pos.outcome}</span></td>
                        <td>$${pos.entry_price.toFixed(3)}</td>
                        <td>$${(pos.exit_price || 0).toFixed(3)}</td>
                        <td class="${pnlClass}">${formatCurrency(pos.pnl)}</td>
                        <td><span class="badge ${badgeClass}">${statusText}</span></td>
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
                console.error('Failed to fetch:', err);
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
    return jsonify(get_portfolio_data())


def main():
    parser = argparse.ArgumentParser(description="Sniper Trading Dashboard")
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

    print(f"Starting Sniper Dashboard on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
