Bybit Futures Intraday Bot (PRO VERSION)

Strategy: IB Breakout + VWAP Retest + Volume Spike + EMA Filter + TP/SL

import os 
import pandas as pd 
from datetime import datetime, timedelta from pybit.unified_trading import HTTP

API_KEY = os.getenv("BYBIT_API_KEY") API_SECRET = os.getenv("BYBIT_API_SECRET")

session = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)

PAIRS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT"] TIMEFRAME = "5" RISK_PER_TRADE = 0.03  # safer LEVERAGE = 50 DAILY_DD_LIMIT = 0.4 MAX_CONCURRENT_TRADES = 2

start_balance = None trading_enabled = True open_trades = 0

-----------------------------

Helpers

-----------------------------

def get_balance(): bal = session.get_wallet_balance(accountType="UNIFIED") return float(bal["result"]["list"][0]["totalEquity"])

def get_klines(symbol, limit=200): data = session.get_kline(category="linear", symbol=symbol, interval=TIMEFRAME, limit=limit) df = pd.DataFrame(data["result"]["list"], columns=["time","open","high","low","close","volume","turnover"]) df = df.astype(float).sort_values("time") return df

def calculate_indicators(df): df["cum_vol"] = df["volume"].cumsum() df["cum_vol_price"] = (df["close"] * df["volume"]).cumsum() df["vwap"] = df["cum_vol_price"] / df["cum_vol"] df["ema50"] = df["close"].ewm(span=50).mean() return df

def volume_spike(df): avg_vol = df["volume"].rolling(20).mean().iloc[-1] return df["volume"].iloc[-1] > 1.5 * avg_vol

def get_ib_levels(df): now = datetime.utcnow() session_start = now.replace(hour=8, minute=0, second=0, microsecond=0) ib_end = session_start + timedelta(hours=1) ib_df = df[(df["time"] >= session_start.timestamp()*1000) & (df["time"] <= ib_end.timestamp()*1000)] if len(ib_df) == 0: return None, None return ib_df["high"].max(), ib_df["low"].min()

-----------------------------

Strategy Logic

-----------------------------

def check_trade(symbol): df = get_klines(symbol) df = calculate_indicators(df)

ib_high, ib_low = get_ib_levels(df)
if not ib_high:
    return None

price = df["close"].iloc[-1]
vwap = df["vwap"].iloc[-1]
ema = df["ema50"].iloc[-1]

# BUY
if price > ib_high and price > ema:
    if abs(price - vwap)/vwap < 0.002 and volume_spike(df):
        return "Buy"

# SELL
if price < ib_low and price < ema:
    if abs(price - vwap)/vwap < 0.002 and volume_spike(df):
        return "Sell"

return None

-----------------------------

Risk + TP/SL

-----------------------------

def calc_position_size(balance, price): risk_amount = balance * RISK_PER_TRADE return round((risk_amount * LEVERAGE) / price, 3)

def place_trade(symbol, side, qty, price): if side == "Buy": sl = price * 0.995 tp = price * 1.02 else: sl = price * 1.005 tp = price * 0.98

session.place_order(
    category="linear",
    symbol=symbol,
    side=side,
    orderType="Market",
    qty=qty,
    takeProfit=tp,
    stopLoss=sl,
    timeInForce="GoodTillCancel"
)

-----------------------------

Main

-----------------------------

def run_bot(): global start_balance, trading_enabled, open_trades

if start_balance is None:
    start_balance = get_balance()

balance = get_balance()

if balance <= start_balance * (1 - DAILY_DD_LIMIT):
    trading_enabled = False
    return

if not trading_enabled or open_trades >= MAX_CONCURRENT_TRADES:
    return

for pair in PAIRS:
    signal = check_trade(pair)
    if signal:
        price = get_klines(pair)["close"].iloc[-1]
        qty = calc_position_size(balance, price)
        place_trade(pair, signal, qty, price)
        open_trades += 1

if name == "main": run_bot()