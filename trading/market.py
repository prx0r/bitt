"""MarketFrame — loads 5m candles from TAOStats + Binance.

Two data sources:
- HISTORY: TAOStats 5m OHLCV (historical backtest)
- LIVE: Bittensor node → alpha prices every 5 min

BTC/ETH/TAO context features from Binance.

Stores in market.duckdb (boring analytical store, not Hydra).
"""
import sqlite3
import json
import http.client
import ssl
from pathlib import Path


DB_PATH = Path("/root/bitt/market.duckdb")
CTX = ssl.create_default_context()


def init_db():
    """Initialize market database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subnet_5m (
            timestamp TEXT,
            netuid INTEGER,
            open REAL,
            high REAL,
            low REAL,
            close_tao REAL,
            volume REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS macro_5m (
            timestamp TEXT,
            btc_usd REAL,
            eth_usd REAL,
            tao_usd REAL
        )
    """)
    conn.commit()
    conn.close()


def store_subnet_candles(netuid: int, candles: list[dict]):
    """Store 5m candles for a subnet."""
    conn = sqlite3.connect(str(DB_PATH))
    for c in candles:
        conn.execute(
            "INSERT INTO subnet_5m (timestamp, netuid, open, high, low, close_tao, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c.get('t'), netuid, c.get('o'), c.get('h'), c.get('l'), c.get('c'), c.get('v', 0))
        )
    conn.commit()
    conn.close()


def store_macro_candles(candles: list[dict]):
    """Store macro candles (BTC, ETH, TAO)."""
    conn = sqlite3.connect(str(DB_PATH))
    for c in candles:
        conn.execute(
            "INSERT INTO macro_5m (timestamp, btc_usd, eth_usd, tao_usd) "
            "VALUES (?, ?, ?, ?)",
            (c.get('t'), c.get('btc'), c.get('eth'), c.get('tao'))
        )
    conn.commit()
    conn.close()


def get_subnet_candles(netuid: int, limit: int = 1000) -> list[dict]:
    """Get 5m candles for a subnet."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM subnet_5m WHERE netuid = ? ORDER BY timestamp DESC LIMIT ?",
        (netuid, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_prices() -> dict[int, float]:
    """Get latest price for each subnet."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT netuid, close_tao FROM subnet_5m "
        "WHERE timestamp = (SELECT MAX(timestamp) FROM subnet_5m) "
        "OR timestamp IN (SELECT MAX(timestamp) FROM subnet_5m GROUP BY netuid)"
    ).fetchall()
    conn.close()
    return {r['netuid']: r['close_tao'] for r in rows}


def get_market_frame(timestamp: str) -> dict:
    """Get all data for a specific timestamp (5m bucket)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Get subnet prices
    sub_rows = conn.execute(
        "SELECT netuid, close_tao FROM subnet_5m WHERE timestamp = ?",
        (timestamp,)
    ).fetchall()
    subs = {r['netuid']: r['close_tao'] for r in sub_rows}

    # Get macro
    macro_row = conn.execute(
        "SELECT * FROM macro_5m WHERE timestamp = ?",
        (timestamp,)
    ).fetchone()
    macro = dict(macro_row) if macro_row else {}

    conn.close()

    return {
        "timestamp": timestamp,
        "subnets": subs,
        "macro": macro,
    }


def init_from_oracle():
    """Initialize market DB from existing oracle.db data."""
    oracle_db = sqlite3.connect(str(Path("/root/bitt/oracle.db")))
    oracle_db.row_factory = sqlite3.Row

    # Get all historical scans
    rows = oracle_db.execute(
        "SELECT data, scanned_at FROM subnet_snapshots ORDER BY scanned_at"
    ).fetchall()

    market_db = sqlite3.connect(str(DB_PATH))
    for row in rows:
        data = json.loads(row['data'])
        netuid = data.get('netuid', 0)
        alpha_price = data.get('alpha_price', 0)
        tao_day = data.get('tao_equiv_day', 0)

        # Store as a single "candle" (simplified)
        market_db.execute(
            "INSERT INTO subnet_5m (timestamp, netuid, open, high, low, close_tao, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row['scanned_at'], netuid, alpha_price, alpha_price, alpha_price, tao_day, 0)
        )

    market_db.commit()
    market_db.close()
    oracle_db.close()
    print(f"Initialized market DB from {len(rows)} oracle snapshots")


if __name__ == "__main__":
    init_db()
    init_from_oracle()
    print("Market DB initialized")


def fetch_binance_context() -> dict:
    """Fetch BTC/ETH/TAO 5m context from Binance.

    Context features (not investment targets):
    - BTC return (1h, 4h, 24h)
    - ETH return (1h, 4h, 24h)
    - TAO return (1h, 4h, 24h)
    - Volume changes
    - Regime detection (bull/bear/sideways)
    """
    pairs = {"BTCUSDT": "btc", "ETHUSDT": "eth", "TAOUSDT": "tao"}
    context = {}

    for pair, label in pairs.items():
        try:
            conn = http.client.HTTPSConnection("api.binance.com", ctx=CTX, timeout=10)
            conn.request("GET", f"/api/v3/klines?symbol={pair}&interval=5m&limit=288")  # 24h of 5m data
            resp = conn.getresponse()
            data = json.loads(resp.read().decode())
            conn.close()

            if data and len(data) >= 2:
                closes = [float(k[4]) for k in data]

                # Calculate returns
                ret_1h = (closes[-1] - closes[-12]) / closes[-12] if len(closes) >= 12 else 0
                ret_4h = (closes[-1] - closes[-48]) / closes[-48] if len(closes) >= 48 else 0
                ret_24h = (closes[-1] - closes[0]) / closes[0] if closes[0] > 0 else 0

                context[label] = {
                    "price": closes[-1],
                    "ret_1h": ret_1h,
                    "ret_4h": ret_4h,
                    "ret_24h": ret_24h,
                }
        except Exception as e:
            context[label] = {"error": str(e)}

    return context


def detect_regime(context: dict) -> str:
    """Detect market regime from BTC/ETH/TAO context.

    Returns: bull, bear, sideways, mixed
    """
    btc_ret = context.get("btc", {}).get("ret_24h", 0)
    eth_ret = context.get("eth", {}).get("ret_24h", 0)
    tao_ret = context.get("tao", {}).get("ret_24h", 0)

    # Simple regime detection
    if btc_ret > 0.03 and eth_ret > 0.03 and tao_ret > 0.03:
        return "bull"
    elif btc_ret < -0.03 and eth_ret < -0.03 and tao_ret < -0.03:
        return "bear"
    elif abs(btc_ret) < 0.01 and abs(eth_ret) < 0.01:
        return "sideways"
    else:
        return "mixed"


def store_context(context: dict, timestamp: str):
    """Store context in market DB."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO macro_5m (timestamp, btc_usd, eth_usd, tao_usd) "
        "VALUES (?, ?, ?, ?)",
        (timestamp,
         context.get("btc", {}).get("price", 0),
         context.get("eth", {}).get("price", 0),
         context.get("tao", {}).get("price", 0))
    )
    conn.commit()
    conn.close()
