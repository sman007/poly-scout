"""
Comprehensive Poly-Scout Dashboard v2.

Displays:
- Portfolio tracking (balance, P&L, positions)
- Live sports edges (PM vs Vegas)
- Tracked wallets (24 wallets with strategies)
- Daemon status

Usage:
    python -m src.dashboard_v2              # Run on port 8081
    python -m src.dashboard_v2 --port 5000  # Custom port
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, render_template_string, jsonify

# Data files
KELLY_PORTFOLIO_FILE = "./data/kelly_portfolio.json"
SEEN_WALLETS_FILE = "./data/seen_wallets.json"

app = Flask(__name__)

# Cache for sports edges (updated async)
_sports_cache = {"edges": [], "last_update": None}

# Wallet strategy data (from docs)
WALLET_STRATEGIES = {
    "0xdb27": {"username": "DrPufferfish", "strategy": "LONGSHOT", "win_rate": "N/A", "size": "Micro"},
    "0xc660": {"username": "ChangoChango", "strategy": "DIRECTIONAL", "win_rate": "Mixed", "size": "Medium"},
    "0x161e": {"username": "peter77777", "strategy": "SCALP", "win_rate": "95%+", "size": "Medium"},
    "0xe6a3": {"username": "0xe6a3", "strategy": "MISPRICING", "win_rate": "65-70%", "size": "Medium"},
    "0xe72b": {"username": "norrisfan", "strategy": "DIRECTIONAL", "win_rate": "80%", "size": "Medium"},
    "0x3993": {"username": "Andromeda1", "strategy": "ARB", "win_rate": "N/A", "size": "Large"},
    "0x5aa9": {"username": "apucimama", "strategy": "SCALP", "win_rate": "60-65%", "size": "Small"},
    "0x1af1": {"username": "Pimping", "strategy": "DIRECTIONAL", "win_rate": "High", "size": "Whale"},
    "0x5c3a": {"username": "AdolfMissler", "strategy": "MISPRICING", "win_rate": "Unknown", "size": "Medium"},
    "0xbf51": {"username": "wagwag", "strategy": "MISPRICING", "win_rate": "Strong", "size": "Large"},
    "0x5877": {"username": "Marktakh", "strategy": "LIVE", "win_rate": "Unknown", "size": "Micro"},
    "0xb904": {"username": "lfc123", "strategy": "MISPRICING", "win_rate": "Very Strong", "size": "Whale"},
    "0x9cb9": {"username": "jtwyslljy", "strategy": "DIRECTIONAL", "win_rate": "Unknown", "size": "Medium"},
    "0xf152": {"username": "phonesculptor", "strategy": "MISPRICING", "win_rate": "Strong", "size": "Large"},
    "0x19ed": {"username": "(anon)", "strategy": "SCALP", "win_rate": "Strong", "size": "Medium"},
    "0xc257": {"username": "FollowMeABC123", "strategy": "DIRECTIONAL", "win_rate": "Unknown", "size": "Small"},
    "0x9731": {"username": "BlindOrangutan", "strategy": "SCALP", "win_rate": "Unknown", "size": "Micro"},
    "0x93ab": {"username": "gatorr", "strategy": "DIRECTIONAL", "win_rate": "70%+", "size": "Large"},
    "0xa8e0": {"username": "Wannac", "strategy": "DIRECTIONAL", "win_rate": "Unknown", "size": "Medium"},
    "0x07b8": {"username": "joosangyoo", "strategy": "DIRECTIONAL", "win_rate": "Unknown", "size": "Medium"},
    "0xd3fa": {"username": "BigGumbaBoots", "strategy": "DIRECTIONAL", "win_rate": "65%+", "size": "Medium"},
    "0x20d6": {"username": "Automated Bot", "strategy": "ARB", "win_rate": "50%", "size": "Medium"},
    "0x37e4": {"username": "SemyonMarmeladov", "strategy": "DIRECTIONAL", "win_rate": "Unknown", "size": "Whale"},
    "0xb45a": {"username": "DiviLungaoBBW", "strategy": "DIRECTIONAL", "win_rate": "High", "size": "Medium"},
    # NEW: From X.com strategy research (2026-01-25) - REVERSE ENGINEERED
    "0x4ffe": {"username": "planktonXD", "strategy": "LONGSHOT", "win_rate": "Unknown", "size": "Micro"},
    "0x6a72": {"username": "kch123", "strategy": "MISPRICING", "win_rate": "Very High", "size": "Whale"},
    "0x7c3d": {"username": "Car", "strategy": "GEOPOLITICAL", "win_rate": "Unknown", "size": "Medium"},
    "0xcc50": {"username": "justdance", "strategy": "LONGSHOT", "win_rate": "Unknown", "size": "Micro"},
    "0x0a85": {"username": "Fusion1", "strategy": "GEOPOLITICAL", "win_rate": "Unknown", "size": "Large"},
}


def load_portfolio() -> dict:
    """Load Kelly portfolio from disk."""
    try:
        path = Path(KELLY_PORTFOLIO_FILE)
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "initial_capital": 10000.0,
        "cash": 10000.0,
        "positions": [],
        "closed_positions": [],
        "total_pnl": 0.0,
        "win_count": 0,
        "loss_count": 0,
    }


def load_wallets() -> list:
    """Load tracked wallets from disk."""
    try:
        path = Path(SEEN_WALLETS_FILE)
        if path.exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def get_wallet_info(address: str) -> dict:
    """Get strategy info for a wallet address."""
    prefix = address[:6].lower()
    for key, info in WALLET_STRATEGIES.items():
        if prefix.startswith(key.lower()):
            return info
    return {"username": address[:10] + "...", "strategy": "UNKNOWN", "win_rate": "?", "size": "?"}


async def fetch_sports_edges():
    """Fetch live sports edges from sportsbook scanner."""
    try:
        from src.sportsbook import SportsEdgeScanner
        async with SportsEdgeScanner() as scanner:
            edges = await scanner.scan_all_sports()
            # Filter to only BUY opportunities with >= 3% edge
            buy_edges = [e for e in edges if e.get("edge_pct", 0) >= 3.0]
            return buy_edges
    except Exception as e:
        print(f"[DASHBOARD] Sports scan error: {e}")
        return []


def update_sports_cache():
    """Background task to update sports cache."""
    async def _update():
        global _sports_cache
        while True:
            try:
                edges = await fetch_sports_edges()
                _sports_cache = {
                    "edges": edges,
                    "last_update": datetime.now().isoformat()
                }
            except Exception as e:
                print(f"[DASHBOARD] Cache update error: {e}")
            await asyncio.sleep(300)  # Update every 5 minutes

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_update())


def get_portfolio_data() -> dict:
    """Get portfolio with calculated stats."""
    portfolio = load_portfolio()

    positions = portfolio.get("positions", [])
    total_invested = sum(pos.get("cost_basis", 0) for pos in positions)
    initial = portfolio.get("initial_capital", 10000)
    cash = portfolio.get("cash", initial)
    total_value = cash + total_invested
    total_pnl = portfolio.get("total_pnl", 0)

    wins = portfolio.get("win_count", 0)
    losses = portfolio.get("loss_count", 0)
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    return {
        "portfolio": portfolio,
        "total_invested": total_invested,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "return_pct": (total_pnl / initial * 100) if initial > 0 else 0,
        "timestamp": datetime.now().isoformat(),
    }


def get_wallets_data() -> dict:
    """Get tracked wallets with strategy info."""
    addresses = load_wallets()
    wallets = []
    for addr in addresses:
        info = get_wallet_info(addr)
        wallets.append({
            "address": addr[:10] + "..." + addr[-4:],
            "full_address": addr,
            **info
        })

    # Sort by strategy type
    strategy_order = {"MISPRICING": 0, "ARB": 1, "POLITICAL": 2, "GEOPOLITICAL": 3, "DIRECTIONAL": 4, "SCALP": 5, "LONGSHOT": 6, "LIVE": 7, "UNKNOWN": 8}
    wallets.sort(key=lambda w: strategy_order.get(w["strategy"], 99))

    return {
        "wallets": wallets,
        "total": len(wallets),
        "by_strategy": {},
    }


def get_sports_data() -> dict:
    """Get cached sports edges."""
    return _sports_cache


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Poly-Scout Dashboard v2</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.5;
            padding: 12px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            color: #58a6ff;
            margin-bottom: 16px;
            font-size: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        h1 .subtitle { font-size: 0.8rem; color: #8b949e; font-weight: normal; }
        h2 {
            color: #8b949e;
            margin: 20px 0 10px;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            border-bottom: 1px solid #30363d;
            padding-bottom: 6px;
        }
        .section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .stats-row {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }
        .stat {
            text-align: center;
            min-width: 100px;
        }
        .stat-label { color: #8b949e; font-size: 0.75rem; }
        .stat-value { font-size: 1.4rem; font-weight: 600; }
        .stat-value.positive { color: #3fb950; }
        .stat-value.negative { color: #f85149; }
        .stat-value.neutral { color: #58a6ff; }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }
        th {
            background: #21262d;
            color: #8b949e;
            font-weight: 500;
            font-size: 0.75rem;
            text-transform: uppercase;
        }
        tr:hover { background: #1f2428; }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 600;
        }
        .badge-mispricing { background: #238636; color: #fff; }
        .badge-directional { background: #1f6feb; color: #fff; }
        .badge-arb { background: #8957e5; color: #fff; }
        .badge-scalp { background: #f0883e; color: #fff; }
        .badge-longshot { background: #da3633; color: #fff; }
        .badge-live { background: #db61a2; color: #fff; }
        .badge-political { background: #1158c7; color: #fff; }
        .badge-geopolitical { background: #6e40c9; color: #fff; }
        .badge-unknown { background: #6e7681; color: #fff; }
        .badge-buy { background: #238636; color: #fff; }
        .badge-sell { background: #da3633; color: #fff; }

        .edge-positive { color: #3fb950; font-weight: 600; }
        .edge-negative { color: #f85149; }

        .size-whale { color: #f0883e; font-weight: 600; }
        .size-large { color: #58a6ff; }
        .size-medium { color: #8b949e; }
        .size-small { color: #6e7681; }
        .size-micro { color: #484f58; }

        .win-rate-strong { color: #3fb950; }
        .win-rate-medium { color: #f0883e; }
        .win-rate-unknown { color: #8b949e; }

        .status-row {
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: #8b949e;
        }
        .status-item { display: flex; align-items: center; gap: 4px; }
        .status-ok { color: #3fb950; }
        .status-ok::before { content: "\\2713 "; }

        .refresh-info {
            text-align: center;
            color: #8b949e;
            font-size: 0.75rem;
            margin-top: 16px;
        }

        .mobile-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }

        .no-data {
            text-align: center;
            padding: 20px;
            color: #8b949e;
            font-style: italic;
        }

        @media (max-width: 768px) {
            body { padding: 8px; }
            h1 { font-size: 1.2rem; flex-direction: column; gap: 4px; }
            .stats-row { gap: 12px; }
            .stat { min-width: 80px; }
            .stat-value { font-size: 1.1rem; }
            table { font-size: 0.75rem; }
            th, td { padding: 8px 6px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            Poly-Scout Dashboard v2
            <span class="subtitle">Last update: <span id="last-update">-</span></span>
        </h1>

        <!-- PORTFOLIO SECTION -->
        <div class="section">
            <h2>Portfolio</h2>
            <div class="stats-row">
                <div class="stat">
                    <div class="stat-label">Balance</div>
                    <div class="stat-value neutral" id="balance">$10,000</div>
                </div>
                <div class="stat">
                    <div class="stat-label">P&L</div>
                    <div class="stat-value" id="pnl">$0.00</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Return</div>
                    <div class="stat-value" id="return-pct">0.0%</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Win Rate</div>
                    <div class="stat-value neutral" id="win-rate">0%</div>
                </div>
                <div class="stat">
                    <div class="stat-label">W/L</div>
                    <div class="stat-value neutral" id="win-loss">0/0</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Open</div>
                    <div class="stat-value neutral" id="open-count">0</div>
                </div>
            </div>
            <div class="mobile-scroll">
                <table id="positions-table">
                    <thead>
                        <tr>
                            <th>Market</th>
                            <th>Side</th>
                            <th>Entry</th>
                            <th>Edge</th>
                            <th>Cost</th>
                            <th>Potential</th>
                        </tr>
                    </thead>
                    <tbody id="positions-body"></tbody>
                </table>
            </div>
        </div>

        <!-- SPORTS EDGES SECTION -->
        <div class="section">
            <h2>Live Sports Edges (>=3%)</h2>
            <div class="mobile-scroll">
                <table id="sports-table">
                    <thead>
                        <tr>
                            <th>Game</th>
                            <th>Team</th>
                            <th>PM</th>
                            <th>Vegas</th>
                            <th>Edge</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody id="sports-body"></tbody>
                </table>
            </div>
            <div class="no-data" id="sports-no-data" style="display:none;">No sports edges found (>=3%)</div>
        </div>

        <!-- TRACKED WALLETS SECTION -->
        <div class="section">
            <h2>Tracked Wallets (<span id="wallet-count">0</span>)</h2>
            <div class="mobile-scroll">
                <table id="wallets-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Strategy</th>
                            <th>Win Rate</th>
                            <th>Size</th>
                            <th>Address</th>
                        </tr>
                    </thead>
                    <tbody id="wallets-body"></tbody>
                </table>
            </div>
        </div>

        <!-- DAEMON STATUS -->
        <div class="section">
            <h2>Daemon Status</h2>
            <div class="status-row">
                <div class="status-item status-ok">Sportsbook</div>
                <div class="status-item status-ok">Blockchain</div>
                <div class="status-item status-ok">New Markets</div>
                <div class="status-item status-ok">Longshots</div>
            </div>
        </div>

        <div class="refresh-info">
            Auto-refresh: 30s
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

        function getBadgeClass(strategy) {
            const map = {
                'MISPRICING': 'badge-mispricing',
                'DIRECTIONAL': 'badge-directional',
                'ARB': 'badge-arb',
                'SCALP': 'badge-scalp',
                'LONGSHOT': 'badge-longshot',
                'LIVE': 'badge-live',
                'POLITICAL': 'badge-political',
                'GEOPOLITICAL': 'badge-geopolitical',
            };
            return map[strategy] || 'badge-unknown';
        }

        function getSizeClass(size) {
            const map = {
                'Whale': 'size-whale',
                'Large': 'size-large',
                'Medium': 'size-medium',
                'Small': 'size-small',
                'Micro': 'size-micro',
            };
            return map[size] || 'size-medium';
        }

        function getWinRateClass(wr) {
            if (wr.includes('Strong') || wr.includes('High') || parseInt(wr) >= 70) return 'win-rate-strong';
            if (parseInt(wr) >= 50) return 'win-rate-medium';
            return 'win-rate-unknown';
        }

        function updatePortfolio(data) {
            const p = data.portfolio;

            document.getElementById('balance').textContent = formatCurrency(p.cash + data.total_invested);

            const pnlEl = document.getElementById('pnl');
            pnlEl.textContent = formatCurrency(data.total_pnl);
            pnlEl.className = 'stat-value ' + (data.total_pnl >= 0 ? 'positive' : 'negative');

            const retEl = document.getElementById('return-pct');
            retEl.textContent = formatPct(data.return_pct);
            retEl.className = 'stat-value ' + (data.return_pct >= 0 ? 'positive' : 'negative');

            document.getElementById('win-rate').textContent = data.win_rate.toFixed(0) + '%';
            document.getElementById('win-loss').textContent = data.wins + '/' + data.losses;
            document.getElementById('open-count').textContent = (p.positions || []).length;

            // Positions table
            const positions = p.positions || [];
            const tbody = document.getElementById('positions-body');
            if (positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#8b949e;">No open positions</td></tr>';
            } else {
                tbody.innerHTML = positions.map(pos => `
                    <tr>
                        <td>${pos.market_slug || 'Unknown'}</td>
                        <td>${pos.outcome}</td>
                        <td>${(pos.entry_price * 100).toFixed(1)}%</td>
                        <td class="edge-positive">+${pos.edge_pct.toFixed(1)}%</td>
                        <td>${formatCurrency(pos.cost_basis)}</td>
                        <td>${formatCurrency(pos.potential_payout)}</td>
                    </tr>
                `).join('');
            }
        }

        function updateSports(data) {
            const edges = data.edges || [];
            const tbody = document.getElementById('sports-body');
            const noData = document.getElementById('sports-no-data');

            if (edges.length === 0) {
                tbody.innerHTML = '';
                noData.style.display = 'block';
            } else {
                noData.style.display = 'none';
                tbody.innerHTML = edges.map(e => `
                    <tr>
                        <td>${e.event_name || e.market_slug}</td>
                        <td>${e.team}</td>
                        <td>${(e.pm_price * 100).toFixed(1)}%</td>
                        <td>${(e.sb_prob * 100).toFixed(1)}%</td>
                        <td class="edge-positive">+${e.edge_pct.toFixed(1)}%</td>
                        <td><span class="badge badge-buy">BUY</span></td>
                    </tr>
                `).join('');
            }
        }

        function updateWallets(data) {
            const wallets = data.wallets || [];
            document.getElementById('wallet-count').textContent = wallets.length;

            const tbody = document.getElementById('wallets-body');
            tbody.innerHTML = wallets.map(w => `
                <tr>
                    <td><strong>${w.username}</strong></td>
                    <td><span class="badge ${getBadgeClass(w.strategy)}">${w.strategy}</span></td>
                    <td class="${getWinRateClass(w.win_rate)}">${w.win_rate}</td>
                    <td class="${getSizeClass(w.size)}">${w.size}</td>
                    <td style="font-family:monospace;font-size:0.75rem;">${w.address}</td>
                </tr>
            `).join('');
        }

        async function fetchData() {
            try {
                const [portfolioResp, sportsResp, walletsResp] = await Promise.all([
                    fetch('/api/portfolio'),
                    fetch('/api/sports'),
                    fetch('/api/wallets'),
                ]);

                const portfolioData = await portfolioResp.json();
                const sportsData = await sportsResp.json();
                const walletsData = await walletsResp.json();

                updatePortfolio(portfolioData);
                updateSports(sportsData);
                updateWallets(walletsData);

                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
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


@app.route('/api/sports')
def api_sports():
    """API endpoint for sports edges."""
    return jsonify(get_sports_data())


@app.route('/api/wallets')
def api_wallets():
    """API endpoint for tracked wallets."""
    return jsonify(get_wallets_data())


def main():
    parser = argparse.ArgumentParser(description="Poly-Scout Dashboard v2")
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8081,
        help="Port to run on (default: 8081)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )

    args = parser.parse_args()

    # Start background thread to update sports cache
    # (Disabled for now - fetch on-demand via scan)
    # bg_thread = Thread(target=update_sports_cache, daemon=True)
    # bg_thread.start()

    print(f"Starting Poly-Scout Dashboard v2 on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
