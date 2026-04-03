import os
import time import math from datetime import datetime, timezone import pytz import pandas as pd from pybit.unified_trading import HTTP

================= CONFIG =================

API_KEY = os.getenv("BYBIT_API_KEY") API_SECRET = os.getenv("BYBIT_API_SECRET")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"] TIMEFRAME = "15" LEVERAGE = 50 BASE_RISK_MIN = 0.05 BASE_RISK_MAX = 0.15 MAX_DAILY_DD = 0.40 EMA_PERIOD = 50

Sessions (WAT -> UTC conversion)

London: 7:00–10:00 UTC

New York: 13:00–16:00 UTC

def is_session_active(): now = datetime.now(timezone.utc) hour = now.hour return (7 <= hour < 10) or (13 <= hour < 16)

================= INIT =================

client = HTTP(api_key=API_KEY, api_secret=API_SECRET)

daily_start_balance = None

================= INDICATORS =================

def get_klines(symbol): data = client.get_kline(symbol=symbol, interval=TIMEFRAME, limit=100) df = pd.DataFrame(data['result']['list']) df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'] df = df.astype(float) return df[::-1]

def calculate_ema(df): return df['close'].ewm(span=EMA_PERIOD).mean()

def vwap(df): return (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()

================= STRUCTURE =================

def find_ib(df): first_3 = df.head(3) ib_high = first_3['high'].max() ib_low = first_3['low'].min() return ib_high, ib_low

================= RETEST LOGIC =================

def valid_retest(df, level, direction): last = df.iloc[-1] prev = df.iloc[-2]

# Touch level
touched = (last['low'] <= level <= last['high'])

# Candle rejection
if direction == "long":
    bullish_close = last['close'] > last['open']
    rejection = last['close'] > level
    structure_break = last['close'] > prev['high']
    return touched and bullish_close and rejection and structure_break

if direction == "short":
    bearish_close = last['close'] < last['open']
    rejection = last['close'] < level
    structure_break = last['close'] < prev['low']
    return touched and bearish_close and rejection and structure_break

return False

================= POSITION SIZING =================

def adaptive_risk(volatility): # Normalize volatility into risk range risk = BASE_RISK_MIN + (volatility * (BASE_RISK_MAX - BASE_RISK_MIN)) return max(BASE_RISK_MIN, min(BASE_RISK_MAX, risk))

================= TRADE EXECUTION =================

def place_trade(symbol, side, balance): df = get_klines(symbol)

ema = calculate_ema(df)
df['ema'] = ema
df['vwap'] = vwap(df)

ib_high, ib_low = find_ib(df)

last_close = df.iloc[-1]['close']
last_ema = df.iloc[-1]['ema']
last_vwap = df.iloc[-1]['vwap']

# Trend filter
if side == "long" and last_close < last_ema:
    return
if side == "short" and last_close > last_ema:
    return

# Volatility proxy
volatility = abs(df['close'].pct_change().iloc[-10:].mean()) * 100
risk_pct = adaptive_risk(volatility)

# Retest logic
if side == "long" and valid_retest(df, ib_high, "long"):
    entry = last_close
    sl = ib_low
    tp = entry + (entry - sl) * 2

elif side == "short" and valid_retest(df, ib_low, "short"):
    entry = last_close
    sl = ib_high
    tp = entry - (sl - entry) * 2

else:
    return

risk_amount = balance * risk_pct
qty = risk_amount / abs(entry - sl)

try:
    client.place_order(
        symbol=symbol,
        side="Buy" if side == "long" else "Sell",
        orderType="Market",
        qty=round(qty, 3),
        takeProfit=tp,
        stopLoss=sl,
        leverage=LEVERAGE
    )
    print(f"Trade executed: {symbol} {side}")
except Exception as e:
    print(f"Error placing order: {e}")

================= DAILY DD CHECK =================

def check_drawdown(balance, initial_balance): dd = (initial_balance - balance) / initial_balance return dd >= MAX_DAILY_DD

================= MAIN LOOP =================

def run_bot(): global daily_start_balance

account = client.get_wallet_balance(accountType="UNIFIED")
balance = float(account['result']['list'][0]['totalEquity'])

if daily_start_balance is None:
    daily_start_balance = balance

if check_drawdown(balance, daily_start_balance):
    print("Daily drawdown hit. Stopping trading.")
    return

if not is_session_active():
    print("Outside trading session.")
    return

for symbol in SYMBOLS:
    place_trade(symbol, "long", balance)
    place_trade(symbol, "short", balance)

================= ENTRY =================

if name == "main": while True: run_bot() time.sleep(60)