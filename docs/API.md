# API Reference

Complete API documentation for poly-scout modules.

## Module Overview

- **scanner.py** - Wallet scanning and data fetching
- **analyzer.py** - Trade pattern analysis
- **signals.py** - Anomaly detection
- **reverse.py** - Strategy reverse-engineering
- **config.py** - Configuration management
- **cli.py** - Command-line interface

## scanner.py

### WalletScanner

Main class for scanning Polymarket and fetching wallet data.

#### Constructor

```python
WalletScanner(
    rate_limit: float = 5.0,
    cache_ttl: int = 300,
    timeout: int = 30,
    max_retries: int = 3,
)
```

**Parameters:**
- `rate_limit` (float): Maximum requests per second (default: 5.0)
- `cache_ttl` (int): Cache time-to-live in seconds (default: 300)
- `timeout` (int): HTTP request timeout in seconds (default: 30)
- `max_retries` (int): Maximum retry attempts on failure (default: 3)

**Example:**
```python
scanner = WalletScanner(rate_limit=3.0, cache_ttl=600)
```

#### Methods

##### fetch_leaderboard()

```python
async def fetch_leaderboard(
    limit: int = 500,
    period: str = "all",
) -> List[WalletProfile]
```

Fetch the Polymarket leaderboard of top performers.

**Parameters:**
- `limit` (int): Maximum number of traders to fetch (default: 500)
- `period` (str): Time period - "all", "month", "week", "day" (default: "all")

**Returns:** `List[WalletProfile]`

**Example:**
```python
async with WalletScanner() as scanner:
    leaderboard = await scanner.fetch_leaderboard(limit=100, period="month")
```

##### fetch_wallet_activity()

```python
async def fetch_wallet_activity(
    address: str,
    limit: int = 1000,
) -> List[Trade]
```

Fetch trade history for a specific wallet.

**Parameters:**
- `address` (str): Wallet address
- `limit` (int): Maximum trades to fetch (default: 1000)

**Returns:** `List[Trade]`

**Example:**
```python
trades = await scanner.fetch_wallet_activity("0x1234...", limit=500)
```

##### fetch_wallet_stats()

```python
async def fetch_wallet_stats(
    address: str
) -> Optional[WalletProfile]
```

Fetch comprehensive statistics for a specific wallet.

**Parameters:**
- `address` (str): Wallet address

**Returns:** `Optional[WalletProfile]` - Profile or None if not found

**Example:**
```python
profile = await scanner.fetch_wallet_stats("0x1234...")
if profile:
    print(f"Profit: ${profile.profit}")
```

##### scan_for_emerging_traders()

```python
async def scan_for_emerging_traders(
    min_profit: float = 5000.0,
    min_win_rate: float = 0.85,
    max_age_days: int = 60,
    leaderboard_limit: int = 500,
) -> List[WalletProfile]
```

Scan for emerging traders with sudden profit growth.

**Parameters:**
- `min_profit` (float): Minimum profit in USD (default: 5000.0)
- `min_win_rate` (float): Minimum win rate 0-1 (default: 0.85)
- `max_age_days` (int): Maximum account age in days (default: 60)
- `leaderboard_limit` (int): Leaderboard entries to scan (default: 500)

**Returns:** `List[WalletProfile]` - Sorted by profit descending

**Example:**
```python
emerging = await scanner.scan_for_emerging_traders(
    min_profit=10000,
    min_win_rate=0.90,
    max_age_days=45,
)
```

##### batch_fetch_wallet_stats()

```python
async def batch_fetch_wallet_stats(
    addresses: List[str],
    max_concurrent: int = 5,
) -> List[WalletProfile]
```

Fetch stats for multiple wallets concurrently.

**Parameters:**
- `addresses` (List[str]): List of wallet addresses
- `max_concurrent` (int): Maximum concurrent requests (default: 5)

**Returns:** `List[WalletProfile]`

**Example:**
```python
addresses = ["0x1234...", "0x5678...", "0x9abc..."]
profiles = await scanner.batch_fetch_wallet_stats(addresses)
```

##### fetch_market_data()

```python
async def fetch_market_data(
    market_id: str
) -> Optional[Dict[str, Any]]
```

Fetch market data from Gamma API.

**Parameters:**
- `market_id` (str): Market identifier

**Returns:** `Optional[Dict[str, Any]]` - Market data or None if not found

##### clear_cache()

```python
def clear_cache() -> None
```

Clear all cached responses.

**Example:**
```python
scanner.clear_cache()
```

#### Convenience Functions

##### quick_scan()

```python
async def quick_scan(
    min_profit: float = 5000.0,
    min_win_rate: float = 0.85,
    max_age_days: int = 60,
) -> List[WalletProfile]
```

Quick function to scan without creating scanner instance.

**Example:**
```python
emerging = await quick_scan(min_profit=8000, min_win_rate=0.88)
```

##### get_wallet_info()

```python
async def get_wallet_info(
    address: str
) -> Optional[WalletProfile]
```

Quick function to get info for a single wallet.

**Example:**
```python
profile = await get_wallet_info("0x1234...")
```

### Data Classes

#### WalletProfile

```python
@dataclass
class WalletProfile:
    address: str
    username: Optional[str] = None
    profit: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0
    first_seen: Optional[datetime] = None
    markets_traded: int = 0
    volume: float = 0.0
    rank: Optional[int] = None
    avg_position_size: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    trades: List[Trade] = field(default_factory=list)
```

**Computed Properties:**
- `age_days` (Optional[float]): Account age in days
- `avg_profit_per_trade` (float): Average profit per trade

**Methods:**
- `to_dict()` -> Dict[str, Any]: Convert to dictionary

#### Trade

```python
@dataclass
class Trade:
    timestamp: datetime
    market_id: str
    side: str  # "buy" or "sell"
    size: float
    price: float
    outcome: str
    profit: float
    market_title: Optional[str] = None
```

### Utility Classes

#### SimpleCache

```python
class SimpleCache:
    def __init__(self, ttl_seconds: int = 300)
    def get(self, key: str) -> Optional[Any]
    def set(self, key: str, value: Any) -> None
    def clear(self) -> None
    @staticmethod
    def make_key(*args, **kwargs) -> str
```

#### RateLimiter

```python
class RateLimiter:
    def __init__(self, requests_per_second: float = 5.0)
    async def acquire(self) -> None
```

## analyzer.py

### TradeAnalyzer

Main class for analyzing trade patterns and classifying strategies.

#### Constructor

```python
TradeAnalyzer(min_trades: int = 10)
```

**Parameters:**
- `min_trades` (int): Minimum trades required for analysis (default: 10)

#### Methods

##### analyze_wallet()

```python
def analyze_wallet(
    trades: List[Trade]
) -> Optional[WalletAnalysis]
```

Perform complete wallet analysis.

**Parameters:**
- `trades` (List[Trade]): List of trades to analyze

**Returns:** `Optional[WalletAnalysis]` - Analysis or None if insufficient data

**Example:**
```python
analyzer = TradeAnalyzer(min_trades=20)
analysis = analyzer.analyze_wallet(trades)
print(f"Strategy: {analysis.strategy_type.value}")
print(f"Edge: {analysis.edge_estimate:.2f}%")
```

##### detect_strategy_type()

```python
def detect_strategy_type(
    trades: List[Trade]
) -> Tuple[StrategyType, float]
```

Classify trading strategy.

**Parameters:**
- `trades` (List[Trade]): List of trades to classify

**Returns:** `Tuple[StrategyType, float]` - Strategy type and confidence (0-1)

##### analyze_timing_patterns()

```python
def analyze_timing_patterns(
    trades: List[Trade]
) -> TimingAnalysis
```

Analyze when and how frequently wallet trades.

**Parameters:**
- `trades` (List[Trade]): List of trades

**Returns:** `TimingAnalysis`

##### analyze_market_concentration()

```python
def analyze_market_concentration(
    trades: List[Trade]
) -> float
```

Analyze market focus using Gini coefficient.

**Parameters:**
- `trades` (List[Trade]): List of trades

**Returns:** `float` - Gini coefficient (0=diversified, 1=concentrated)

##### analyze_position_sizing()

```python
def analyze_position_sizing(
    trades: List[Trade]
) -> SizingAnalysis
```

Detect position sizing patterns.

**Parameters:**
- `trades` (List[Trade]): List of trades

**Returns:** `SizingAnalysis`

##### calculate_profit_acceleration()

```python
def calculate_profit_acceleration(
    trades: List[Trade]
) -> float
```

Measure exponential profit growth.

**Parameters:**
- `trades` (List[Trade]): List of trades (chronological)

**Returns:** `float` - Exponential coefficient (>1.0 = accelerating)

##### detect_maker_vs_taker()

```python
def detect_maker_vs_taker(
    trades: List[Trade]
) -> float
```

Calculate maker order ratio.

**Parameters:**
- `trades` (List[Trade]): List of trades

**Returns:** `float` - Maker ratio (0-1)

### Data Classes

#### StrategyType (Enum)

```python
class StrategyType(Enum):
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    DIRECTIONAL = "directional"
    SNIPER = "sniper"
    UNKNOWN = "unknown"
```

#### WalletAnalysis

```python
@dataclass
class WalletAnalysis:
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
```

#### TimingAnalysis

```python
@dataclass
class TimingAnalysis:
    avg_hold_time: float  # seconds
    trade_frequency: float  # trades per day
    time_of_day_pattern: dict[int, float]  # hour -> frequency
    day_of_week_pattern: dict[int, float]  # day -> frequency
    burst_trading_score: float  # 0-1
```

#### SizingAnalysis

```python
@dataclass
class SizingAnalysis:
    avg_size: float
    max_size: float
    size_variance: float
    scaling_pattern: str  # 'fixed', 'kelly', 'martingale', 'progressive', 'variable'
    size_percentiles: dict[int, float]
```

#### Trade

```python
@dataclass
class Trade:
    timestamp: datetime
    market_id: str
    side: str  # 'YES' or 'NO'
    size: float
    price: float
    is_maker: bool
    realized_pnl: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
```

## signals.py

### SignalDetector

Class for detecting anomalous wallet behavior indicating edge.

#### Constructor

```python
SignalDetector()
```

#### Methods

##### detect_profit_spike()

```python
def detect_profit_spike(
    trades: List[Trade],
    multiplier: float = 3.0
) -> Optional[Signal]
```

Detect sudden profit jump.

**Parameters:**
- `trades` (List[Trade]): Chronologically sorted trades
- `multiplier` (float): Threshold multiplier (default: 3.0)

**Returns:** `Optional[Signal]` - Signal or None if not detected

##### detect_win_rate_anomaly()

```python
def detect_win_rate_anomaly(
    trades: List[Trade],
    threshold: float = 0.90,
    min_trades: int = 100
) -> Optional[Signal]
```

Detect statistically improbable win rate.

**Parameters:**
- `trades` (List[Trade]): List of trades
- `threshold` (float): Minimum win rate (default: 0.90)
- `min_trades` (int): Minimum trades for significance (default: 100)

**Returns:** `Optional[Signal]`

##### detect_rapid_growth()

```python
def detect_rapid_growth(
    profile: WalletProfile,
    max_age_days: int = 60,
    min_profit: float = 10000.0
) -> Optional[Signal]
```

Detect new wallet with high profit.

**Parameters:**
- `profile` (WalletProfile): Wallet profile
- `max_age_days` (int): Maximum age (default: 60)
- `min_profit` (float): Minimum profit (default: 10000.0)

**Returns:** `Optional[Signal]`

##### detect_market_specialist()

```python
def detect_market_specialist(
    trades: List[Trade],
    threshold: float = 0.80
) -> Optional[Signal]
```

Detect category concentration.

**Parameters:**
- `trades` (List[Trade]): List of trades with categories
- `threshold` (float): Minimum concentration (default: 0.80)

**Returns:** `Optional[Signal]`

##### detect_frequency_spike()

```python
def detect_frequency_spike(
    trades: List[Trade],
    multiplier: float = 5.0
) -> Optional[Signal]
```

Detect sudden increase in trading frequency.

**Parameters:**
- `trades` (List[Trade]): Chronologically sorted trades
- `multiplier` (float): Threshold multiplier (default: 5.0)

**Returns:** `Optional[Signal]`

##### detect_consistent_edge()

```python
def detect_consistent_edge(
    trades: List[Trade],
    min_days: int = 7
) -> Optional[Signal]
```

Detect consecutive profitable days.

**Parameters:**
- `trades` (List[Trade]): Chronologically sorted trades
- `min_days` (int): Minimum consecutive days (default: 7)

**Returns:** `Optional[Signal]`

##### detect_all_signals()

```python
def detect_all_signals(
    trades: List[Trade],
    profile: Optional[WalletProfile] = None
) -> List[Signal]
```

Run all signal detectors.

**Parameters:**
- `trades` (List[Trade]): List of trades
- `profile` (Optional[WalletProfile]): Wallet profile for context

**Returns:** `List[Signal]` - All detected signals

**Example:**
```python
detector = SignalDetector()
signals = detector.detect_all_signals(trades, profile)
for signal in signals:
    print(f"{signal.signal_type}: {signal.strength:.2f}")
    print(f"  {signal.description}")
```

### Data Classes

#### Signal

```python
@dataclass
class Signal:
    signal_type: str
    strength: float  # 0.0-1.0
    description: str
    evidence: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

**Signal Types:**
- `PROFIT_SPIKE` - Sudden profit jump
- `WIN_RATE_ANOMALY` - Improbable win rate
- `RAPID_GROWTH` - New wallet, high profit
- `MARKET_SPECIALIST` - Category concentration
- `FREQUENCY_SPIKE` - Trading frequency increase
- `CONSISTENT_EDGE` - Consecutive profitable days

## reverse.py

### StrategyReverser

Class for reverse-engineering strategies into actionable blueprints.

#### Constructor

```python
StrategyReverser(
    min_confidence: float = 0.6,
    min_evidence: int = 10
)
```

**Parameters:**
- `min_confidence` (float): Minimum rule confidence (default: 0.6)
- `min_evidence` (int): Minimum supporting trades (default: 10)

#### Methods

##### reverse_engineer()

```python
def reverse_engineer(
    trades: List[Trade],
    analysis: Optional[WalletAnalysis] = None
) -> StrategyBlueprint
```

Generate complete strategy blueprint from trades.

**Parameters:**
- `trades` (List[Trade]): List of trades to analyze
- `analysis` (Optional[WalletAnalysis]): Pre-computed analysis

**Returns:** `StrategyBlueprint`

**Example:**
```python
reverser = StrategyReverser(min_confidence=0.7)
blueprint = reverser.reverse_engineer(trades)
print(f"Strategy: {blueprint.name}")
print(f"Replicability: {blueprint.replicability_score:.2f}")
for rule in blueprint.entry_rules:
    print(f"  Entry: {rule.condition} = {rule.value}")
```

##### extract_entry_rules()

```python
def extract_entry_rules(
    trades: List[Trade]
) -> List[Rule]
```

Extract entry conditions from trades.

##### extract_exit_rules()

```python
def extract_exit_rules(
    trades: List[Trade]
) -> List[Rule]
```

Extract exit conditions from trades.

##### extract_sizing_rules()

```python
def extract_sizing_rules(
    trades: List[Trade]
) -> List[Rule]
```

Extract position sizing methodology.

##### extract_market_filters()

```python
def extract_market_filters(
    trades: List[Trade]
) -> List[Rule]
```

Extract market selection criteria.

##### to_json()

```python
def to_json(
    blueprint: StrategyBlueprint
) -> str
```

Serialize blueprint to JSON.

##### from_json()

```python
@staticmethod
def from_json(json_str: str) -> StrategyBlueprint
```

Deserialize blueprint from JSON.

### Data Classes

#### StrategyType (Enum)

```python
class StrategyType(Enum):
    ARBITRAGE_BINARY = "arbitrage_binary"
    ARBITRAGE_MULTI = "arbitrage_multi"
    MARKET_MAKER = "market_maker"
    DIRECTIONAL = "directional"
    SNIPER = "sniper"
    HYBRID = "hybrid"
```

#### RuleType (Enum)

```python
class RuleType(Enum):
    ENTRY_CONDITION = "entry_condition"
    EXIT_CONDITION = "exit_condition"
    SIZING_RULE = "sizing_rule"
    MARKET_FILTER = "market_filter"
```

#### Rule

```python
@dataclass
class Rule:
    condition: str
    value: Any
    confidence: float  # 0-1
    evidence_count: int
    rule_type: RuleType
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### StrategyBlueprint

```python
@dataclass
class StrategyBlueprint:
    name: str
    strategy_type: StrategyType
    entry_rules: List[Rule]
    exit_rules: List[Rule]
    sizing_rules: List[Rule]
    market_filters: List[Rule]
    estimated_edge: Dict[str, float]
    capital_required: float
    replicability_score: float
    timeframe: str = "unknown"
    trade_frequency: float = 0.0
    win_rate: float = 0.0
    risk_profile: str = "unknown"
    additional_notes: str = ""
```

**Methods:**
- `to_dict()` -> Dict[str, Any]: Convert to dictionary
- `summary()` -> str: Human-readable summary

## config.py

### Config

Configuration management with environment variables and YAML support.

#### Constructor

```python
@dataclass
class Config:
    polymarket_data_api: str = "https://data-api.polymarket.com"
    polymarket_gamma_api: str = "https://gamma-api.polymarket.com"
    scan_min_profit: float = 5000.0
    scan_min_win_rate: float = 0.85
    scan_max_age_days: int = 60
    rate_limit_rps: int = 5
    rate_limit_burst: int = 10
    output_dir: Path = Path("./output")
    data_dir: Path = Path("./data")
    min_trades_for_analysis: int = 10
    lookback_days: int = 90
    watchlist_path: Path = Path("./data/watchlist.json")
    log_level: str = "INFO"
    log_file: Optional[Path] = None
```

#### Methods

##### from_env()

```python
@classmethod
def from_env(cls) -> Config
```

Load configuration from environment variables.

**Example:**
```python
config = Config.from_env()
```

##### from_yaml()

```python
@classmethod
def from_yaml(cls, config_path: Path) -> Config
```

Load configuration from YAML file.

**Example:**
```python
config = Config.from_yaml(Path("config.yaml"))
```

##### load()

```python
@classmethod
def load(cls, config_path: Optional[Path] = None) -> Config
```

Load with precedence: CLI > env > YAML > defaults.

**Example:**
```python
config = Config.load(Path("config.yaml"))
```

##### to_dict()

```python
def to_dict(self) -> dict
```

Convert configuration to dictionary.

## Configuration Options

### API Endpoints

- `polymarket_data_api` (str): Data API URL
- `polymarket_gamma_api` (str): Gamma API URL

### Scanning Thresholds

- `scan_min_profit` (float): Minimum profit in USD
- `scan_min_win_rate` (float): Minimum win rate (0-1)
- `scan_max_age_days` (int): Maximum account age in days

### Rate Limiting

- `rate_limit_rps` (int): Requests per second
- `rate_limit_burst` (int): Burst size

### Directories

- `output_dir` (Path): Output directory for reports
- `data_dir` (Path): Data storage directory

### Analysis Settings

- `min_trades_for_analysis` (int): Minimum trades required
- `lookback_days` (int): Historical lookback period

### Watchlist

- `watchlist_path` (Path): Watchlist JSON file path

### Logging

- `log_level` (str): Log level (DEBUG, INFO, WARNING, ERROR)
- `log_file` (Optional[Path]): Log file path

## Extension Points

### Custom Signal Detectors

Extend `SignalDetector` to add custom signals:

```python
class CustomSignalDetector(SignalDetector):
    def detect_my_signal(self, trades: List[Trade]) -> Optional[Signal]:
        # Your custom logic
        if some_condition:
            return Signal(
                signal_type="MY_SIGNAL",
                strength=0.8,
                description="Custom signal detected",
                evidence={"key": "value"},
            )
        return None
```

### Custom Strategy Classification

Extend `TradeAnalyzer` to add strategy types:

```python
class CustomAnalyzer(TradeAnalyzer):
    def detect_strategy_type(self, trades: List[Trade]) -> Tuple[StrategyType, float]:
        # Your custom classification logic
        if my_heuristic(trades):
            return StrategyType.CUSTOM, 0.9
        return super().detect_strategy_type(trades)
```

### Custom Rule Extraction

Extend `StrategyReverser` to extract custom rules:

```python
class CustomReverser(StrategyReverser):
    def extract_my_rules(self, trades: List[Trade]) -> List[Rule]:
        # Your custom rule extraction
        rules = []
        # ... extract rules
        return rules
```

### Custom Data Sources

Extend `WalletScanner` to add data sources:

```python
class CustomScanner(WalletScanner):
    async def fetch_from_custom_api(self, params: dict) -> dict:
        url = "https://my-api.com/endpoint"
        return await self._request("GET", url, params)
```

## Error Handling

All async methods may raise:
- `httpx.HTTPError` - Network or HTTP errors
- `asyncio.TimeoutError` - Request timeout
- `ValueError` - Invalid parameters
- `KeyError` - Missing data in API response

**Recommended pattern:**

```python
try:
    async with WalletScanner() as scanner:
        result = await scanner.fetch_leaderboard()
except httpx.HTTPError as e:
    print(f"HTTP error: {e}")
except asyncio.TimeoutError:
    print("Request timed out")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Performance Considerations

**Rate Limiting:**
- Default 5 req/sec is conservative
- Increase cautiously to avoid blocking
- Use caching to minimize requests

**Concurrency:**
- `batch_fetch_wallet_stats()` uses semaphore
- Default max_concurrent=5 is safe
- Increase for faster batch operations

**Caching:**
- Default 300s TTL balances freshness vs speed
- Clear cache for time-sensitive operations
- Cache key includes all parameters

**Memory:**
- Large scans load many profiles in memory
- Process in batches if memory constrained
- Clear `trades` list from profiles if not needed

## Testing

All modules include example usage in their docstrings. Run module directly:

```bash
python src/scanner.py
python src/analyzer.py
python src/signals.py
python src/reverse.py
```

Or use pytest:

```bash
pytest tests/ -v
```

## Version Compatibility

- Python: 3.10+
- httpx: 0.27.0+
- pandas: 2.2.0+
- numpy: 1.26.0+
- click: 8.1.7+
- rich: 13.7.0+

See `pyproject.toml` for complete dependency list.
