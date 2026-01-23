"""
Weather Market Arbitrage Scanner.

Finds edge in Polymarket temperature markets by comparing PM odds against
weather forecast APIs (Open-Meteo - free, no API key).

Cities tracked: Seoul, London, Wellington (based on Hans323's trading)
"""

import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Dict
import re


def log(msg: str):
    print(f"[WEATHER] {msg}", flush=True)


# Cities with their coordinates for Open-Meteo
# From polymarket.com/predictions/weather active markets
WEATHER_CITIES = {
    "london": {"lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
    "seoul": {"lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul"},
    "wellington": {"lat": -41.2866, "lon": 174.7756, "tz": "Pacific/Auckland"},
    "nyc": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
    "new-york": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "tz": "America/Chicago"},
    "los-angeles": {"lat": 34.0522, "lon": -118.2437, "tz": "America/Los_Angeles"},
    "atlanta": {"lat": 33.7490, "lon": -84.3880, "tz": "America/New_York"},
    "toronto": {"lat": 43.6532, "lon": -79.3832, "tz": "America/Toronto"},
    "ankara": {"lat": 39.9334, "lon": 32.8597, "tz": "Europe/Istanbul"},
    "seattle": {"lat": 47.6062, "lon": -122.3321, "tz": "America/Los_Angeles"},
    "miami": {"lat": 25.7617, "lon": -80.1918, "tz": "America/New_York"},
    "buenos-aires": {"lat": -34.6037, "lon": -58.3816, "tz": "America/Argentina/Buenos_Aires"},
}


@dataclass
class WeatherForecast:
    """Weather forecast data."""
    city: str
    date: str  # YYYY-MM-DD
    high_temp_c: float
    high_temp_f: float
    forecast_model: str  # e.g. "best_match", "ecmwf", "gfs"
    fetched_at: datetime


@dataclass
class WeatherMarket:
    """A Polymarket weather market."""
    city: str
    date: str
    temp_bracket: str  # e.g., "8", "9", "0 or higher"
    temp_unit: str  # "C" or "F"
    pm_price_yes: float  # Price of YES outcome (probability)
    pm_price_no: float
    condition_id: str
    market_slug: str


@dataclass
class WeatherEdge:
    """Detected edge opportunity."""
    market: WeatherMarket
    forecast: WeatherForecast
    pm_probability: float  # PM implied probability
    forecast_probability: float  # Our calculated probability
    edge_pct: float  # Difference (positive = opportunity)
    direction: str  # "BUY_YES" or "BUY_NO"
    confidence: str  # "HIGH", "MEDIUM", "LOW"


def fetch_weather_forecast(city: str, date: str) -> Optional[WeatherForecast]:
    """
    Fetch weather forecast from Open-Meteo API.

    Args:
        city: City name (must be in WEATHER_CITIES)
        date: Date in YYYY-MM-DD format

    Returns:
        WeatherForecast or None if failed
    """
    if city not in WEATHER_CITIES:
        log(f"Unknown city: {city}")
        return None

    coords = WEATHER_CITIES[city]

    try:
        # Open-Meteo API - free, no key required
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={coords['lat']}&longitude={coords['lon']}"
            f"&daily=temperature_2m_max"
            f"&timezone={coords['tz']}"
            f"&start_date={date}&end_date={date}"
        )

        r = requests.get(url, timeout=10)
        data = r.json()

        if "daily" not in data or not data["daily"]["temperature_2m_max"]:
            log(f"No forecast data for {city} on {date}")
            return None

        high_c = data["daily"]["temperature_2m_max"][0]
        high_f = (high_c * 9/5) + 32

        return WeatherForecast(
            city=city,
            date=date,
            high_temp_c=high_c,
            high_temp_f=high_f,
            forecast_model="best_match",
            fetched_at=datetime.now()
        )

    except Exception as e:
        log(f"Error fetching forecast for {city}: {e}")
        return None


def calculate_temp_probability(
    forecast_temp: float,
    bracket_temp: int,
    bracket_type: str = "exact"  # "exact", "or_higher", "or_lower"
) -> float:
    """
    Calculate probability of temperature hitting a bracket.

    Uses forecast uncertainty (typically +-2°C for next-day forecasts).

    Args:
        forecast_temp: Forecasted high temperature
        bracket_temp: Target temperature in market
        bracket_type: Type of bracket comparison

    Returns:
        Probability 0.0 to 1.0
    """
    # Forecast uncertainty (standard deviation) ~2°C for 1-day forecast
    # Increases with forecast distance
    std_dev = 2.0

    # Z-score
    z = (bracket_temp - forecast_temp) / std_dev

    # Normal CDF approximation
    from math import erf, sqrt
    def norm_cdf(x):
        return 0.5 * (1 + erf(x / sqrt(2)))

    if bracket_type == "or_higher":
        # P(temp >= bracket)
        return 1 - norm_cdf(z - 0.5)  # -0.5 for discrete binning
    elif bracket_type == "or_lower":
        # P(temp <= bracket)
        return norm_cdf(z + 0.5)
    else:
        # P(temp == bracket) - probability of landing in 1-degree bucket
        return norm_cdf(z + 0.5) - norm_cdf(z - 0.5)


def parse_bracket_title(title: str) -> Optional[Dict]:
    """
    Parse groupItemTitle from API like "-6°C or below", "-5°C", "0°C or higher".

    Returns dict with temp and bracket_type.
    """
    if not title:
        return None

    # Pattern: {number}°C [or below|or higher]
    match = re.match(r"(-?\d+)°C(?: or (below|higher))?", title)
    if not match:
        return None

    temp = int(match.group(1))
    modifier = match.group(2)

    if modifier == "below":
        bracket_type = "or_lower"
    elif modifier == "higher":
        bracket_type = "or_higher"
    else:
        bracket_type = "exact"

    return {"temp": temp, "bracket_type": bracket_type, "unit": "C"}


def parse_market_question(question: str) -> Optional[Dict]:
    """
    Parse Polymarket weather question to extract city, date, temp bracket.

    Examples:
    - "Will the highest temperature in Seoul be -3°C on January 24?"
    - "Will the highest temperature in London be 8°C on January 23?"
    - "Will the highest temperature in Seoul be 0°C or higher on January 23?"
    """
    # Pattern: "highest temperature in {city} be {temp}°{C/F} on {date}"
    pattern = r"highest temperature in (\w+) be (-?\d+)°([CF])( or higher| or lower)? on (\w+ \d+)"

    match = re.search(pattern, question, re.IGNORECASE)
    if not match:
        return None

    city = match.group(1).lower()
    temp = int(match.group(2))
    unit = match.group(3).upper()
    modifier = match.group(4).strip().lower() if match.group(4) else "exact"
    date_str = match.group(5)  # e.g., "January 24"

    # Convert date string to YYYY-MM-DD
    try:
        year = datetime.now().year
        date_obj = datetime.strptime(f"{date_str} {year}", "%B %d %Y")
        # If date is in the past, assume next year
        if date_obj.date() < datetime.now().date():
            date_obj = datetime.strptime(f"{date_str} {year+1}", "%B %d %Y")
        date_formatted = date_obj.strftime("%Y-%m-%d")
    except ValueError:
        return None

    bracket_type = "exact"
    if "or higher" in modifier:
        bracket_type = "or_higher"
    elif "or lower" in modifier:
        bracket_type = "or_lower"

    return {
        "city": city,
        "temp": temp,
        "unit": unit,
        "bracket_type": bracket_type,
        "date": date_formatted
    }


def scan_weather_markets(cities: List[str] = None, days_ahead: int = 3) -> List[Dict]:
    """
    Scan Polymarket for active weather/temperature markets.

    Uses slug-based event lookup (the only working API method for daily temps).
    Pattern: highest-temperature-in-{city}-on-{month}-{day}

    Args:
        cities: List of cities to scan (defaults to Hans323's cities)
        days_ahead: How many days forward to look

    Returns list of markets with relevant data.
    """
    if cities is None:
        cities = ["seoul", "london", "wellington"]

    markets = []

    for city in cities:
        for days in range(days_ahead + 1):
            date = datetime.now() + timedelta(days=days)
            month = date.strftime("%B").lower()
            day = date.day
            date_str = date.strftime("%Y-%m-%d")

            slug = f"highest-temperature-in-{city}-on-{month}-{day}"

            try:
                r = requests.get(
                    f"https://gamma-api.polymarket.com/events/slug/{slug}",
                    timeout=15
                )

                if r.status_code == 200:
                    event = r.json()
                    event_markets = event.get("markets", [])

                    for m in event_markets:
                        # Parse temperature bracket from groupItemTitle
                        bracket_title = m.get("groupItemTitle", "")
                        parsed = parse_bracket_title(bracket_title)

                        if parsed:
                            markets.append({
                                "event": event,
                                "market": m,
                                "parsed": parsed,
                                "city": city,
                                "date": date_str,
                                "slug": slug,
                                "condition_id": m.get("conditionId", ""),
                                "volume": float(m.get("volume", 0) or 0),
                                "liquidity": float(m.get("liquidityNum", 0) or 0)
                            })

                    if event_markets:
                        log(f"Found {len(event_markets)} brackets for {city} {month} {day}")
                elif r.status_code == 404:
                    # Market doesn't exist for this date - normal
                    pass
                else:
                    log(f"Unexpected status {r.status_code} for {slug}")

            except Exception as e:
                log(f"Error fetching {slug}: {e}")

    log(f"Total: {len(markets)} weather market brackets")
    return markets


def find_weather_edges(min_edge_pct: float = 5.0) -> List[WeatherEdge]:
    """
    Find edge opportunities in weather markets.

    Args:
        min_edge_pct: Minimum edge percentage to report

    Returns:
        List of detected edges
    """
    import json as json_module

    edges = []
    markets = scan_weather_markets()

    # Cache forecasts per city/date to avoid duplicate API calls
    forecast_cache = {}

    for market_data in markets:
        parsed = market_data["parsed"]
        city = market_data["city"]
        date = market_data["date"]
        temp = parsed["temp"]
        unit = parsed.get("unit", "C")
        bracket_type = parsed["bracket_type"]

        # Get weather forecast (with caching)
        cache_key = f"{city}_{date}"
        if cache_key not in forecast_cache:
            forecast_cache[cache_key] = fetch_weather_forecast(city, date)
        forecast = forecast_cache[cache_key]

        if not forecast:
            continue

        # Convert to same unit
        if unit == "F":
            forecast_temp = forecast.high_temp_f
        else:
            forecast_temp = forecast.high_temp_c

        # Calculate our probability
        our_prob = calculate_temp_probability(forecast_temp, temp, bracket_type)

        # Get PM probability from market prices (outcomePrices is a JSON string)
        market = market_data["market"]
        try:
            prices_str = market.get("outcomePrices", "[0.5, 0.5]")
            prices = json_module.loads(prices_str) if isinstance(prices_str, str) else prices_str
            pm_prob_yes = float(prices[0])
        except (json_module.JSONDecodeError, IndexError, TypeError):
            pm_prob_yes = 0.5

        # Calculate edge
        edge_pct = (our_prob - pm_prob_yes) * 100

        # Determine direction
        if edge_pct > 0:
            direction = "BUY_YES"
            edge = edge_pct
        else:
            direction = "BUY_NO"
            edge = abs(edge_pct)

        # Determine confidence
        if edge >= 15:
            confidence = "HIGH"
        elif edge >= 10:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        if edge >= min_edge_pct:
            # Build bracket display string
            bracket_display = f"{temp}"
            if bracket_type == "or_higher":
                bracket_display += " or higher"
            elif bracket_type == "or_lower":
                bracket_display += " or below"

            market_obj = WeatherMarket(
                city=city,
                date=date,
                temp_bracket=bracket_display,
                temp_unit=unit,
                pm_price_yes=pm_prob_yes,
                pm_price_no=1 - pm_prob_yes,
                condition_id=market_data["condition_id"],
                market_slug=market_data["slug"]
            )

            edge_obj = WeatherEdge(
                market=market_obj,
                forecast=forecast,
                pm_probability=pm_prob_yes,
                forecast_probability=our_prob,
                edge_pct=edge,
                direction=direction,
                confidence=confidence
            )

            edges.append(edge_obj)

            log(f"EDGE: {city.upper()} {temp}°{unit} on {date}")
            log(f"  Forecast: {forecast_temp:.1f}°{unit}")
            log(f"  PM says: {pm_prob_yes*100:.1f}% | We say: {our_prob*100:.1f}%")
            log(f"  Edge: {edge:.1f}% → {direction} ({confidence})")

    return edges


def generate_expected_market_slugs(days_ahead: int = 2) -> List[str]:
    """
    Generate expected market slug patterns for weather markets.

    Based on observed pattern: highest-temperature-in-{city}-on-{month}-{day}
    """
    slugs = []

    for city in ["london", "seoul", "wellington"]:
        for days in range(days_ahead + 1):
            date = datetime.now() + timedelta(days=days)
            month = date.strftime("%B").lower()
            day = date.day

            slug = f"highest-temperature-in-{city}-on-{month}-{day}"
            slugs.append(slug)

    return slugs


if __name__ == "__main__":
    log("Weather Arbitrage Scanner")
    log("=" * 50)

    # Test forecast
    log("\nTesting Open-Meteo API...")
    for city in ["london", "seoul", "wellington"]:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        forecast = fetch_weather_forecast(city, tomorrow)
        if forecast:
            log(f"  {city.upper()}: {forecast.high_temp_c:.1f}°C / {forecast.high_temp_f:.1f}°F")

    # Test probability calculation
    log("\nTesting probability calculation...")
    log(f"  Forecast 8°C, bracket 8°C exact: {calculate_temp_probability(8, 8, 'exact')*100:.1f}%")
    log(f"  Forecast 8°C, bracket 10°C exact: {calculate_temp_probability(8, 10, 'exact')*100:.1f}%")
    log(f"  Forecast 8°C, bracket 6°C or higher: {calculate_temp_probability(8, 6, 'or_higher')*100:.1f}%")

    # Scan for markets
    log("\nScanning Polymarket for weather markets...")
    edges = find_weather_edges(min_edge_pct=3.0)

    if edges:
        log(f"\nFound {len(edges)} edge opportunities!")
    else:
        log("\nNo edges found (weather markets may not be active right now)")

    # Show expected slugs
    log("\nExpected market slugs to monitor:")
    for slug in generate_expected_market_slugs(2):
        log(f"  https://polymarket.com/event/{slug}")
