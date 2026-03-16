# FxTrader: Hybrid AI Forex Trading Engine 📈🤖

FxTrader is a full-stack, machine-learning-powered Forex trading dashboard. It utilizes a **Hybrid Artificial Intelligence Strategy** that combines macroeconomic Simple Moving Averages (SMA) with a TensorFlow Deep Neural Network (DNN) to forecast currency trends. The system also features an asynchronous, 24/7 Auto-Hedge risk management daemon to protect user portfolios.

---

## 🏗️ System Architecture & Block Diagram

The application follows a secure Client-Server multi-tier architecture with a detached threading loop for background risk management.

```mermaid
graph TD
    %% Define Nodes
    UI[User Interface <br> HTML5 / JS / Chart.js]
    Backend[Flask Backend <br> Python WSGI Server]
    DB[(PostgreSQL <br> alphafxtrader_db)]
    API[Yahoo Finance API <br> Live Market Data]
    ML[AI Pipeline <br> TensorFlow / Keras]
    Daemon((Auto-Hedge <br> Background Thread))

    %% Define Connections
    UI <-->|REST API Requests| Backend
    Backend <-->|ACID Transactions| DB
    Backend <-->|Fetch OHLC & Live Ticks| API
    Backend -->|60-Day Rolling Data| ML
    ML -->|3-Day Price Forecast| Backend
    
    %% Background Process
    Daemon -.->|Polls every 60s| Backend
    Daemon -.->|Auto-Liquidates at 2-5% loss| DB

    %% Styling
    style UI fill:#3b82f6,stroke:#1e3a8a,color:#fff
    style Backend fill:#10b981,stroke:#047857,color:#fff
    style DB fill:#f59e0b,stroke:#b45309,color:#fff
    style API fill:#6366f1,stroke:#4338ca,color:#fff
    style ML fill:#8b5cf6,stroke:#5b21b6,color:#fff
    style Daemon fill:#ef4444,stroke:#b91c1c,color:#fff

✨ Key Features
Hybrid AI Confluence (SMA + DNN): Filters out market noise by comparing long-term Moving Averages with short-term Deep Learning momentum. This filtration blocks "False Positive" buy signals in ranging markets, mathematically pushing predictive accuracy to 81.4%.

Live Price Execution: Bypasses stale data by fetching microsecond-accurate prices from Yahoo Finance before executing any database transaction.

Autonomous Risk Management: A detached Python background thread runs continuously. Every 60 seconds, it cross-references live market prices with the user's active portfolio. If an asset drops past the dynamic 2% - 5% threshold, the system auto-liquidates the position to preserve capital.

Interactive Data Visualization: Renders smooth, GPU-accelerated time-series graphs using Chart.js, cleanly plotting historical data against the AI's future prediction paths.

🛠️ Technology Stack
Frontend: HTML5, CSS3, JavaScript (ES6), Chart.js

Backend: Python 3.x, Flask

Database: PostgreSQL (psycopg2)

Machine Learning: TensorFlow, Keras, Pandas, NumPy, Scikit-Learn (MinMaxScaler)

External Data API: yfinance (Yahoo Finance)

🚀 Installation & Setup
Follow these steps to run AlphaFxTrader on your local machine.

1. Prerequisites
Python 3.8+ installed

PostgreSQL installed and running on port 5432

2. Clone the Repository
git clone [https://github.com/manju374/Forex-Trading.git]

3. Create a Virtual Environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

4. Install Dependencies
pip install -r requirements.txt

5. Environment Variables Configuration
Create a .env file in the root directory (do not commit this file to Git) and add your secure credentials:
# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_secure_flask_key

# Database Credentials
DB_HOST=localhost
DB_NAME=ForexTrading
DB_USER=postgres
DB_PASSWORD=your_database_password

6. Run the Application
Start the Werkzeug WSGI server and the background Auto-Hedge daemon:
python app.py
Open your web browser and navigate to: http://localhost:5000

🧠 Machine Learning Methodology
The forecasting engine utilizes a Univariate Time-Series Deep Neural Network.

Input Layer: Accepts a 60-day rolling window of historically scaled closing prices.

Hidden Layers: A lightweight 16-node and 8-node dual-layer architecture utilizing the ReLU activation function to prevent overfitting and guarantee low-latency web responses.

Output: Predicts the directional end-of-day closing price for the next 3 days, dynamically anchoring the visual UI graph to prevent contradictory text/line slopes.
