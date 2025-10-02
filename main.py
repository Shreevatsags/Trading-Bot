#!/usr/bin/env python3
"""
Simplified Binance Futures (USDT-M) Trading Bot (Testnet)
Supports MARKET, LIMIT and simple TWAP (sliced MARKET) orders.

Usage examples:
  python main.py --symbol BTCUSDT --side BUY --ordertype MARKET --quantity 0.001
  python main.py --symbol BTCUSDT --side SELL --ordertype LIMIT --quantity 0.001 --price 30000
  python main.py --symbol BTCUSDT --side BUY --ordertype TWAP --quantity 0.01 --slices 5 --interval 10

Note: Requires a Binance Futures Testnet API key/secret and .env file.
"""

import os
import time
import hmac
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import argparse
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv
from math import isfinite

# Load .env
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
if not API_KEY or not API_SECRET:
    raise SystemExit("ERROR: API_KEY and API_SECRET must be set in .env")

# Binance Futures Testnet base URL (USDT-M)
BASE_URL = "https://testnet.binancefuture.com"  # per assignment
ORDER_ENDPOINT = "/fapi/v1/order"  # new order

# Logging setup
LOGFILE = "trading_bot.log"
logger = logging.getLogger("trading_bot")
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(fmt)
logger.addHandler(ch)

fh = RotatingFileHandler(LOGFILE, maxBytes=5_000_000, backupCount=3)
fh.setLevel(logging.DEBUG)
fh.setFormatter(fmt)
logger.addHandler(fh)


class BinanceFuturesClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = BASE_URL, recv_window: int = 5000):
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.recv_window = recv_window
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})
        self.time_offset = self._get_server_time_offset()

    def _get_server_time_offset(self) -> int:
        try:
            r = self.session.get(self.base_url + "/fapi/v1/time", timeout=5)
            r.raise_for_status()
            server_time = r.json()["serverTime"]
            local_time = int(time.time() * 1000)
            offset = server_time - local_time
            logger.info("Server time offset: %d ms", offset)
            return offset
        except Exception as e:
            logger.warning("Failed to fetch server time, default offset=0: %s", e)
            return 0

    def _timestamp(self) -> int:
        return int(time.time() * 1000 + self.time_offset)

    def _sign(self, params: dict) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        query = urlencode(params, doseq=True)
        signature = hmac.new(self.api_secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
        signed = params.copy()
        signed["signature"] = signature
        return signed

    def _post(self, path: str, params: dict, timeout: int = 10) -> dict:
        url = self.base_url + path
        signed = self._sign(params)
        logger.debug("POST %s %s", url, params)
        try:
            resp = self.session.post(url, data=signed, timeout=timeout)
            text = resp.text
            logger.debug("Response [%s]: %s", resp.status_code, text)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error("HTTP error during POST %s : %s", url, str(e))
            try:
                return {"error": str(e), "raw": resp.text}
            except Exception:
                return {"error": str(e)}

    def place_order(self, symbol: str, side: str, ordertype: str, quantity: float,
                    price: float = None, stop_price: float = None, time_in_force: str = "GTC",
                    reduce_only: bool = False, close_position: bool = False) -> dict:
        side = side.upper()
        ordertype = ordertype.upper()
        assert side in ("BUY", "SELL")
        assert ordertype in ("MARKET", "LIMIT")

        params = {
            "symbol": symbol,
            "side": side,
            "type": ordertype,
            "quantity": float(quantity),
            "timestamp": self._timestamp(),
            "recvWindow": self.recv_window,
            "reduceOnly": str(reduce_only).lower(),
            "closePosition": str(close_position).lower(),
        }

        if ordertype == "LIMIT":
            if price is None:
                raise ValueError("LIMIT order requires --price")
            params.update({
                "price": float(price),
                "timeInForce": time_in_force
            })
        elif ordertype == "MARKET":
            params.pop("price", None)

        return self._post(ORDER_ENDPOINT, params)

    def simple_twap(self, symbol: str, side: str, total_qty: float, slices: int, interval: int):
        if slices <= 0:
            raise ValueError("slices must be > 0")
        per_slice = float(total_qty) / slices
        logger.info("TWAP: %s slices of %s each, interval=%ss", slices, per_slice, interval)
        results = []
        for i in range(slices):
            logger.info("TWAP slice %d/%d: placing MARKET order for %s %s", i+1, slices, per_slice, symbol)
            res = self.place_order(symbol=symbol, side=side, ordertype="MARKET", quantity=per_slice)
            results.append(res)
            if i < slices - 1:
                time.sleep(interval)
        return results

    def get_current_price(self, symbol: str) -> float:
        resp = self.session.get(self.base_url + "/fapi/v1/ticker/price", params={"symbol": symbol}).json()
        return float(resp["price"])


# ------------------------
# Helper functions
# ------------------------
def ensure_min_notional(symbol: str, quantity: float, client: BinanceFuturesClient) -> float:
    min_notional = 100
    current_price = client.get_current_price(symbol)
    if quantity * current_price < min_notional:
        quantity = min_notional / current_price
        logger.info("Adjusted quantity to meet min notional: %.6f", quantity)
    return round(quantity, 6)


def retry_order(client: BinanceFuturesClient, **kwargs) -> dict:
    for attempt in range(3):
        resp = client.place_order(**kwargs)
        if resp.get("code") == -1000:
            logger.warning("Retrying due to Testnet error (-1000), attempt %d/3", attempt+1)
            time.sleep(2)
            continue
        return resp
    return resp


# ------------------------
# CLI Parsing
# ------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Simplified Binance Futures Testnet Trading Bot")
    p.add_argument("--symbol", required=True, help="Trading pair e.g., BTCUSDT")
    p.add_argument("--side", required=True, choices=["BUY", "SELL"], help="BUY or SELL")
    p.add_argument("--ordertype", required=True, choices=["MARKET", "LIMIT", "TWAP"], help="Order type")
    p.add_argument("--quantity", required=True, type=float, help="Order quantity (number)")
    p.add_argument("--price", type=float, help="Price (required for LIMIT)")
    p.add_argument("--stop-price", type=float, help="Stop price (optional)")
    p.add_argument("--slices", type=int, default=1, help="TWAP slices (for TWAP)")
    p.add_argument("--interval", type=int, default=10, help="TWAP slice interval seconds")
    p.add_argument("--time-in-force", default="GTC", choices=["GTC", "IOC", "FOK"], help="Time in force for LIMIT")
    return p.parse_args()


def validate_args(args):
    if args.ordertype == "LIMIT" and args.price is None:
        raise SystemExit("ERROR: LIMIT order requires --price")
    if args.ordertype == "TWAP":
        if args.slices <= 0:
            raise SystemExit("ERROR: --slices must be > 0 for TWAP")
        if args.interval < 0:
            raise SystemExit("ERROR: --interval must be >= 0")
    if not isfinite(args.quantity) or args.quantity <= 0:
        raise SystemExit("ERROR: --quantity must be > 0")
    return True


# ------------------------
# Main run
# ------------------------
def run():
    args = parse_args()
    validate_args(args)

    client = BinanceFuturesClient(API_KEY, API_SECRET, recv_window=10000)

    # Auto-adjust quantity to meet min notional for MARKET/LIMIT
    if args.ordertype != "TWAP":
        args.quantity = ensure_min_notional(args.symbol, args.quantity, client)

    logger.info("Placing order: %s %s %s qty=%s", args.symbol, args.side, args.ordertype, args.quantity)

    try:
        if args.ordertype == "MARKET":
            resp = retry_order(client,
                               symbol=args.symbol,
                               side=args.side,
                               ordertype="MARKET",
                               quantity=args.quantity)
            logger.info("Order response: %s", resp)
            print("--- ORDER RESULT ---")
            print(resp)

        elif args.ordertype == "LIMIT":
            # If price not provided, fetch current price ± small delta
            if args.price is None:
                current_price = client.get_current_price(args.symbol)
                args.price = current_price + 1 if args.side == "BUY" else current_price - 1
                logger.info("Auto-set LIMIT price: %s", args.price)

            resp = retry_order(client,
                               symbol=args.symbol,
                               side=args.side,
                               ordertype="LIMIT",
                               quantity=args.quantity,
                               price=args.price,
                               time_in_force=args.time_in_force)
            logger.info("Order response: %s", resp)
            print("--- ORDER RESULT ---")
            print(resp)

        elif args.ordertype == "TWAP":
            results = client.simple_twap(
                symbol=args.symbol,
                side=args.side,
                total_qty=args.quantity,
                slices=args.slices,
                interval=args.interval
            )
            logger.info("TWAP results collected.")
            print("--- TWAP RESULTS ---")
            for i, r in enumerate(results, 1):
                print(f"Slice {i}: {r}")

    except AssertionError as a:
        logger.error("Assertion/validation error: %s", a)
        raise SystemExit(str(a))
    except ValueError as v:
        logger.error("Value error: %s", v)
        raise SystemExit(str(v))
    except Exception as e:
        logger.exception("Unhandled error during order placement: %s", e)
        raise SystemExit("Order failed. Check logs for details.")

