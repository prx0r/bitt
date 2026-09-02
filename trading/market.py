"""MarketFrame — canonical historical data store for Bittensor.

Schema per BUILD-PLAN-CP0:
  subnet_candles: timestamp, block, netuid, open_tao, high_tao, low_tao, close_tao, volume_tao
  pool_state:     timestamp, block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity
  subnet_state:   timestamp, block, netuid, emission, registration_cost, miners, validators, stake, owner
  macro:          timestamp, btc_usd, eth_usd, tao_usd

Data sources:
  - TAOStats API: historical subnet OHLCV + pool state + subnet state
  - Binance: BTC/ETH/TAO context candles
  - Bittensor archive RPC: specific historical chain state (verification)

Stores in market.duckdb (analytical store, not Hydra).
"""
import sqlite3
import json
import http.client
import ssl
from pathlib import Path


DB_PATH = Path("/root/bitt/market.duckdb")
CTX = ssl.create_default_context()


def init_db():
    """Initialize market database with correct schema."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS subnet_candles (
            timestamp TEXT NOT NULL,
            block INTEGER,
            netuid INTEGER NOT NULL,
            open_tao REAL,
            high_tao REAL,
            low_tao REAL,
            close_tao REAL,
            volume_tao REAL,
            PRIMARY KEY (timestamp, netuid)
        );

        CREATE TABLE IF NOT EXISTS pool_state (
            timestamp TEXT NOT NULL,
            block INTEGER,
            netuid INTEGER NOT NULL,
            tao_reserve REAL,
            alpha_reserve REAL,
            alpha_price REAL,
            liquidity REAL,
            PRIMARY KEY (timestamp, netuid)
        );

        CREATE TABLE IF NOT EXISTS subnet_state (
            timestamp TEXT NOT NULL,
            block INTEGER,
            netuid INTEGER NOT NULL,
            emission REAL,
            registration_cost REAL,
            miners INTEGER,
            validators INTEGER,
            stake REAL,
            owner TEXT,
            PRIMARY KEY (timestamp, netuid)
        );

        CREATE TABLE IF NOT EXISTS macro (
            timestamp TEXT NOT NULL PRIMARY KEY,
            btc_usd REAL,
            eth_usd REAL,
            tao_usd REAL
        );

        CREATE INDEX IF NOT EXISTS idx_candles_netuid ON subnet_candles(netuid);
        CREATE INDEX IF NOT EXISTS idx_candles_ts ON subnet_candles(timestamp);
        CREATE INDEX IF NOT EXISTS idx_pool_netuid ON pool_state(netuid);
        CREATE INDEX IF NOT EXISTS idx_substate_netuid ON subnet_state(netuid);
    """)
    conn.commit()
    conn.close()


def store_subnet_candle(timestamp: str, block: int, netuid: int,
                         open_tao: float, high_tao: float, low_tao: float,
                         close_tao: float, volume_tao: float = 0):
    """Store one subnet candle."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO subnet_candles "
        "(timestamp, block, netuid, open_tao, high_tao, low_tao, close_tao, volume_tao) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, block, netuid, open_tao, high_tao, low_tao, close_tao, volume_tao)
    )
    conn.commit()
    conn.close()


def store_pool_state(timestamp: str, block: int, netuid: int,
                      tao_reserve: float, alpha_reserve: float,
                      alpha_price: float, liquidity: float = 0):
    """Store pool state snapshot."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO pool_state "
        "(timestamp, block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (timestamp, block, netuid, tao_reserve, alpha_reserve, alpha_price, liquidity)
    )
    conn.commit()
    conn.close()


def store_subnet_state(timestamp: str, block: int, netuid: int,
                        emission: float, registration_cost: float,
                        miners: int, validators: int, stake: float,
                        owner: str = ""):
    """Store subnet state snapshot."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO subnet_state "
        "(timestamp, block, netuid, emission, registration_cost, miners, validators, stake, owner) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, block, netuid, emission, registration_cost, miners, validators, stake, owner)
    )
    conn.commit()
    conn.close()


def store_macro_candle(timestamp: str, btc_usd: float, eth_usd: float, tao_usd: float):
    """Store macro candle."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO macro (timestamp, btc_usd, eth_usd, tao_usd) "
        "VALUES (?, ?, ?, ?)",
        (timestamp, btc_usd, eth_usd, tao_usd)
    )
    conn.commit()
    conn.close()


def get_subnet_candles(netuid: int, limit: int = 1000) -> list[dict]:
    """Get candles for a subnet, newest first."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM subnet_candles WHERE netuid = ? ORDER BY timestamp DESC LIMIT ?",
        (netuid, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pool_states(netuid: int, limit: int = 1000) -> list[dict]:
    """Get pool states for a subnet, newest first."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM pool_state WHERE netuid = ? ORDER BY timestamp DESC LIMIT ?",
        (netuid, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_latest_prices() -> dict[int, float]:
    """Get latest alpha price for each subnet."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT netuid, alpha_price FROM pool_state "
        "WHERE timestamp = (SELECT MAX(timestamp) FROM pool_state) "
        "OR timestamp IN (SELECT MAX(timestamp) FROM pool_state GROUP BY netuid)"
    ).fetchall()
    conn.close()
    return {r['netuid']: r['alpha_price'] for r in rows if r['alpha_price']}


def get_market_frame(timestamp: str) -> dict:
    """Get all data for a specific timestamp (5m bucket)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Get subnet candles at this timestamp
    sub_rows = conn.execute(
        "SELECT netuid, close_tao FROM subnet_candles WHERE timestamp = ?",
        (timestamp,)
    ).fetchall()
    subs = {r['netuid']: r['close_tao'] for r in sub_rows}

    # Get pool states at this timestamp
    pool_rows = conn.execute(
        "SELECT netuid, alpha_price, tao_reserve, alpha_reserve FROM pool_state WHERE timestamp = ?",
        (timestamp,)
    ).fetchall()
    pools = {r['netuid']: {
        'alpha_price': r['alpha_price'],
        'tao_reserve': r['tao_reserve'],
        'alpha_reserve': r['alpha_reserve'],
    } for r in pool_rows}

    # Get macro
    macro_row = conn.execute(
        "SELECT * FROM macro WHERE timestamp = ?",
        (timestamp,)
    ).fetchone()
    macro = dict(macro_row) if macro_row else {}

    conn.close()

    return {
        "timestamp": timestamp,
        "subnets": subs,
        "pools": pools,
        "macro": macro,
    }


def fetch_binance_context() -> dict:
    """Fetch BTC/ETH/TAO 5m context from Binance."""
    pairs = {"BTCUSDT": "btc", "ETHUSDT": "eth", "TAOUSDT": "tao"}
    context = {}

    for pair, label in pairs.items():
        try:
            conn = http.client.HTTPSConnection("api.binance.com", ctx=CTX, timeout=10)
            conn.request("GET", f"/api/v3/klines?symbol={pair}&interval=5m&limit=288")
            resp = conn.getresponse()
            data = json.loads(resp.read().decode())
            conn.close()

            if data and len(data) >= 2:
                closes = [float(k[4]) for k in data]
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


def store_context(context: dict, timestamp: str):
    """Store macro context in market DB."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT OR REPLACE INTO macro (timestamp, btc_usd, eth_usd, tao_usd) "
        "VALUES (?, ?, ?, ?)",
        (timestamp,
         context.get("btc", {}).get("price", 0),
         context.get("eth", {}).get("price", 0),
         context.get("tao", {}).get("price", 0))
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Market DB initialized with correct schema")
    print("Tables: subnet_candles, pool_state, subnet_state, macro")
