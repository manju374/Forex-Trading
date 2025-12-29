let chartInstance = null;
let globalHistoryData = []; 
const API_BASE_URL = 'http://127.0.0.1:5000';
const LIVE_RATES_API = 'https://open.er-api.com/v6/latest/';

document.addEventListener('DOMContentLoaded', () => {
    fetchAvailablePairs();
    document.getElementById('analyzeBtn').addEventListener('click', analyzeData);
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            updateTimeRange(e.target.dataset.range, e.target);
        });
    });
});

async function fetchAvailablePairs() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/pairs`);
        if (!res.ok) throw new Error("Failed to connect to backend");

        const pairs = await res.json();
        const select = document.getElementById('currencySelect');
        select.innerHTML = ''; 

        if(pairs.length === 0) {
            const opt = document.createElement('option');
            opt.text = "No CSV files found in /data";
            select.appendChild(opt);
            return;
        }

        const defaultOpt = document.createElement('option');
        defaultOpt.text = "Select a Currency Pair";
        defaultOpt.value = "";
        defaultOpt.disabled = true;
        defaultOpt.selected = true;
        select.appendChild(defaultOpt);

        pairs.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.innerText = p.replace('_', '/');
            select.appendChild(opt);
        });
    } catch (err) {
        console.error("Backend Error:", err);
        const select = document.getElementById('currencySelect');
        select.innerHTML = '<option>Connection Error</option>';
    }
}

async function analyzeData() {
    const pair = document.getElementById('currencySelect').value;
    if (!pair) { alert("Please select a currency pair first."); return; }

    const loader = document.getElementById('loader');
    loader.classList.remove('hidden');

    try {
        const res = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pair: pair })
        });

        if (!res.ok) throw new Error("Analysis failed");
        const data = await res.json();

        globalHistoryData = data.history;
        const lastHistoryPrice = data.current_price;

        const maSignalEl = document.getElementById('maSignal');
        maSignalEl.innerText = data.ma_signal;
        if (data.ma_signal.includes("BUY")) maSignalEl.style.color = "#4ade80";
        else if (data.ma_signal.includes("SELL")) maSignalEl.style.color = "#f87171";
        else maSignalEl.style.color = "#f1f5f9";

        updateStrategyTooltip(data.ma_signal);

        await fetchLiveAndCompare(pair, lastHistoryPrice);

        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector('.filter-btn[data-range="MAX"]').classList.add('active');
        
        updateTimeRange('MAX');

    } catch (err) {
        alert("Error during analysis: " + err.message);
    } finally {
        loader.classList.add('hidden');
    }
}

function updateStrategyTooltip(maSignal) {
    const badge = document.getElementById('strategyBadge');
    const desc = document.getElementById('strategyDesc');

    const isMaBuy = maSignal.includes("BUY");
    const isMaSell = maSignal.includes("SELL");

    badge.className = 'strategy-badge';

    if (isMaBuy) {
        badge.innerText = 'BULLISH';
        badge.classList.add('strong-buy');
        desc.innerHTML = '✅ <strong>Golden Cross Active:</strong> The 50-day SMA is above the 200-day SMA. This is a classic technical indicator of a long-term uptrend. Consider <strong>LONG</strong> positions.';
    } 
    else if (isMaSell) {
        badge.innerText = 'BEARISH';
        badge.classList.add('strong-sell');
        desc.innerHTML = '🔻 <strong>Death Cross Active:</strong> The 50-day SMA is below the 200-day SMA. This indicates downward momentum. Consider <strong>SHORT</strong> positions or exiting.';
    }
    else {
        badge.innerText = 'NEUTRAL';
        desc.innerText = 'No clear Moving Average crossover signal detected. Market may be ranging.';
    }
}

async function fetchLiveAndCompare(pairStr, historyPrice) {
    const livePriceEl = document.getElementById('livePrice');
    const liveChangeEl = document.getElementById('liveChange');
    const subtextEl = document.getElementById('liveSubtext');

    try {
        const res = await fetch(`${API_BASE_URL}/api/live`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pair: pairStr })
        });
        
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const currentRate = data.rate; 
        const diff = currentRate - historyPrice;
        const percentage = (diff / historyPrice) * 100;
        
        livePriceEl.innerText = currentRate.toFixed(4);
        
        const sign = percentage >= 0 ? "+" : "";
        liveChangeEl.innerText = `${sign}${percentage.toFixed(2)}%`;
        
        liveChangeEl.classList.remove('hidden', 'change-up', 'change-down');
        liveChangeEl.classList.add(percentage >= 0 ? 'change-up' : 'change-down');
        subtextEl.innerText = `vs Last CSV Price (${historyPrice.toFixed(4)})`;

    } catch (err) {
        livePriceEl.innerText = historyPrice.toFixed(4); 
        liveChangeEl.innerText = "Offline";
        liveChangeEl.classList.add('change-down');
    }
}

function updateTimeRange(range, clickedBtn) {
    if (globalHistoryData.length === 0) return;

    if (clickedBtn) {
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        clickedBtn.classList.add('active');
    }

    const lastDateStr = globalHistoryData[globalHistoryData.length - 1].x;
    const referenceDate = new Date(lastDateStr);
    let cutoffDate = new Date(referenceDate);

    if (range === '1M') cutoffDate.setMonth(referenceDate.getMonth() - 1);
    if (range === '6M') cutoffDate.setMonth(referenceDate.getMonth() - 6);
    if (range === '1Y') cutoffDate.setFullYear(referenceDate.getFullYear() - 1);
    if (range === '5Y') cutoffDate.setFullYear(referenceDate.getFullYear() - 5);
    if (range === 'MAX') cutoffDate = new Date('1900-01-01');

    const filteredData = globalHistoryData.filter(d => {
        const date = new Date(d.x);
        return date >= cutoffDate;
    });

    const pairName = document.getElementById('currencySelect').value;
    renderChart(pairName, filteredData);
}

function renderChart(label, history) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    
    if (chartInstance) chartInstance.destroy();

    const labels = history.map(d => d.x);
    const prices = history.map(d => d.y);
    const sma50 = history.map(d => d.sma50); 
    const sma200 = history.map(d => d.sma200);
    
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Price',
                    data: prices,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.1,
                    order: 1
                },
                {
                    label: 'SMA 50',
                    data: sma50,
                    borderColor: '#facc15', 
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.1,
                    order: 2
                },
                {
                    label: 'SMA 200',
                    data: sma200,
                    borderColor: '#f87171', 
                    borderWidth: 1.5,
                    pointRadius: 0,
                    fill: false,
                    tension: 0.1,
                    order: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: {
                x: { grid: { color: '#334155' }, ticks: { maxTicksLimit: 10 } },
                y: { grid: { color: '#334155' } }
            },
            plugins: {
                legend: { labels: { color: '#f1f5f9' } }
            }
        }
    });
}