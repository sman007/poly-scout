"""
CLI interface for poly-scout using Click.

Provides commands for scanning, analyzing, and monitoring Polymarket traders.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TextColumn
from rich.panel import Panel
from rich import print as rprint

from src.config import Config
from src.scanner import WalletScanner
from src.analyzer import TradeAnalyzer
from src.signals import SignalDetector

# Create console with safe encoding for Windows
console = Console(legacy_windows=False, force_terminal=True)


def load_config(config_file: Optional[Path]) -> Config:
    """
    Load configuration from file or defaults.

    Args:
        config_file: Optional path to config file

    Returns:
        Config: Loaded configuration
    """
    try:
        return Config.load(config_file)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        sys.exit(1)


@click.group()
@click.version_option(version="0.1.0", prog_name="poly-scout")
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file (YAML)",
)
@click.pass_context
def cli(ctx, config):
    """
    Polymarket wallet scanner - detect emerging alpha traders.

    Scan the Polymarket platform for high-performing traders,
    analyze their strategies, and monitor their activity.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.option(
    "--min-profit",
    type=float,
    help="Minimum profit threshold (USD)",
)
@click.option(
    "--min-win-rate",
    type=float,
    help="Minimum win rate (0.0-1.0)",
)
@click.option(
    "--max-age-days",
    type=int,
    help="Maximum account age in days",
)
@click.option(
    "--output-format",
    type=click.Choice(["json", "table", "html"], case_sensitive=False),
    default="table",
    help="Output format for results",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path (optional)",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of traders to return",
)
@click.pass_context
def scan(ctx, min_profit, min_win_rate, max_age_days, output_format, output, limit):
    """
    Run full scan for emerging traders.

    Scans the Polymarket platform for traders matching specified criteria.
    Results are displayed in the chosen format and optionally saved to a file.

    Example:
        poly-scout scan --min-profit 10000 --min-win-rate 0.90 --output-format table
    """
    config = ctx.obj["config"]

    # Override config with CLI options if provided
    if min_profit is not None:
        config.scan_min_profit = min_profit
    if min_win_rate is not None:
        config.scan_min_win_rate = min_win_rate
    if max_age_days is not None:
        config.scan_max_age_days = max_age_days

    console.print(Panel.fit(
        f"[bold cyan]Scanning for emerging traders[/bold cyan]\n\n"
        f"Min Profit: [green]${config.scan_min_profit:,.0f}[/green]\n"
        f"Min Win Rate: [green]{config.scan_min_win_rate:.1%}[/green]\n"
        f"Max Age: [green]{config.scan_max_age_days} days[/green]\n"
        f"Limit: [green]{limit}[/green]",
        title="Scan Parameters"
    ))

    console.print("\n[cyan]Scanning platform...[/cyan]")

    # Use actual scanner
    async def do_scan():
        async with WalletScanner() as scanner:
            profiles = await scanner.scan_for_emerging_traders(
                min_profit=config.scan_min_profit,
                min_win_rate=config.scan_min_win_rate,
                max_age_days=config.scan_max_age_days,
                leaderboard_limit=min(limit * 10, 500),  # Scan more to find matches
            )
            return profiles[:limit]

    try:
        profiles = asyncio.run(do_scan())
        results = [
            {
                "address": p.address,
                "username": p.username or p.address[:12] + "...",
                "profit": p.profit,
                "win_rate": p.win_rate,
                "trades": p.trade_count,
                "age_days": p.age_days or 0,
            }
            for p in profiles
        ]
    except Exception as e:
        console.print(f"[red]Scan failed: {e}[/red]")
        results = []

    console.print("[green]Scan complete![/green]")

    # Output results
    if output_format == "table":
        _display_results_table(results)
    elif output_format == "json":
        _display_results_json(results)
    elif output_format == "html":
        _display_results_html(results)

    # Save to file if specified
    if output:
        _save_results(results, output, output_format)
        console.print(f"\n[green]Results saved to:[/green] {output}")

    console.print(f"\n[bold green]Found {len(results)} traders matching criteria[/bold green]")


@cli.command()
@click.argument("address")
@click.option(
    "--output-format",
    type=click.Choice(["json", "table", "html"], case_sensitive=False),
    default="table",
    help="Output format for analysis",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path (optional)",
)
@click.option(
    "--add-to-watchlist",
    is_flag=True,
    help="Add trader to watchlist after analysis",
)
@click.pass_context
def analyze(ctx, address, output_format, output, add_to_watchlist):
    """
    Deep dive analysis on a specific wallet.

    Provides detailed statistics, trading patterns, and performance metrics
    for the specified wallet address.

    Example:
        poly-scout analyze 0x1234... --output-format table --add-to-watchlist
    """
    config = ctx.obj["config"]

    console.print(Panel.fit(
        f"[bold cyan]Analyzing wallet[/bold cyan]\n\n"
        f"Address: [yellow]{address}[/yellow]",
        title="Wallet Analysis"
    ))

    console.print("\n[cyan]Fetching wallet data...[/cyan]")

    # Use actual scanner and analyzer
    async def do_analyze():
        async with WalletScanner() as scanner:
            profile = await scanner.fetch_wallet_stats(address)
            if not profile:
                return None

            trades = await scanner.fetch_wallet_activity(address, limit=500)
            profile.trades = trades

            # Run signal detection
            detector = SignalDetector()
            signals = detector.detect_all_signals(profile, trades)
            alpha_score = detector.calculate_alpha_score(signals)

            return profile, signals, alpha_score

    try:
        result = asyncio.run(do_analyze())
        if result is None:
            console.print(f"[red]Could not fetch data for {address}[/red]")
            return

        profile, signals, alpha_score = result

        analysis = {
            "address": profile.address,
            "username": profile.username or "Unknown",
            "total_profit": profile.profit,
            "win_rate": profile.win_rate,
            "total_trades": profile.trade_count,
            "active_positions": len([t for t in profile.trades if t.profit == 0]) if profile.trades else 0,
            "avg_position_size": profile.avg_position_size,
            "best_market": "Crypto" if profile.markets_traded else "Unknown",
            "roi": (profile.profit / max(profile.volume, 1)) if profile.volume else 0,
            "alpha_score": alpha_score,
            "signals": [{"type": s.signal_type, "strength": s.strength} for s in signals],
        }
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        analysis = {"address": address, "error": str(e)}

    console.print("[green]Analysis complete![/green]")

    # Display results
    if output_format == "table":
        _display_analysis_table(analysis)
    elif output_format == "json":
        _display_analysis_json(analysis)
    elif output_format == "html":
        _display_analysis_html(analysis)

    # Save to file if specified
    if output:
        _save_results(analysis, output, output_format)
        console.print(f"\n[green]Analysis saved to:[/green] {output}")

    # Add to watchlist if requested
    if add_to_watchlist:
        _add_to_watchlist(address, config.watchlist_path)
        console.print(f"\n[green]Added to watchlist:[/green] {address}")


@cli.command()
@click.option(
    "--interval",
    type=int,
    default=300,
    help="Monitoring interval in seconds",
)
@click.option(
    "--min-profit",
    type=float,
    help="Minimum profit threshold for alerts",
)
@click.option(
    "--watchlist-only",
    is_flag=True,
    help="Monitor only wallets in watchlist",
)
@click.pass_context
def watch(ctx, interval, min_profit, watchlist_only):
    """
    Continuous monitoring mode.

    Continuously monitors the platform for new opportunities and alerts
    on significant trader activity. Press Ctrl+C to stop.

    Example:
        poly-scout watch --interval 60 --watchlist-only
    """
    config = ctx.obj["config"]

    if min_profit is not None:
        config.scan_min_profit = min_profit

    console.print(Panel.fit(
        f"[bold cyan]Continuous Monitoring Mode[/bold cyan]\n\n"
        f"Interval: [green]{interval}s[/green]\n"
        f"Min Profit Alert: [green]${config.scan_min_profit:,.0f}[/green]\n"
        f"Watchlist Only: [green]{watchlist_only}[/green]\n\n"
        f"[yellow]Press Ctrl+C to stop[/yellow]",
        title="Watch Mode"
    ))

    try:
        # TODO: Implement actual monitoring logic here
        console.print("\n[yellow]Monitoring not yet implemented. This is a placeholder.[/yellow]")
        console.print("[dim]Future: Will continuously scan for new opportunities[/dim]")
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Monitoring stopped by user[/yellow]")
        sys.exit(0)


@cli.command()
@click.option(
    "--output-format",
    type=click.Choice(["json", "table", "html"], case_sensitive=False),
    default="table",
    help="Output format for report",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    help="Output file path (optional)",
)
@click.option(
    "--detailed",
    is_flag=True,
    help="Include detailed statistics for each trader",
)
@click.pass_context
def report(ctx, output_format, output, detailed):
    """
    Generate report on watchlist.

    Creates a comprehensive report of all traders in the watchlist,
    including their current performance and recent activity.

    Example:
        poly-scout report --detailed --output watchlist_report.html
    """
    config = ctx.obj["config"]

    console.print(Panel.fit(
        f"[bold cyan]Generating Watchlist Report[/bold cyan]\n\n"
        f"Watchlist: [yellow]{config.watchlist_path}[/yellow]\n"
        f"Detailed: [green]{detailed}[/green]",
        title="Report Generation"
    ))

    # Load watchlist
    if not config.watchlist_path.exists():
        console.print("[yellow]Watchlist is empty or doesn't exist yet[/yellow]")
        return

    console.print("\n[cyan]Generating report...[/cyan]")

    # TODO: Implement actual report generation logic here
    # For now, mock data
    watchlist_data = [
        {
            "address": "0x" + "a" * 40,
            "profit": 12500.0,
            "win_rate": 0.92,
            "trades": 45,
            "last_active": "2 hours ago",
        },
    ]

    console.print("[green]Report generated![/green]")

    # Display results
    if output_format == "table":
        _display_watchlist_table(watchlist_data, detailed)
    elif output_format == "json":
        _display_watchlist_json(watchlist_data)
    elif output_format == "html":
        _display_watchlist_html(watchlist_data, detailed)

    # Save to file if specified
    if output:
        _save_results(watchlist_data, output, output_format)
        console.print(f"\n[green]Report saved to:[/green] {output}")


# Helper functions for displaying results

def _display_results_table(results: list):
    """Display scan results as a rich table."""
    table = Table(title="Emerging Traders", show_header=True, header_style="bold cyan")

    table.add_column("Address", style="yellow", no_wrap=True)
    table.add_column("Profit", justify="right", style="green")
    table.add_column("Win Rate", justify="right", style="green")
    table.add_column("Trades", justify="right")
    table.add_column("Age (days)", justify="right")

    for trader in results:
        table.add_row(
            trader["address"][:10] + "...",
            f"${trader['profit']:,.0f}",
            f"{trader['win_rate']:.1%}",
            str(trader["trades"]),
            str(trader["age_days"]),
        )

    console.print(table)


def _display_results_json(results: list):
    """Display scan results as JSON."""
    rprint(json.dumps(results, indent=2))


def _display_results_html(results: list):
    """Display scan results as HTML (placeholder)."""
    console.print("[yellow]HTML output format not yet implemented[/yellow]")


def _display_analysis_table(analysis: dict):
    """Display wallet analysis as a rich table."""
    table = Table(title="Wallet Analysis", show_header=True, header_style="bold cyan")

    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Address", analysis["address"][:20] + "...")
    table.add_row("Total Profit", f"${analysis['total_profit']:,.0f}")
    table.add_row("Win Rate", f"{analysis['win_rate']:.1%}")
    table.add_row("Total Trades", str(analysis["total_trades"]))
    table.add_row("Active Positions", str(analysis["active_positions"]))
    table.add_row("Avg Position Size", f"${analysis['avg_position_size']:,.0f}")
    table.add_row("Best Market", analysis["best_market"])
    table.add_row("ROI", f"{analysis['roi']:.1%}")
    table.add_row("Sharpe Ratio", f"{analysis['sharpe_ratio']:.2f}")

    console.print(table)


def _display_analysis_json(analysis: dict):
    """Display wallet analysis as JSON."""
    rprint(json.dumps(analysis, indent=2))


def _display_analysis_html(analysis: dict):
    """Display wallet analysis as HTML (placeholder)."""
    console.print("[yellow]HTML output format not yet implemented[/yellow]")


def _display_watchlist_table(watchlist: list, detailed: bool):
    """Display watchlist report as a rich table."""
    table = Table(title="Watchlist Report", show_header=True, header_style="bold cyan")

    table.add_column("Address", style="yellow", no_wrap=True)
    table.add_column("Profit", justify="right", style="green")
    table.add_column("Win Rate", justify="right", style="green")
    table.add_column("Trades", justify="right")
    table.add_column("Last Active", style="dim")

    for trader in watchlist:
        table.add_row(
            trader["address"][:10] + "...",
            f"${trader['profit']:,.0f}",
            f"{trader['win_rate']:.1%}",
            str(trader["trades"]),
            trader["last_active"],
        )

    console.print(table)


def _display_watchlist_json(watchlist: list):
    """Display watchlist report as JSON."""
    rprint(json.dumps(watchlist, indent=2))


def _display_watchlist_html(watchlist: list, detailed: bool):
    """Display watchlist report as HTML (placeholder)."""
    console.print("[yellow]HTML output format not yet implemented[/yellow]")


def _save_results(data, output_path: Path, format_type: str):
    """Save results to file in specified format."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format_type == "json":
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
    elif format_type == "html":
        # Placeholder for HTML export
        with open(output_path, "w") as f:
            f.write(f"<html><body><pre>{json.dumps(data, indent=2)}</pre></body></html>")
    else:
        # Save as JSON by default
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)


def _add_to_watchlist(address: str, watchlist_path: Path):
    """Add a wallet address to the watchlist."""
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing watchlist
    if watchlist_path.exists():
        with open(watchlist_path, "r") as f:
            watchlist = json.load(f)
    else:
        watchlist = []

    # Add address if not already present
    if address not in [w.get("address") for w in watchlist]:
        watchlist.append({
            "address": address,
            "added_at": "now",  # TODO: Use actual timestamp
        })

        # Save updated watchlist
        with open(watchlist_path, "w") as f:
            json.dump(watchlist, f, indent=2)


def main():
    """Main entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
