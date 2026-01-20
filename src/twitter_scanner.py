"""
Twitter/X.com scanner for poly-scout.

Scans X.com mentions of Polymarket via Nitter (free alternative).
Extracts market URLs, price claims, and whale activity from tweets.
"""

import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from src.config import NITTER_INSTANCES, GAMMA_API_BASE, SEEN_TWEETS_FILE


def log(msg: str):
    print(f"[TWITTER] {msg}", flush=True)


@dataclass
class TweetSignal:
    """A signal extracted from a tweet about Polymarket."""
    tweet_id: str
    author: str
    text: str
    timestamp: datetime
    market_url: Optional[str]
    market_slug: Optional[str]
    price_mentioned: Optional[float]
    whale_amount: Optional[float]
    signal_type: str  # "market_mention", "price_claim", "whale_alert", "news"


class TwitterScanner:
    """Scan X.com for Polymarket opportunities using Nitter."""

    SEARCH_TERMS = [
        "polymarket",
        "@Polymarket",
        "polymarket.com",
    ]

    # Regex patterns
    PM_URL_PATTERN = re.compile(r'polymarket\.com/event/([a-z0-9-]+)', re.IGNORECASE)
    PRICE_PATTERN = re.compile(r'(\d{1,3})%|trading at (\d{1,3})|priced at (\d{1,3})', re.IGNORECASE)
    WHALE_PATTERN = re.compile(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|m|bet|wager|position)', re.IGNORECASE)

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)
        self.seen_tweets = self._load_seen_tweets()
        self.current_nitter_index = 0

    def _load_seen_tweets(self) -> set:
        """Load previously seen tweet IDs."""
        try:
            path = Path(SEEN_TWEETS_FILE)
            if path.exists():
                with open(path) as f:
                    return set(json.load(f))
        except Exception:
            pass
        return set()

    def _save_seen_tweets(self):
        """Save seen tweet IDs."""
        try:
            path = Path(SEEN_TWEETS_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(list(self.seen_tweets), f)
        except Exception as e:
            log(f"Error saving seen tweets: {e}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self._save_seen_tweets()
        await self.client.aclose()

    def _get_nitter_url(self) -> str:
        """Get current Nitter instance URL."""
        instance = NITTER_INSTANCES[self.current_nitter_index % len(NITTER_INSTANCES)]
        return f"https://{instance}"

    def _rotate_nitter(self):
        """Rotate to next Nitter instance."""
        self.current_nitter_index += 1
        log(f"Rotating to Nitter instance: {NITTER_INSTANCES[self.current_nitter_index % len(NITTER_INSTANCES)]}")

    async def search_tweets(self, query: str, max_results: int = 50) -> list[dict]:
        """Search for tweets using Nitter."""
        tweets = []

        for attempt in range(len(NITTER_INSTANCES)):
            try:
                base_url = self._get_nitter_url()
                search_url = f"{base_url}/search?f=tweets&q={query}"

                resp = await self.client.get(search_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })

                if resp.status_code != 200:
                    self._rotate_nitter()
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Parse tweets from Nitter HTML
                for tweet_div in soup.select(".timeline-item"):
                    try:
                        # Extract tweet data
                        tweet_link = tweet_div.select_one(".tweet-link")
                        if not tweet_link:
                            continue

                        tweet_url = tweet_link.get("href", "")
                        tweet_id = tweet_url.split("/")[-1].split("#")[0] if tweet_url else ""

                        author_elem = tweet_div.select_one(".username")
                        author = author_elem.text.strip() if author_elem else ""

                        content_elem = tweet_div.select_one(".tweet-content")
                        text = content_elem.text.strip() if content_elem else ""

                        time_elem = tweet_div.select_one(".tweet-date a")
                        time_str = time_elem.get("title", "") if time_elem else ""

                        tweets.append({
                            "id": tweet_id,
                            "author": author,
                            "text": text,
                            "time_str": time_str,
                            "url": tweet_url,
                        })

                        if len(tweets) >= max_results:
                            break

                    except Exception as e:
                        continue

                break  # Success, exit retry loop

            except Exception as e:
                log(f"Nitter error: {e}")
                self._rotate_nitter()

        return tweets

    def extract_signals(self, tweets: list[dict]) -> list[TweetSignal]:
        """Extract actionable signals from tweets."""
        signals = []

        for tweet in tweets:
            tweet_id = tweet.get("id", "")

            # Skip if already seen
            if tweet_id in self.seen_tweets:
                continue

            text = tweet.get("text", "")

            # Extract market URL
            market_match = self.PM_URL_PATTERN.search(text)
            market_url = None
            market_slug = None
            if market_match:
                market_slug = market_match.group(1)
                market_url = f"https://polymarket.com/event/{market_slug}"

            # Extract price mentions
            price_mentioned = None
            price_match = self.PRICE_PATTERN.search(text)
            if price_match:
                for group in price_match.groups():
                    if group:
                        price_mentioned = float(group) / 100
                        break

            # Extract whale amounts
            whale_amount = None
            whale_match = self.WHALE_PATTERN.search(text)
            if whale_match:
                amount_str = whale_match.group(1).replace(",", "")
                whale_amount = float(amount_str)
                if "k" in text.lower():
                    whale_amount *= 1000
                elif "m" in text.lower():
                    whale_amount *= 1_000_000

            # Determine signal type
            signal_type = "market_mention"
            if whale_amount and whale_amount >= 10000:
                signal_type = "whale_alert"
            elif price_mentioned:
                signal_type = "price_claim"
            elif any(kw in text.lower() for kw in ["mispriced", "undervalued", "edge", "opportunity", "free money"]):
                signal_type = "price_claim"

            # Parse timestamp
            try:
                time_str = tweet.get("time_str", "")
                if time_str:
                    timestamp = datetime.strptime(time_str, "%b %d, %Y · %I:%M %p %Z")
                else:
                    timestamp = datetime.now()
            except Exception:
                timestamp = datetime.now()

            signals.append(TweetSignal(
                tweet_id=tweet_id,
                author=tweet.get("author", ""),
                text=text[:500],  # Truncate
                timestamp=timestamp,
                market_url=market_url,
                market_slug=market_slug,
                price_mentioned=price_mentioned,
                whale_amount=whale_amount,
                signal_type=signal_type,
            ))

            self.seen_tweets.add(tweet_id)

        return signals

    async def validate_market(self, slug: str) -> Optional[dict]:
        """Validate that a mentioned market exists and get current price."""
        try:
            url = f"{GAMMA_API_BASE}/events?slug={slug}"
            resp = await self.client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    return data[0]
        except Exception as e:
            log(f"Error validating market {slug}: {e}")
        return None

    async def scan_all(self) -> list[TweetSignal]:
        """Scan all Polymarket mentions on X.com."""
        all_signals = []

        for term in self.SEARCH_TERMS:
            log(f"Searching: {term}")
            tweets = await self.search_tweets(term, max_results=30)
            log(f"  Found {len(tweets)} tweets")

            signals = self.extract_signals(tweets)
            all_signals.extend(signals)

        # Deduplicate by tweet_id
        seen_ids = set()
        unique_signals = []
        for sig in all_signals:
            if sig.tweet_id not in seen_ids:
                seen_ids.add(sig.tweet_id)
                unique_signals.append(sig)

        # Sort by signal type priority
        type_priority = {"whale_alert": 0, "price_claim": 1, "market_mention": 2, "news": 3}
        unique_signals.sort(key=lambda x: type_priority.get(x.signal_type, 99))

        return unique_signals


async def main():
    """Test the Twitter scanner."""
    async with TwitterScanner() as scanner:
        signals = await scanner.scan_all()

        print(f"\nFound {len(signals)} signals")
        for sig in signals[:10]:
            print(f"\n[{sig.signal_type.upper()}] @{sig.author}")
            print(f"  {sig.text[:100]}...")
            if sig.market_slug:
                print(f"  Market: {sig.market_slug}")
            if sig.price_mentioned:
                print(f"  Price mentioned: {sig.price_mentioned:.0%}")
            if sig.whale_amount:
                print(f"  Whale amount: ${sig.whale_amount:,.0f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
