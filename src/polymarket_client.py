"""
Polymarket SDK and WebSocket Client for poly-scout.

Provides real-time market data via websockets and SDK integration.
"""

import json
import asyncio
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Dict, List
from queue import Queue

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BookParams
import websocket


# API endpoints
CLOB_HOST = "https://clob.polymarket.com"
WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def log(msg: str):
    print(f"[PM-CLIENT] {msg}", flush=True)


@dataclass
class OrderBookLevel:
    """Single level in the order book."""
    price: float
    size: float


@dataclass
class OrderBook:
    """Order book snapshot."""
    token_id: str
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    timestamp: datetime


class PolymarketClient:
    """
    Polymarket client using the official SDK.

    Provides order book fetching and market data via REST API.
    For paper trading (read-only), no authentication needed.
    """

    def __init__(self):
        self.client = ClobClient(CLOB_HOST)
        log("SDK client initialized (read-only mode)")

    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Fetch order book for a token using the SDK.

        Returns OrderBook with bids and asks.
        """
        try:
            book = self.client.get_order_book(token_id)

            bids = [
                OrderBookLevel(price=float(level.price), size=float(level.size))
                for level in book.bids
            ]
            asks = [
                OrderBookLevel(price=float(level.price), size=float(level.size))
                for level in book.asks
            ]

            return OrderBook(
                token_id=token_id,
                bids=bids,
                asks=asks,
                timestamp=datetime.now()
            )
        except Exception as e:
            log(f"Error fetching order book for {token_id[:16]}...: {e}")
            return None

    def get_order_books(self, token_ids: List[str]) -> Dict[str, OrderBook]:
        """Fetch multiple order books efficiently."""
        results = {}
        try:
            params = [BookParams(token_id=tid) for tid in token_ids]
            books = self.client.get_order_books(params)

            for token_id, book in zip(token_ids, books):
                bids = [
                    OrderBookLevel(price=float(level.price), size=float(level.size))
                    for level in book.bids
                ]
                asks = [
                    OrderBookLevel(price=float(level.price), size=float(level.size))
                    for level in book.asks
                ]
                results[token_id] = OrderBook(
                    token_id=token_id,
                    bids=bids,
                    asks=asks,
                    timestamp=datetime.now()
                )
        except Exception as e:
            log(f"Error fetching order books: {e}")

        return results

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token."""
        try:
            return float(self.client.get_midpoint(token_id))
        except Exception:
            return None

    def get_price(self, token_id: str, side: str = "BUY") -> Optional[float]:
        """Get best price for a side (BUY or SELL)."""
        try:
            return float(self.client.get_price(token_id, side=side))
        except Exception:
            return None

    def get_markets(self) -> List[dict]:
        """Get list of active markets."""
        try:
            return self.client.get_simplified_markets()
        except Exception as e:
            log(f"Error fetching markets: {e}")
            return []

    def get_last_trade_price(self, token_id: str) -> Optional[float]:
        """
        Get last trade price for a token.

        More accurate than midpoint for fill simulation as it reflects
        actual executed trades.
        """
        try:
            return float(self.client.get_last_trade_price(token_id))
        except Exception:
            return None

    def get_server_time(self) -> Optional[int]:
        """
        Get server time in milliseconds.

        Useful for time synchronization to ensure order timestamps
        are accurate.
        """
        try:
            return int(self.client.get_server_time())
        except Exception:
            return None

    def get_time_offset(self) -> int:
        """
        Calculate time offset between local and server time.

        Returns offset in milliseconds (positive = local ahead of server).
        """
        import time
        local_ms = int(time.time() * 1000)
        server_ms = self.get_server_time()
        if server_ms:
            return local_ms - server_ms
        return 0


class MarketWebSocket:
    """
    WebSocket client for real-time market data.

    Subscribes to order book updates for specified tokens.
    """

    def __init__(self, on_message: Optional[Callable] = None):
        self.ws: Optional[websocket.WebSocketApp] = None
        self.thread: Optional[threading.Thread] = None
        self.subscribed_tokens: set = set()
        self.on_message_callback = on_message
        self.message_queue: Queue = Queue()
        self.running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60

    def _on_open(self, ws):
        log("WebSocket connected")
        self._reconnect_delay = 1  # Reset on successful connect

        # Resubscribe to tokens if any
        if self.subscribed_tokens:
            self._send_subscribe(list(self.subscribed_tokens))

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)

            # Put in queue for async processing
            self.message_queue.put(data)

            # Call callback if provided
            if self.on_message_callback:
                self.on_message_callback(data)

        except json.JSONDecodeError:
            pass

    def _on_error(self, ws, error):
        log(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        log(f"WebSocket closed: {close_status_code} - {close_msg}")

        # Reconnect if still running
        if self.running:
            log(f"Reconnecting in {self._reconnect_delay}s...")
            threading.Timer(self._reconnect_delay, self._connect).start()
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    def _send_subscribe(self, token_ids: List[str]):
        """Send subscription message."""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            msg = {
                "assets_ids": token_ids,
                "type": "market"
            }
            self.ws.send(json.dumps(msg))
            log(f"Subscribed to {len(token_ids)} tokens")

    def _send_unsubscribe(self, token_ids: List[str]):
        """Send unsubscription message."""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            msg = {
                "assets_ids": token_ids,
                "operation": "unsubscribe"
            }
            self.ws.send(json.dumps(msg))

    def _connect(self):
        """Create and connect WebSocket."""
        self.ws = websocket.WebSocketApp(
            WS_MARKET_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.run_forever(ping_interval=10, ping_timeout=5)

    def start(self):
        """Start WebSocket connection in background thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._connect, daemon=True)
        self.thread.start()
        log("WebSocket thread started")

    def stop(self):
        """Stop WebSocket connection."""
        self.running = False
        if self.ws:
            self.ws.close()
        log("WebSocket stopped")

    def subscribe(self, token_ids: List[str]):
        """Subscribe to market updates for tokens."""
        new_tokens = [t for t in token_ids if t not in self.subscribed_tokens]
        if new_tokens:
            self.subscribed_tokens.update(new_tokens)
            self._send_subscribe(new_tokens)

    def unsubscribe(self, token_ids: List[str]):
        """Unsubscribe from tokens."""
        tokens_to_remove = [t for t in token_ids if t in self.subscribed_tokens]
        if tokens_to_remove:
            self.subscribed_tokens -= set(tokens_to_remove)
            self._send_unsubscribe(tokens_to_remove)

    def get_message(self, timeout: float = 0.1) -> Optional[dict]:
        """Get next message from queue (non-blocking)."""
        try:
            return self.message_queue.get(timeout=timeout)
        except:
            return None


class RealTimeMarketMonitor:
    """
    High-level monitor combining SDK and WebSocket for real-time market tracking.

    Detects new markets and price changes instantly via WebSocket,
    falls back to SDK for order book queries.
    """

    def __init__(self):
        self.client = PolymarketClient()
        self.ws = MarketWebSocket(on_message=self._handle_ws_message)
        self.order_books: Dict[str, OrderBook] = {}
        self.price_callbacks: List[Callable] = []
        self._lock = threading.Lock()

    def _handle_ws_message(self, data: dict):
        """Handle incoming WebSocket message."""
        # Update local order book cache
        if "market" in data:
            token_id = data.get("asset_id", "")
            if token_id:
                with self._lock:
                    # Parse and cache order book update
                    pass  # Will implement based on actual message format

    def start(self):
        """Start real-time monitoring."""
        self.ws.start()

    def stop(self):
        """Stop monitoring."""
        self.ws.stop()

    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Get order book - uses cache if available, falls back to SDK.
        """
        with self._lock:
            if token_id in self.order_books:
                cached = self.order_books[token_id]
                # Use cache if fresh (< 5 seconds old)
                age = (datetime.now() - cached.timestamp).total_seconds()
                if age < 5:
                    return cached

        # Fetch via SDK
        book = self.client.get_order_book(token_id)
        if book:
            with self._lock:
                self.order_books[token_id] = book
        return book

    def subscribe_to_tokens(self, token_ids: List[str]):
        """Subscribe to real-time updates for tokens."""
        self.ws.subscribe(token_ids)

    def add_price_callback(self, callback: Callable):
        """Add callback for price updates."""
        self.price_callbacks.append(callback)


# Async wrapper for use with asyncio
class AsyncPolymarketClient:
    """Async wrapper around the SDK client."""

    def __init__(self):
        self._client = PolymarketClient()

    async def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """Async order book fetch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_order_book, token_id)

    async def get_order_books(self, token_ids: List[str]) -> Dict[str, OrderBook]:
        """Async batch order book fetch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_order_books, token_ids)

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """Async midpoint fetch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_midpoint, token_id)

    async def get_markets(self) -> List[dict]:
        """Async markets fetch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_markets)

    async def get_last_trade_price(self, token_id: str) -> Optional[float]:
        """Async last trade price fetch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_last_trade_price, token_id)

    async def get_server_time(self) -> Optional[int]:
        """Async server time fetch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_server_time)

    async def get_time_offset(self) -> int:
        """Async time offset calculation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._client.get_time_offset)


if __name__ == "__main__":
    # Test the client
    client = PolymarketClient()

    # Get some markets
    markets = client.get_markets()
    print(f"Found {len(markets)} markets")

    if markets:
        # Get order book for first market
        token_id = markets[0].get("tokens", [{}])[0].get("token_id", "")
        if token_id:
            book = client.get_order_book(token_id)
            if book:
                print(f"Order book for {token_id[:16]}...")
                print(f"  Best bid: ${book.bids[0].price if book.bids else 0:.4f}")
                print(f"  Best ask: ${book.asks[0].price if book.asks else 0:.4f}")
