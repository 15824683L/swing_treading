from flask import Flask
import pandas as pd
import numpy as np
import yfinance as yf
import time
import pytz
import requests
from datetime import datetime
if __name__ == "__main__":
    keep_alive()
    # তারপর আপনার মেইন ফাংশন রান করান
    main()

# ========== SETTINGS ==========
nifty_50_stocks = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "HINDUNILVR.NS",
    "KOTAKBANK.NS", "LT.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS", "ASIANPAINT.NS",
    "HCLTECH.NS", "AXISBANK.NS", "ITC.NS", "MARUTI.NS", "WIPRO.NS", "SUNPHARMA.NS",
    "POWERGRID.NS", "TITAN.NS", "TATAMOTORS.NS", "ONGC.NS", "NTPC.NS", "ULTRACEMCO.NS",
    "BAJAJFINSV.NS", "TECHM.NS", "HDFC.NS", "NESTLEIND.NS", "TATASTEEL.NS", "JSWSTEEL.NS",
    "DIVISLAB.NS", "HDFCLIFE.NS", "GRASIM.NS", "DRREDDY.NS", "ADANIPORTS.NS", "EICHERMOT.NS",
    "CIPLA.NS", "BPCL.NS", "BRITANNIA.NS", "SHREECEM.NS", "HINDALCO.NS", "COALINDIA.NS",
    "HEROMOTOCO.NS", "UPL.NS", "SBILIFE.NS", "INDUSINDBK.NS", "TATACONSUM.NS", "BAJAJ-AUTO.NS",
    "APOLLOHOSP.NS", "M&M.NS"
]

telegram_bot_token = "8100205821:AAE0sGJhnA8ySkuSusEXSf9bYU5OU6sFzVg"
telegram_chat_id = "8191014589"

# ========== FUNCTION PART ==========

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def calculate_ema(df, period):
    return df['Close'].ewm(span=period, adjust=False).mean()

def detect_trend(df):
    df['ema_50'] = calculate_ema(df, 50)
    df['ema_200'] = calculate_ema(df, 200)
    
    if df['ema_50'].iloc[-1] > df['ema_200'].iloc[-1]:
        return "UP"
    elif df['ema_50'].iloc[-1] < df['ema_200'].iloc[-1]:
        return "DOWN"
    else:
        return "NO_TREND"

def detect_liquidity_grab(df):
    df['high_shift1'] = df['High'].shift(1)
    df['low_shift1'] = df['Low'].shift(1)
    
    latest_high = df['High'].iloc[-1]
    latest_low = df['Low'].iloc[-1]
    
    grab_high = latest_high > df['high_shift1'].max()
    grab_low = latest_low < df['low_shift1'].min()
    
    if grab_high:
        return "SELL"
    elif grab_low:
        return "BUY"
    else:
        return "NO_SIGNAL"

def final_signal(daily_df, h4_df):
    trend = detect_trend(daily_df)
    signal = detect_liquidity_grab(h4_df)
    
    if signal == "BUY" and trend == "UP":
        return "BUY"
    elif signal == "SELL" and trend == "DOWN":
        return "SELL"
    else:
        return "NO"

def check_tp_sl(symbol, entry_price, direction):
    live_price = yf.download(symbol, period="1d", interval="5m", progress=False)['Close'].iloc[-1]
    
    if direction == "BUY":
        tp = entry_price * 1.01  # +1%
        sl = entry_price * 0.99  # -1%
        if live_price >= tp:
            return "TP Hit ✅"
        elif live_price <= sl:
            return "SL Hit ❌"
    elif direction == "SELL":
        tp = entry_price * 0.99  # -1%
        sl = entry_price * 1.01  # +1%
        if live_price <= tp:
            return "TP Hit ✅"
        elif live_price >= sl:
            return "SL Hit ❌"
    return "Running..."

def fetch_data(symbol, timeframe, lookback_days):
    interval = '1d' if timeframe == '1d' else '4h'
    df = yf.download(symbol, period=f"{lookback_days}d", interval=interval, progress=False)
    return df

# ========== MAIN EXECUTION ==========

for symbol in nifty_50_stocks:
    try:
        print(f"Scanning {symbol}...")

        # Fetch Daily and 4H Data
        daily_df = fetch_data(symbol, '1d', 365)
        h4_df = fetch_data(symbol, '4h', 30)

        if len(daily_df) < 200 or len(h4_df) < 50:
            print(f"Not enough data for {symbol}")
            continue

        # Get Final Signal
        signal = final_signal(daily_df, h4_df)
        
        # Get Kolkata Time
        india_timezone = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(india_timezone).strftime("%Y-%m-%d %H:%M:%S")

        if signal == "BUY" or signal == "SELL":
            entry_price = h4_df['Close'].iloc[-1]
            tp_sl_status = check_tp_sl(symbol, entry_price, signal)

            message = f"🕰️ *Time:* {current_time}\n📈 *Stock:* {symbol}\n🔔 *Signal:* {signal}\n💰 *Entry Price:* {entry_price:.2f}\n🎯 *Status:* {tp_sl_status}"
            print(message)
            send_telegram_message(message)

        else:
            print(f"No signal for {symbol} at {current_time}")
        
        time.sleep(600)  # Sleep for 10 minutes after each stock

    except Exception as e:
        print(f"Error with {symbol}: {e}")

