import time
import yfinance as yf
import requests
import logging
import pandas as pd
from datetime import datetime
import ssl
import certifi
import os
import pytz
from keep_alive import keep_alive

# Keep Alive (for Replit or VPS)
keep_alive()

# SSL Certificates
os.environ['SSL_CERT_FILE'] = certifi.where()

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
TELEGRAM_GROUP_CHAT_ID = "@SwingTreadingSmartbot"

# Stock List
INDIAN_STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
    "KOTAKBANK.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS", "ASIANPAINT.NS",
    "HCLTECH.NS", "AXISBANK.NS", "ITC.NS", "MARUTI.NS", "WIPRO.NS", "SUNPHARMA.NS",
    "POWERGRID.NS", "TITAN.NS", "TATAMOTORS.NS", "ONGC.NS", "NTPC.NS", "ULTRACEMCO.NS",
    "BAJAJFINSV.NS", "TECHM.NS", "HDFC.NS", "NESTLEIND.NS", "TATASTEEL.NS", "JSWSTEEL.NS",
    "DIVISLAB.NS", "HDFCLIFE.NS", "GRASIM.NS", "DRREDDY.NS", "ADANIPORTS.NS", "EICHERMOT.NS",
    "CIPLA.NS", "BPCL.NS", "BRITANNIA.NS", "SHREECEM.NS", "HINDALCO.NS", "COALINDIA.NS",
    "HEROMOTOCO.NS", "UPL.NS", "SBILIFE.NS", "INDUSINDBK.NS", "TATACONSUM.NS", "BAJAJ-AUTO.NS",
    "APOLLOHOSP.NS", "M&M.NS"]

ALL_SYMBOLS = INDIAN_STOCKS 

# Timeframes
TIMEFRAMES = {"Position": "1d"}  # Only 1d timeframe now

# Active Trades
active_trades = {}

# Logging
logging.basicConfig(filename="trade_bot.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Telegram Message Sender
def send_telegram(message, chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

# Fetch Data
def fetch_ohlcv(symbol, timeframe):
    try:
        interval_map = {"1d": "1d"}  # Only using 1-day interval now
        df = yf.download(tickers=symbol, period="365d", interval=interval_map[timeframe])
        df.reset_index(inplace=True)
        if df.empty:
            logging.error(f"No data fetched for {symbol}")
            return None
        return df
    except Exception as e:
        logging.error(f"Data Fetch Error ({symbol}): {e}")
        return None

# Calculate EMA
def calculate_ema(df, period):
    return df['Close'].ewm(span=period, adjust=False).mean()

# Detect Trend based on EMA 50/200
def detect_trend(df):
    if df is None or df.empty:
        return "NO_TREND"
    df['ema_50'] = calculate_ema(df, 50)
    df['ema_200'] = calculate_ema(df, 200)
    
    if df['ema_50'].iloc[-1] > df['ema_200'].iloc[-1]:
        return "UP"
    elif df['ema_50'].iloc[-1] < df['ema_200'].iloc[-1]:
        return "DOWN"
    else:
        return "NO_TREND"

# Detect Liquidity Grab 
def detect_liquidity_grab(df):
    if df is None or df.empty:
        return "NO_SIGNAL"
    
    df['high_shift1'] = df['High'].shift(1)
    df['low_shift1'] = df['Low'].shift(1)
    
    latest_high = df['High'].iloc[-1]
    latest_low = df['Low'].iloc[-1]
    
    previous_highs = df['high_shift1'].dropna()
    previous_lows = df['low_shift1'].dropna()
    
    grab_high = latest_high > previous_highs.max()
    grab_low = latest_low < previous_lows.min()

    if grab_high.any():
        return "SELL"
    elif grab_low.any():
        return "BUY"
    else:
        return "NO_SIGNAL"

# Detect Order Block
def detect_order_block(df):
    if df is None or df.empty:
        return "NO_SIGNAL"
    
    last_candle = df.iloc[-1]
    second_last_candle = df.iloc[-2]
    
    if last_candle['Close'].item() > last_candle['Open'].item() and second_last_candle['Close'].item() < second_last_candle['Open'].item():
        return "BUY"
    elif last_candle['Close'].item() < last_candle['Open'].item() and second_last_candle['Close'].item() > second_last_candle['Open'].item():
        return "SELL"
    else:
        return "NO_SIGNAL"

# Final Signal Combining everything
def final_signal(daily_df):
    trend = detect_trend(daily_df)
    liquidity_signal = detect_liquidity_grab(daily_df)
    order_block_signal = detect_order_block(daily_df)

    # BUY Setup
    if liquidity_signal == "BUY" and order_block_signal == "BULLISH_OB" and trend == "UP":
        return "BUY"

    # SELL Setup
    elif liquidity_signal == "SELL" and order_block_signal == "BEARISH_OB" and trend == "DOWN":
        return "SELL"
    
    else:
        return "NO_SIGNAL"

# Check TP/SL
def check_tp_sl(symbol, entry_price, direction, yf):
    live_price = yf.download(symbol, period="1d", interval="5m", progress=False)['Close'].iloc[-1]
    
    if direction == "BUY":
        tp = entry_price * 1.01
        sl = entry_price * 0.99
        if live_price >= tp:
            return "TP Hit ✅"
        elif live_price <= sl:
            return "SL Hit ❌"
    elif direction == "SELL":
        tp = entry_price * 0.99
        sl = entry_price * 1.01
        if live_price <= tp:
            return "TP Hit ✅"
        elif live_price >= sl:
            return "SL Hit ❌"
    return "Running..."

# Main Bot Loop
def run_bot():
    last_signal_time = time.time()
    while True:
        signal_found = False

        for symbol in ALL_SYMBOLS:
            # Check Existing Trade
            if symbol in active_trades:
                df = fetch_ohlcv(symbol, "1d")  # Fetch 1d data for ongoing trade check
                if df is not None and not df.empty:
                    last_price = df['Close'].iloc[-1]
                    trade = active_trades[symbol]
                    now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M')

                    if trade['direction'] == "BUY" and (last_price >= trade['tp'] or last_price <= trade['sl']):
                        result = "TP HIT" if last_price >= trade['tp'] else "SL HIT"
                        emoji = "✅" if last_price >= trade['tp'] else "🛑"
                        send_telegram(f"{emoji} *{result} for {symbol}*\nTime: `{now}`\nPrice: `{last_price}`", TELEGRAM_GROUP_CHAT_ID)
                        del active_trades[symbol]

                    elif trade['direction'] == "SELL" and (last_price <= trade['tp'] or last_price >= trade['sl']):
                        result = "TP HIT" if last_price <= trade['tp'] else "SL HIT"
                        emoji = "✅" if last_price <= trade['tp'] else "🛑"
                        send_telegram(f"{emoji} *{result} for {symbol}*\nTime: `{now}`\nPrice: `{last_price}`", TELEGRAM_GROUP_CHAT_ID)
                        del active_trades[symbol]
                continue

            # New Trade Check
            daily_df = fetch_ohlcv(symbol, "1d")

            if daily_df is not None:
                signal = final_signal(daily_df)
                if signal != "NO_SIGNAL":
                    entry_price = daily_df['Close'].iloc[-1]
                    tp_sl_status = check_tp_sl(symbol, entry_price, signal, yf)

                    now = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')
                    msg = (
                        f"📈 *{signal} Signal for {symbol}*\n"
                        f"🕰️ Time: `{now}`\n"
                        f"💰 Entry: `{entry_price}`\n"
                        f"🎯 Status: {tp_sl_status}"
                    )
                    send_telegram(msg, TELEGRAM_GROUP_CHAT_ID)
                    active_trades[symbol] = {"entry": entry_price, "sl": entry_price * 0.98, "tp": entry_price * 1.02, "direction": signal}
                    signal_found = True

        # No Signal Alert
        if not signal_found and (time.time() - last_signal_time > 3600):
            send_telegram("⚠️ No Signal in the Last 1 Hour", TELEGRAM_GROUP_CHAT_ID)
           
