"""
Configuration management for poly-scout.

Loads settings from environment variables and config.yaml file.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# API Keys and Credentials
# =============================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "4f966793260d394e5fe551bd517d4957")

# =============================================================================
# API Endpoints
# =============================================================================

GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

# =============================================================================
# Edge Validation Thresholds
# =============================================================================

MIN_EDGE_PCT = 3.0          # Minimum edge % to consider (after comparing to external source)
MIN_LIQUIDITY_USD = 1000    # Minimum order book liquidity
MAX_SLIPPAGE_PCT = 1.0      # Maximum acceptable slippage
MIN_EXPECTED_PROFIT = 10    # Minimum expected profit in USD
MAX_RESOLUTION_DAYS = 7     # Maximum days until resolution

# =============================================================================
# Scan Intervals (seconds)
# =============================================================================

SCAN_INTERVAL_LEADERBOARD = 300   # 5 minutes
SCAN_INTERVAL_SPORTSBOOK = 300    # 5 minutes
SCAN_INTERVAL_TWITTER = 900       # 15 minutes
SCAN_INTERVAL_NEW_MARKETS = 60    # 1 minute (aggressive for sniping)

# =============================================================================
# Monitored Sports (sport_key, pm_prefix, display_name)
# =============================================================================

MONITORED_SPORTS = [
    ("basketball_nba", "nba", "NBA"),
    ("soccer_spain_la_liga", "lal", "La Liga"),
    ("soccer_epl", "epl", "EPL"),
    ("soccer_germany_bundesliga", "bun", "Bundesliga"),
    ("soccer_italy_serie_a", "ser", "Serie A"),
    ("soccer_france_ligue_one", "fl1", "Ligue 1"),
    ("icehockey_nhl", "nhl", "NHL"),
]

# =============================================================================
# NBA Team Codes (for building PM slugs)
# =============================================================================

NBA_TEAM_CODES = {
    "Atlanta Hawks": "atl",
    "Boston Celtics": "bos",
    "Brooklyn Nets": "bkn",
    "Charlotte Hornets": "cha",
    "Chicago Bulls": "chi",
    "Cleveland Cavaliers": "cle",
    "Dallas Mavericks": "dal",
    "Denver Nuggets": "den",
    "Detroit Pistons": "det",
    "Golden State Warriors": "gsw",
    "Houston Rockets": "hou",
    "Indiana Pacers": "ind",
    "Los Angeles Clippers": "lac",
    "Los Angeles Lakers": "lal",
    "Memphis Grizzlies": "mem",
    "Miami Heat": "mia",
    "Milwaukee Bucks": "mil",
    "Minnesota Timberwolves": "min",
    "New Orleans Pelicans": "nop",
    "New York Knicks": "nyk",
    "Oklahoma City Thunder": "okc",
    "Orlando Magic": "orl",
    "Philadelphia 76ers": "phi",
    "Phoenix Suns": "phx",
    "Portland Trail Blazers": "por",
    "Sacramento Kings": "sac",
    "San Antonio Spurs": "sas",
    "Toronto Raptors": "tor",
    "Utah Jazz": "uta",
    "Washington Wizards": "wsh",
}

# =============================================================================
# Nitter Instances (for X.com scraping)
# =============================================================================

NITTER_INSTANCES = [
    "nitter.poast.org",
    "nitter.privacydev.net",
    "nitter.woodland.cafe",
    "nitter.esmailelbob.xyz",
]

# =============================================================================
# Data Files
# =============================================================================

SEEN_TWEETS_FILE = "./data/seen_tweets.json"
SEEN_OPPORTUNITIES_FILE = "./data/seen_opportunities.json"

# =============================================================================
# Helper Functions
# =============================================================================

def american_to_prob(price: float) -> float:
    """Convert American odds to implied probability."""
    if price > 0:
        return 100 / (price + 100)
    else:
        return abs(price) / (abs(price) + 100)


# =============================================================================
# Config Dataclass (legacy support)
# =============================================================================

@dataclass
class Config:
    """Configuration settings for poly-scout."""

    # API Endpoints
    polymarket_data_api: str = "https://data-api.polymarket.com"
    polymarket_gamma_api: str = "https://gamma-api.polymarket.com"

    # Scanning thresholds
    scan_min_profit: float = 5000.0
    scan_min_win_rate: float = 0.85
    scan_max_age_days: int = 60

    # Rate limiting
    rate_limit_rps: int = 5
    rate_limit_burst: int = 10

    # Output settings
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    data_dir: Path = field(default_factory=lambda: Path("./data"))

    # Analysis settings
    min_trades_for_analysis: int = 10
    lookback_days: int = 90

    # Watchlist settings
    watchlist_path: Path = field(default_factory=lambda: Path("./data/watchlist.json"))

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    def __post_init__(self):
        """Convert string paths to Path objects and create directories."""
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.watchlist_path, str):
            self.watchlist_path = Path(self.watchlist_path)
        if self.log_file and isinstance(self.log_file, str):
            self.log_file = Path(self.log_file)

        # Create directories if they don't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Returns:
            Config: Configuration instance with values from environment
        """
        load_dotenv()

        return cls(
            polymarket_data_api=os.getenv(
                "POLYMARKET_DATA_API",
                "https://data-api.polymarket.com"
            ),
            polymarket_gamma_api=os.getenv(
                "POLYMARKET_GAMMA_API",
                "https://gamma-api.polymarket.com"
            ),
            scan_min_profit=float(os.getenv("SCAN_MIN_PROFIT", "5000")),
            scan_min_win_rate=float(os.getenv("SCAN_MIN_WIN_RATE", "0.85")),
            scan_max_age_days=int(os.getenv("SCAN_MAX_AGE_DAYS", "60")),
            rate_limit_rps=int(os.getenv("RATE_LIMIT_RPS", "5")),
            rate_limit_burst=int(os.getenv("RATE_LIMIT_BURST", "10")),
            output_dir=Path(os.getenv("OUTPUT_DIR", "./output")),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            min_trades_for_analysis=int(os.getenv("MIN_TRADES_FOR_ANALYSIS", "10")),
            lookback_days=int(os.getenv("LOOKBACK_DAYS", "90")),
            watchlist_path=Path(os.getenv("WATCHLIST_PATH", "./data/watchlist.json")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=Path(os.getenv("LOG_FILE")) if os.getenv("LOG_FILE") else None,
        )

    @classmethod
    def from_yaml(cls, config_path: Path) -> "Config":
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Config: Configuration instance with values from YAML
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        return cls(**data)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration with precedence: CLI args > env vars > config file > defaults.

        Args:
            config_path: Optional path to YAML config file

        Returns:
            Config: Merged configuration instance
        """
        # Start with defaults
        config = cls()

        # Load from YAML if provided
        if config_path and config_path.exists():
            yaml_config = cls.from_yaml(config_path)
            # Merge YAML config into defaults
            for key, value in vars(yaml_config).items():
                setattr(config, key, value)

        # Load from environment (highest precedence)
        env_config = cls.from_env()
        # Only override with env vars that are explicitly set
        for key, value in vars(env_config).items():
            env_key = key.upper()
            if os.getenv(env_key) is not None:
                setattr(config, key, value)

        return config

    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary.

        Returns:
            dict: Configuration as dictionary
        """
        result = {}
        for key, value in vars(self).items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result
