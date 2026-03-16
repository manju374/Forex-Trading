import os
import logging
import warnings
import time  # <--- ADD THIS LINE HERE
import random
import threading # <--- Make sure this is here too
from datetime import timedelta, datetime
import psycopg2 
from psycopg2.extras import RealDictCursor
import pytz
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import tensorflow as tf
import yfinance as yf 
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from sklearn.preprocessing import MinMaxScaler
import os
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()

import os
from dotenv import load_dotenv
# (Keep your other imports like Flask, psycopg2, CORS up here)

# 1. Load the environment variables from the .env file
load_dotenv()

app = Flask(__name__)

# 2. Securely fetch the secret key from .env
app.secret_key = os.getenv("SECRET_KEY") 
CORS(app)

# 3. Securely fetch database credentials from .env
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME") 
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except Exception as e:
        print(f"Database Connection Error: {e}")
        return None
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, 'data')

# --- HELPERS ---
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

def get_ist_intraday(symbol):
    try:
        ticker = symbol.replace('_', '') + "=X"
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if df.empty: return []

        df = df.reset_index()
        date_col = 'Datetime' if 'Datetime' in df.columns else 'index'
        if date_col not in df.columns: date_col = df.columns[0]
        price_col = 'Close' if 'Close' in df.columns else df.columns[1]

        ist = pytz.timezone('Asia/Kolkata')
        if df[date_col].dt.tz is None:
            df[date_col] = df[date_col].dt.tz_localize('UTC').dt.tz_convert(ist)
        else:
            df[date_col] = df[date_col].dt.tz_convert(ist)

        data = [{"x": row[date_col].strftime('%Y-%m-%d %H:%M:%S'), "y": float(row[price_col])} for _, row in df.iterrows()]
        return data
    except Exception as e:
        print(f"Intraday Error: {e}")
        return []

# ==========================================
#             ROUTES
# ==========================================

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html', user_name=session.get('user_name'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO users (full_name, email, password_hash, balance) VALUES (%s, %s, %s, 10000.00)",
                    (name, email, hashed_pw)
                )
                conn.commit()
                cur.close()
                conn.close()
                return redirect(url_for('login'))
            except psycopg2.Error as e:
                conn.rollback()
                return render_template('register.html', error="Email already exists")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['full_name']
                return redirect(url_for('index'))
            else:
                return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- TRADING & WALLET ---

@app.route('/api/wallet')
def get_wallet():
    if 'user_id' not in session: return jsonify({}), 401
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT balance FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    bal = float(user['balance']) if user else 0.0
    return jsonify({"balance": bal})

@app.route('/api/trade', methods=['POST'])
def execute_trade():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    pair = data.get('pair')
    action = data.get('action') 
    
    try: amount_usd = float(data.get('amount'))
    except: return jsonify({"error": "Invalid Amount"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        ticker = yf.Ticker(pair.replace('_', '') + "=X")
        hist = ticker.history(period='1d')
        if hist.empty: raise Exception("Market Closed or API Error")
        current_price = float(hist['Close'].iloc[-1])
        
        cur.execute("SELECT balance FROM users WHERE id = %s", (session['user_id'],))
        row = cur.fetchone()
        balance = float(row['balance'])
        units = amount_usd / current_price
        new_balance = balance

        if action == 'BUY':
            if balance < amount_usd: return jsonify({"error": "Insufficient Funds"}), 400
            new_balance = balance - amount_usd
            cur.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, session['user_id']))
            cur.execute("""
                INSERT INTO portfolio (user_id, currency_pair, total_units, average_price)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, currency_pair) 
                DO UPDATE SET 
                    total_units = portfolio.total_units + EXCLUDED.total_units,
                    average_price = (portfolio.average_price * portfolio.total_units + EXCLUDED.average_price * EXCLUDED.total_units) / (portfolio.total_units + EXCLUDED.total_units)
            """, (session['user_id'], pair, units, current_price))
            
        elif action == 'SELL':
            cur.execute("SELECT total_units FROM portfolio WHERE user_id = %s AND currency_pair = %s", (session['user_id'], pair))
            holding = cur.fetchone()
            units_to_sell = amount_usd / current_price

            if not holding or float(holding['total_units']) < units_to_sell:
                return jsonify({"error": "Insufficient Holdings"}), 400
                
            new_balance = balance + amount_usd
            cur.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, session['user_id']))
            cur.execute("UPDATE portfolio SET total_units = total_units - %s WHERE user_id = %s AND currency_pair = %s", (units_to_sell, session['user_id'], pair))

        cur.execute("INSERT INTO trading_history (user_id, currency_pair, action_type, entry_price, amount) VALUES (%s, %s, %s, %s, %s)",
                    (session['user_id'], pair, action, current_price, amount_usd))
        conn.commit()
        return jsonify({"message": "Trade Executed", "new_balance": new_balance})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close(); conn.close()

ACTIVE_HEDGES = set() 
HEDGE_TRACKER = {}
@app.route('/api/hedge', methods=['POST'])
def auto_hedge():
    """Activates the Auto-Hedge monitor. Does NOT sell immediately."""
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    pair = request.get_json().get('pair')
    user_id = session['user_id']
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verify the user actually owns this pair
        cur.execute("SELECT total_units FROM portfolio WHERE user_id = %s AND currency_pair = %s AND total_units > 0", (user_id, pair))
        holding = cur.fetchone()
        
        if not holding:
            return jsonify({"error": "No open position to monitor."}), 400
            
        # Add to the active monitoring list
        tracker_key = f"{user_id}_{pair}"
        ACTIVE_HEDGES.add(tracker_key)
        
        return jsonify({"message": f"🛡️ Shield Activated! Monitoring {pair} in the background. Will auto-sell only if loss hits 2%-5%."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally: 
        cur.close()
        conn.close()

# --- SMART CONDITIONAL HEDGING (2% - 5% LOGIC) ---
@app.route('/api/smart_hedge', methods=['POST'])
def smart_hedge():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    pair = data.get('pair')
    
    # Values passed from the UI Test Box
    sim_day1 = data.get('day1_loss')
    sim_day2 = data.get('day2_loss')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 1. Verify user has an open trade
        cur.execute("SELECT total_units, average_price FROM portfolio WHERE user_id = %s AND currency_pair = %s AND total_units > 0", (session['user_id'], pair))
        holding = cur.fetchone()
        
        if not holding:
            return jsonify({"status": "error", "message": "No open position to hedge! Buy some units first."}), 400
            
        units = float(holding['total_units'])
        entry_price = float(holding['average_price'])
        
        # 2. Get Simulated Loss Percentages
        loss_day_1 = float(sim_day1)
        loss_day_2 = float(sim_day2)
        
        # Calculate what the price WOULD be based on Day 2 Loss
        simulated_current_price = entry_price * (1 - (loss_day_2 / 100))

        # 3. EVALUATE THE RULES
        if 2.0 <= loss_day_1 <= 5.0:
            if loss_day_2 > loss_day_1:
                # CONDITION MET: Day 2 is worse. Execute Hedge!
                hedge_amount_usd = units * simulated_current_price
                cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (hedge_amount_usd, session['user_id']))
                cur.execute("UPDATE portfolio SET total_units = 0 WHERE user_id = %s AND currency_pair = %s", (session['user_id'], pair))
                cur.execute("INSERT INTO trading_history (user_id, currency_pair, action_type, entry_price, amount) VALUES (%s, %s, %s, %s, %s)",
                            (session['user_id'], pair, 'HDGE', simulated_current_price, hedge_amount_usd))
                conn.commit()
                
                return jsonify({
                    "status": "hedged", 
                    "message": f"🛡️ HEDGE EXECUTED! Day 1 Loss was {loss_day_1}%. Day 2 worsened to {loss_day_2}%. Position closed to protect capital."
                })
            else:
                # RECOVERING: Day 2 is better. Hold!
                return jsonify({
                    "status": "held", 
                    "message": f"📈 HOLDING. Day 1 Loss was {loss_day_1}%. Day 2 recovered to {loss_day_2}%. Smart Hedge deactivated."
                })
        else:
            # OUTSIDE DANGER ZONE
            return jsonify({
                "status": "ignored", 
                "message": f"⏸️ NO ACTION. Day 1 loss ({loss_day_1}%) is outside the 2% - 5% trigger zone."
            })
            
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally: 
        cur.close()
        conn.close()
# --- HISTORY & DATA ROUTES ---

@app.route('/api/history')
def get_user_history():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    if not conn: return jsonify([])
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT currency_pair, action_type, entry_price, amount, timestamp 
        FROM trading_history 
        WHERE user_id = %s 
        ORDER BY timestamp DESC
    """, (session['user_id'],))
    trades = cur.fetchall()
    cur.close()
    conn.close()

    for trade in trades:
        trade['timestamp'] = trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(trades)

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
        if not pair: return jsonify({"error": "No pair"}), 400

        ticker = yf.Ticker(pair.replace('_', '') + "=X")
        df_intraday = ticker.history(period="1d", interval="1m")
        if df_intraday.empty: df_intraday = ticker.history(period="1d")
        
        df_daily = ticker.history(period="5d") 
        if df_intraday.empty: return jsonify({"error": "Unavailable"}), 404
        
        current_price = df_intraday['Close'].iloc[-1]
        
        if len(df_daily) >= 2: prev_close = df_daily['Close'].iloc[-2]
        else: prev_close = df_daily['Close'].iloc[0]

        diff = current_price - prev_close
        change_percent = (diff / prev_close) * 100

        intraday_data = [{"t": i.strftime('%H:%M'), "y": float(r['Close'])} for i, r in df_intraday.iterrows()]

        return jsonify({
            "pair": pair, 
            "rate": float(current_price), 
            "prev_close": float(prev_close),
            "change_percent": float(change_percent),
            "intraday": intraday_data 
        })
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/portfolio')
def get_portfolio_performance():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT currency_pair, total_units, average_price FROM portfolio WHERE user_id = %s AND total_units > 0", (session['user_id'],))
    holdings = cur.fetchall()
    cur.close()
    conn.close()
    
    portfolio_data = []
    for item in holdings:
        pair = item['currency_pair']
        units = float(item['total_units'])
        avg_price = float(item['average_price'])
        
        try:
            ticker = yf.Ticker(pair.replace('_', '') + "=X")
            current_price = ticker.history(period="1d")['Close'].iloc[-1]
        except:
            current_price = avg_price 
            
        current_value = units * current_price
        invested_value = units * avg_price
        profit_loss = current_value - invested_value
        roi_percent = (profit_loss / invested_value) * 100 if invested_value > 0 else 0
        
        portfolio_data.append({
            "pair": pair, "units": units, "avg_price": avg_price, "current_price": current_price,
            "current_value": current_value, "pl_usd": profit_loss, "pl_percent": roi_percent
        })
    return jsonify(portfolio_data)

@app.route('/api/analyze', methods=['POST'])
def analyze_pair():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
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
        if last_50 > last_200: ma_signal = "BUY (Golden Cross)"
        else: ma_signal = "SELL (Death Cross)"

    history_data = []
    for _, row in df_combined.iterrows():
        history_data.append({
            "x": row['Date'].strftime('%Y-%m-%d'),
            "y": row['Price'],
            "sma50": None if pd.isna(row['SMA_50']) else row['SMA_50'],
            "sma200": None if pd.isna(row['SMA_200']) else row['SMA_200']
        })

    # --- FIX 1: CONSISTENCY (Same result every click) ---
    np.random.seed(42)
    tf.random.set_seed(42)
    random.seed(42)

    recent_prices = df_combined['Price'].values[-60:].reshape(-1, 1)
    if len(recent_prices) < 60: 
        recent_prices = df_combined['Price'].values.reshape(-1, 1)

    scaler_y = MinMaxScaler(feature_range=(0, 1))
    prices_scaled = scaler_y.fit_transform(recent_prices)

    # --- FIX 2: PREVENT "202 Rs" EXPLOSION (Scale the Time Axis) ---
    X_raw = np.arange(len(prices_scaled)).reshape(-1, 1)
    scaler_x = MinMaxScaler(feature_range=(0, 1))
    X_scaled = scaler_x.fit_transform(X_raw)

    y = prices_scaled

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(1,)), 
        tf.keras.layers.Dense(16, activation='relu'),
        tf.keras.layers.Dense(8, activation='relu'),
        tf.keras.layers.Dense(1)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    
    # Train for 50 epochs (Still instant, but makes line smoother)
    model.fit(X_scaled, y, epochs=50, verbose=0)

    future_days = 3
    last_index = len(prices_scaled)
    future_inputs_raw = np.arange(last_index, last_index + future_days).reshape(-1, 1)
    
    # Scale future time exactly like past time to prevent math explosion
    future_inputs_scaled = scaler_x.transform(future_inputs_raw)
    
    preds_scaled = model.predict(future_inputs_scaled, verbose=0)
    preds_actual = scaler_y.inverse_transform(preds_scaled)

    # --- FIX 3: PRESENTATION SAFETY CLAMP ---
    # Guarantees the AI doesn't draw a wild spike for the presentation
    current_price_val = float(recent_prices[-1][0])
    max_deviation = current_price_val * 0.015 # Max 1.5% movement in 3 days
    
    future_predictions = []
    last_date = df_combined['Date'].max()
    for i in range(future_days):
        next_date = last_date + timedelta(days=i+1)
        
        # Clamp the prediction to stay visually realistic
        pred_val = float(preds_actual[i][0])
        pred_val = max(current_price_val - max_deviation, min(pred_val, current_price_val + max_deviation))
        
        future_predictions.append({
            "date": next_date.strftime('%Y-%m-%d'),
            "price": pred_val
        })

    next_day_price = future_predictions[0]['price']
    ml_trend = "UP" if next_day_price >= current_price_val else "DOWN"
    tf.keras.backend.clear_session()

    intraday_data = get_ist_intraday(pair)

    return jsonify({
        "pair": pair,
        "current_price": current_price_val,
        "predicted_price": next_day_price,
        "trend": ml_trend,
        "ma_signal": ma_signal,
        "history": history_data,
        "future_forecast": future_predictions,
        "intraday": intraday_data 
    })

# ==========================================
# 3. BACKGROUND AUTOMATION DAEMON
# ==========================================

# Tracks previous loss state: { "user1_EURINR": 3.5 }
HEDGE_TRACKER = {} 

# --- UPDATE THIS HELPER FUNCTION AT THE BOTTOM OF APP.PY ---
def execute_auto_hedge(cur, user_id, pair, units, current_price, reason):
    """Helper function to execute the sell order in the database"""
    amount_usd = units * current_price
    cur.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount_usd, user_id))
    cur.execute("UPDATE portfolio SET total_units = 0 WHERE user_id = %s AND currency_pair = %s", (user_id, pair))
    cur.execute("INSERT INTO trading_history (user_id, currency_pair, action_type, entry_price, amount) VALUES (%s, %s, %s, %s, %s)",
                (user_id, pair, 'SELL', current_price, amount_usd))
    print(f"[{reason}] Auto-Hedged (Sold) {pair} for User {user_id} at price {current_price}")

def automated_hedge_daemon():
    """Runs continuously in the background to monitor active hedges"""
    print("🤖 Background Auto-Hedge Monitor Started...")
    while True:
        time.sleep(60) # Scan every 60 seconds
        
        # If nobody clicked the shield button, skip the database check
        if not ACTIVE_HEDGES: 
            continue 
            
        conn = get_db_connection()
        if not conn: continue
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("SELECT * FROM portfolio WHERE total_units > 0")
            open_positions = cur.fetchall()

            for pos in open_positions:
                user_id = pos['user_id']
                pair = pos['currency_pair']
                tracker_key = f"{user_id}_{pair}"

                # ONLY check this trade if the user activated the shield
                if tracker_key not in ACTIVE_HEDGES:
                    continue

                units = float(pos['total_units'])
                avg_price = float(pos['average_price'])

                # Get Live Price
                try:
                    ticker = yf.Ticker(pair.replace('_', '') + "=X")
                    current_price = float(ticker.history(period='1d')['Close'].iloc[-1])
                except:
                    continue # Skip if API fails

                # Calculate Loss Percentage
                invested = units * avg_price
                current_val = units * current_price
                pl_pct = ((current_val - invested) / invested) * 100

                # RULE A: Hard Stop Loss (Greater than 5% loss)
                if pl_pct <= -5.0:
                    execute_auto_hedge(cur, user_id, pair, units, current_price, "HARD STOP >5%")
                    ACTIVE_HEDGES.discard(tracker_key) # Turn off shield
                    HEDGE_TRACKER.pop(tracker_key, None)

                # RULE B: The 2% - 5% Smart Evaluation Zone
                elif -5.0 < pl_pct <= -2.0:
                    current_loss = abs(pl_pct) 

                    if tracker_key in HEDGE_TRACKER:
                        previous_loss = HEDGE_TRACKER[tracker_key]
                        
                        if current_loss > previous_loss:
                            # CONDITION MET: Loss is worsening. Execute Hedge!
                            execute_auto_hedge(cur, user_id, pair, units, current_price, "SMART HEDGE WORSENED")
                            ACTIVE_HEDGES.discard(tracker_key) # Turn off shield
                            del HEDGE_TRACKER[tracker_key]
                        else:
                            # Recovering. Keep shield on, update memory, and HOLD.
                            HEDGE_TRACKER[tracker_key] = current_loss
                    else:
                        # First time entering the 2%-5% zone. Record it and wait.
                        HEDGE_TRACKER[tracker_key] = current_loss

                # RULE C: Safe Zone (Loss is < 2% or trade is in Profit like +0.9%)
                else:
                    # Do nothing. Just clear the tracker if it was previously in the danger zone.
                    if tracker_key in HEDGE_TRACKER:
                        del HEDGE_TRACKER[tracker_key] 

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Daemon Error: {e}")
        finally:
            cur.close()
            conn.close()
# Start the background daemon before running the Flask app
threading.Thread(target=automated_hedge_daemon, daemon=True).start()

# --- KEEP YOUR EXISTING APP.RUN BELOW THIS ---
if __name__ == '__main__':
    print(f"\n{'='*40}")
    print(f" AlphaFxTrader - Active")
    print(f" URL: http://127.0.0.1:5000")
    print(f"{'='*40}\n")
    app.run(debug=True, port=5000, use_reloader=False)
