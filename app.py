import os
import logging
import warnings
from datetime import timedelta

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore')

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
logging.getLogger('tensorflow').setLevel(logging.ERROR)

import numpy as np
import pandas as pd
import tensorflow as tf
import yfinance as yf 
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from sklearn.preprocessing import MinMaxScaler

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, 'data')

app.logger.disabled = True
log = logging.getLogger('werkzeug')
log.disabled = True

def parse_custom_csv(filepath):
    try:
        df = pd.read_csv(filepath, quotechar='"', thousands=',')
        df.columns = df.columns.str.strip()
        if 'Date' not in df.columns or 'Price' not in df.columns: return None
        df['Date'] = pd.to_datetime(df['Date']).dt.normalize()
        if df['Price'].dtype == object:
             df['Price'] = df['Price'].astype(str).str.replace(',', '').astype(float)
        df = df.sort_values('Date', ascending=True)
        return df
    except Exception: return None

def fetch_missing_data(symbol, start_date):
    try:
        ticker_symbol = symbol.replace('_', '') + "=X"
        start_fetch = start_date + timedelta(days=1)
        df_yahoo = yf.download(ticker_symbol, start=start_fetch, progress=False, auto_adjust=True)
        if df_yahoo.empty: return pd.DataFrame()
        df_yahoo = df_yahoo.reset_index()
        df_clean = pd.DataFrame()
        df_clean['Date'] = df_yahoo['Date'].dt.normalize()
        if 'Close' in df_yahoo.columns: df_clean['Price'] = df_yahoo['Close']
        else: df_clean['Price'] = df_yahoo.iloc[:, 1]
        return df_clean
    except Exception: return pd.DataFrame()

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/pairs', methods=['GET'])
def get_pairs():
    if not os.path.exists(DATA_FOLDER): return jsonify([])
    files = [f.replace('.csv', '') for f in os.listdir(DATA_FOLDER) if f.endswith('.csv')]
    return jsonify(files)

@app.route('/api/live', methods=['POST'])
def get_live_price():
    try:
        req_data = request.get_json()
        pair = req_data.get('pair')
        ticker_symbol = pair.replace('_', '') + "=X"
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="1d", interval="1m")
        if data.empty: data = ticker.history(period="1d")
        if data.empty: return jsonify({"error": "Unavailable"}), 404
        current_price = data['Close'].iloc[-1]
        return jsonify({"pair": pair, "rate": float(current_price), "source": "Yahoo"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_pair():
    req_data = request.get_json()
    pair = req_data.get('pair')
    
    filepath = os.path.join(DATA_FOLDER, f"{pair}.csv")
    if not os.path.exists(filepath): return jsonify({"error": "File not found"}), 404

    df_csv = parse_custom_csv(filepath)
    if df_csv is None: return jsonify({"error": "Failed to parse CSV"}), 500

    last_csv_date = df_csv['Date'].max()
    df_api = fetch_missing_data(pair, last_csv_date)
    
    if not df_api.empty:
        df_combined = pd.concat([df_csv, df_api]).drop_duplicates(subset='Date').sort_values('Date')
    else:
        df_combined = df_csv

    df_combined['SMA_50'] = df_combined['Price'].rolling(window=50).mean()
    df_combined['SMA_200'] = df_combined['Price'].rolling(window=200).mean()

    ma_signal = "NEUTRAL"
    if len(df_combined) > 200:
        last_50 = df_combined['SMA_50'].iloc[-1]
        last_200 = df_combined['SMA_200'].iloc[-1]
        
        if last_50 > last_200:
            ma_signal = "BUY (Golden Cross)"
        else:
            ma_signal = "SELL (Death Cross)"

    history_data = []
    for _, row in df_combined.iterrows():
        history_data.append({
            "x": row['Date'].strftime('%Y-%m-%d'),
            "y": row['Price'],
            "sma50": None if pd.isna(row['SMA_50']) else row['SMA_50'],
            "sma200": None if pd.isna(row['SMA_200']) else row['SMA_200']
        })

    prices = df_combined['Price'].values.reshape(-1, 1)
    scaler = MinMaxScaler(feature_range=(0, 1))
    prices_scaled = scaler.fit_transform(prices)

    X = np.arange(len(prices_scaled)).reshape(-1, 1)
    y = prices_scaled

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(1,)), 
        tf.keras.layers.Dense(64, activation='relu'),
        tf.keras.layers.Dense(32, activation='relu'),
        tf.keras.layers.Dense(1)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X, y, epochs=10, verbose=0)

    future_days = 7
    future_predictions = []
    last_index = len(prices_scaled)
    future_inputs = np.arange(last_index, last_index + future_days).reshape(-1, 1)
    preds_scaled = model.predict(future_inputs, verbose=0)
    preds_actual = scaler.inverse_transform(preds_scaled)

    last_date = df_combined['Date'].max()
    for i in range(future_days):
        next_date = last_date + timedelta(days=i+1)
        future_predictions.append({
            "date": next_date.strftime('%Y-%m-%d'),
            "price": float(preds_actual[i][0])
        })

    latest_price = prices[-1][0]
    reference_price = float(prices[-2][0]) if len(prices) > 1 else float(latest_price)
    next_day_price = future_predictions[0]['price']
    
    ml_trend = "UP" if next_day_price > latest_price else "DOWN"

    tf.keras.backend.clear_session()

    return jsonify({
        "pair": pair,
        "current_price": reference_price,
        "predicted_price": next_day_price,
        "trend": ml_trend,
        "ma_signal": ma_signal,
        "history": history_data,
        "future_forecast": future_predictions
    })

if __name__ == '__main__':
    print(f"\n{'='*40}")
    print(f" AlphaFxTrader Hybrid Engine Running")
    print(f" URL: http://127.0.0.1:5000")
    print(f" Mode: Hybrid (ML Regression + SMA Crossover)")
    print(f"{'='*40}\n")
    app.run(debug=True, port=5000, use_reloader=False)