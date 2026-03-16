let chartInstance = null;
let globalHistoryData = []; 
let globalFutureData = []; 
let globalIntradayData = []; // Store 1D data
const API_BASE_URL = 'http://127.0.0.1:5000';

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btnHedge').addEventListener('click', async () => {
    const pair = document.getElementById('currencySelect').value;
    if (!pair) { showToast("Select a currency pair first!", "error"); return; }

    try {
        const res = await fetch(`${API_BASE_URL}/api/hedge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pair: pair })
        });
        
        const data = await res.json();
        if(res.ok) {
            showToast(data.message, "success");
            updateWallet(); // Refresh your balance
        } else {
            showToast(data.error, "error");
        }
    } catch(e) {
        showToast("Hedge Failed: Network Error", "error");
    }
});
    fetchAvailablePairs();
    setupProfileEvents(); // New Profile Logic

    document.getElementById('analyzeBtn').addEventListener('click', analyzeData);
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Handle clicking the dot inside the button
            const target = e.target.tagName === 'SPAN' ? e.target.parentElement : e.target;
            updateTimeRange(target.dataset.range, target);
        });
    });
    ['toggleSMA50', 'toggleSMA200', 'toggleAI'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            // Re-render using currently loaded global data
            // We verify specific range to ensure we don't break 1D view
            const activeBtn = document.querySelector('.filter-btn.active');
            const range = activeBtn ? activeBtn.dataset.range : 'MAX';
            
            if(range !== '1D') {
                updateTimeRange(range, null); 
            }
        });
    });
});

// --- 1. Profile & Modal Logic ---
function setupProfileEvents() {
    // Dropdown Toggle
    const profileBtn = document.getElementById('profileBtn');
    const dropdown = document.getElementById('profileDropdown');
    
    if(profileBtn) {
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('hidden');
        });
        document.addEventListener('click', () => dropdown.classList.add('hidden'));
    }

    // Modal Logic
    const historyLink = document.getElementById('historyLink');
    const modal = document.getElementById('historyModal');
    const closeModal = document.querySelector('.close-modal');

    if(historyLink) {
        historyLink.addEventListener('click', async (e) => {
            e.preventDefault();
            await fetchUserHistory();
            modal.classList.remove('hidden');
        });
    }

    if(closeModal) {
        closeModal.addEventListener('click', () => modal.classList.add('hidden'));
    }

    // --- Add this inside setupProfileEvents() ---

    // ... existing history link logic ...

    // Portfolio Modal Logic
    const portfolioLink = document.getElementById('portfolioLink');
    const portfolioModal = document.getElementById('portfolioModal');
    const closePortfolio = document.getElementById('closePortfolio');

    if (portfolioLink) {
        portfolioLink.addEventListener('click', async (e) => {
            e.preventDefault();
            await fetchPortfolio();
            portfolioModal.classList.remove('hidden');
        });
    }

    if (closePortfolio) {
        closePortfolio.addEventListener('click', () => portfolioModal.classList.add('hidden'));
    }

// --- Add this new function to script.js ---

async function fetchPortfolio() {
    const tbody = document.querySelector('#portfolioTable tbody');
    const msg = document.getElementById('noPortfolioMsg');
    
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Fetching live market data...</td></tr>';

    try {
        const res = await fetch(`${API_BASE_URL}/api/portfolio`);
        const data = await res.json();
        
        tbody.innerHTML = ''; // Clear loading message

        if (data.length === 0) {
            msg.classList.remove('hidden');
        } else {
            msg.classList.add('hidden');
            
            data.forEach(item => {
                // Determine Colors
                const isProfit = item.pl_usd >= 0;
                const plClass = isProfit ? 'text-green' : 'text-red';
                const sign = isProfit ? '+' : '';

                const row = `
                    <tr>
                        <td style="font-weight:bold;">${item.pair}</td>
                        <td>${item.units.toFixed(4)}</td>
                        <td>${item.avg_price.toFixed(4)}</td>
                        <td>${item.current_price.toFixed(4)}</td>
                        <td>$${item.current_value.toFixed(2)}</td>
                        <td class="${plClass}">${sign}$${item.pl_usd.toFixed(2)}</td>
                        <td class="${plClass}" style="font-weight:bold;">${sign}${item.pl_percent.toFixed(2)}%</td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        }
    } catch (err) {
        console.error(err);
        tbody.innerHTML = '<tr><td colspan="7">Error loading portfolio data.</td></tr>';
    }
}
}

async function fetchUserHistory() {
    const tbody = document.querySelector('#historyTable tbody');
    const msg = document.getElementById('noHistoryMsg');
    
    // Show loading state
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Loading history...</td></tr>';

    try {
        const res = await fetch(`${API_BASE_URL}/api/history`);
        const trades = await res.json();
        
        tbody.innerHTML = '';
        
        if (trades.length === 0) {
            msg.classList.remove('hidden');
        } else {
            msg.classList.add('hidden');
            
            trades.forEach(t => {
                // --- FIX: Manual Date Parsing to Prevent Timezone Shifts ---
                // Expected format from backend: "2026-01-23 19:30:00"
                // We split the string to force the browser to accept these exact numbers
                
                let dateObj;
                
                // Safety check: ensure t.timestamp exists and is a string
                if (t.timestamp && typeof t.timestamp === 'string') {
                    const [datePart, timePart] = t.timestamp.split(' ');
                    const [year, month, day] = datePart.split('-').map(Number);
                    const [hour, minute, second] = timePart.split(':').map(Number);

                    // Note: Month is 0-indexed in JS (0 = Jan, 1 = Feb)
                    dateObj = new Date(year, month - 1, day, hour, minute, second);
                } else {
                    // Fallback if format is unexpected
                    dateObj = new Date(t.timestamp);
                }

                // Format: Jan 24, 2026
                const formattedDate = dateObj.toLocaleDateString('en-US', {
                    month: 'short', day: 'numeric', year: 'numeric'
                });
                
                // Format: 10:30 PM
                const formattedTime = dateObj.toLocaleTimeString('en-US', {
                    hour: '2-digit', minute: '2-digit'
                });

                const row = `
                    <tr>
                        <td style="font-size:0.85rem; color:#cbd5e1;">
                            ${formattedDate}<br>
                            <span style="color:#64748b; font-size:0.8em;">${formattedTime}</span>
                        </td>
                        <td style="font-weight:bold;">${t.currency_pair}</td>
                        <td class="action-${t.action_type}">${t.action_type}</td>
                        <td>${parseFloat(t.entry_price).toFixed(4)}</td>
                        <td>$${parseFloat(t.amount).toFixed(2)}</td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        }
    } catch(err) {
        console.error("History Error:", err);
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: #f87171;">Error loading trading history.</td></tr>';
    }
}
// --- 2. Existing Analysis Logic ---
async function fetchAvailablePairs() {
    /* ... (Keep existing code here) ... */
    // Ensure you keep the fetchAvailablePairs code from previous turn
    try {
        const res = await fetch(`${API_BASE_URL}/api/pairs`);
        const pairs = await res.json();
        const select = document.getElementById('currencySelect');
        select.innerHTML = ''; 
        const defaultOpt = document.createElement('option');
        defaultOpt.text = "Select a Currency Pair";
        select.appendChild(defaultOpt);
        pairs.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.innerText = p.replace('_', '/');
            select.appendChild(opt);
        });
    } catch(e) { console.error(e); }
}

async function analyzeData() {
    const pair = document.getElementById('currencySelect').value;
    if (!pair) { alert("Please select a currency pair first."); return; }

    const loader = document.getElementById('loader');
    loader.classList.remove('hidden');

    try {
        // 1. Fetch Analysis Data
        const res = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pair: pair })
        });

        if (!res.ok) throw new Error("Analysis failed");
        const data = await res.json();

        // 2. Set Global Data
        globalHistoryData = data.history;
        globalFutureData = data.future_forecast;
        
        // 3. Update Dashboard (Strategy, Colors, Text)
        updateDashboardText(data);
        
        // 4. Update Live Price
        await fetchLiveAndCompare(pair, data.current_price);

        // 5. Render Chart
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelector('.filter-btn[data-range="MAX"]').classList.add('active');
        updateTimeRange('MAX');

    } catch (err) {
        alert("Error during analysis: " + err.message);
        console.error(err);
    } finally {
        loader.classList.add('hidden');
    }
}

// --- REPLACE THIS FUNCTION IN SCRIPT.JS ---
async function fetchLiveAndCompare(pairStr, historyPrice) {
    const livePriceEl = document.getElementById('livePrice');
    const liveChangeEl = document.getElementById('liveChange');
    const subtextEl = document.getElementById('liveSubtext');

    livePriceEl.innerText = "Loading...";
    
    try {
        const res = await fetch(`${API_BASE_URL}/api/live`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pair: pairStr })
        });
        
        if(!res.ok) throw new Error("API Limit or Network Error");

        const data = await res.json();
        
        globalIntradayData = data.intraday || []; 

        const currentRate = data.rate; 
        const percentage = data.change_percent; // Use the backend calculation
        
        // Update Price
        livePriceEl.innerText = currentRate.toFixed(4);
        
        // Update Percentage
        const sign = percentage >= 0 ? "+" : "";
        liveChangeEl.innerText = `${sign}${percentage.toFixed(2)}%`;
        
        // Update Colors
        liveChangeEl.classList.remove('hidden', 'change-up', 'change-down');
        if (percentage >= 0) {
            liveChangeEl.classList.add('change-up');
            livePriceEl.style.color = "#4ade80"; // Green
        } else {
            liveChangeEl.classList.add('change-down');
            livePriceEl.style.color = "#f87171"; // Red
        }

        subtextEl.innerText = `vs Prev Close (${data.prev_close.toFixed(4)})`;

    } catch (err) {
        console.error("Live Price Error:", err);
        // Fallback to history price if live fetch fails
        livePriceEl.innerText = historyPrice.toFixed(4); 
        liveChangeEl.innerText = "--"; 
        liveChangeEl.classList.remove('change-up', 'change-down');
        subtextEl.innerText = "Live data unavailable";
    }
}
function updateDashboardText(data) {
    // --- 1. MA Strategy Card Logic ---
    const maSignalEl = document.getElementById('maSignal');
    const maCard = maSignalEl.closest('.stat-card'); 

    // Reset Classes
    if (maCard) maCard.classList.remove('card-buy', 'card-sell');
    if (maSignalEl) maSignalEl.classList.remove('text-green', 'text-red');

    if (maSignalEl) maSignalEl.innerText = data.ma_signal;

    if (data.ma_signal.includes("BUY")) {
        if (maCard) maCard.classList.add('card-buy');      // Add Green Background
        if (maSignalEl) maSignalEl.classList.add('text-green'); // Add Green Text
    } 
    else if (data.ma_signal.includes("SELL")) {
        if (maCard) maCard.classList.add('card-sell');     // Add Red Background
        if (maSignalEl) maSignalEl.classList.add('text-red');  
    } // FIXED: This closing bracket was missing in your code!

    // --- 2. AI Prediction Logic ---
    const aiTrendEl = document.getElementById('aiTrend');
    const aiTargetEl = document.getElementById('aiTarget');
    
    if (aiTrendEl) {
        aiTrendEl.innerText = data.trend;
        aiTrendEl.style.color = data.trend === "UP" ? "#4ade80" : "#f87171";
    }
    if (aiTargetEl) {
        aiTargetEl.innerText = `Target: ${data.predicted_price.toFixed(4)}`;
    }

    // --- 3. HYBRID STRATEGY INSIGHTS LOGIC (NEW) ---
    // Make sure your HTML has an element with id="strategyInsights"
    const insightsEl = document.getElementById('strategyInsights');
    
    if (insightsEl) {
        if (data.ma_signal.includes("BUY") && data.trend === "UP") {
            insightsEl.innerText = "Strong Bullish (Hybrid Match ✅)";
            insightsEl.style.color = "#4ade80"; // Green
        } 
        else if (data.ma_signal.includes("SELL") && data.trend === "DOWN") {
            insightsEl.innerText = "Strong Bearish (Hybrid Match ✅)";
            insightsEl.style.color = "#f87171"; // Red
        } 
        else {
            // When MA says BUY but AI says DOWN (or vice versa)
            insightsEl.innerText = "Neutral / Ranging (Signals Disagree ⚠️)";
            insightsEl.style.color = "#fbbf24"; // Yellow warning color
        }
    }

    // --- 4. Tooltip ---
    // If you have a tooltip function, you can optionally pass both data points to it now
    if (typeof updateStrategyTooltip === "function") {
        updateStrategyTooltip(data.ma_signal, data.trend);
    }
}
// --- 3. Updated Time Range Logic (Includes 1D) ---
function updateTimeRange(range, clickedBtn) {
    if (globalHistoryData.length === 0 && range !== '1D') return;

    if (clickedBtn) {
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        clickedBtn.classList.add('active');
    }

    // SPECIAL CASE: 1D View (Intraday)
    if (range === '1D') {
        renderIntradayChart(globalIntradayData);
        return;
    }

    // Standard Historical Logic
    const lastDateStr = globalHistoryData[globalHistoryData.length - 1].x;
    const referenceDate = new Date(lastDateStr);
    let cutoffDate = new Date(referenceDate);

    if (range === '1W') cutoffDate.setDate(referenceDate.getDate() - 7);
    if (range === '1M') cutoffDate.setMonth(referenceDate.getMonth() - 1);
    if (range === '6M') cutoffDate.setMonth(referenceDate.getMonth() - 6);
    if (range === '1Y') cutoffDate.setFullYear(referenceDate.getFullYear() - 1);
    if (range === '5Y') cutoffDate.setFullYear(referenceDate.getFullYear() - 5);
    if (range === 'MAX') cutoffDate = new Date('1900-01-01');

    const filteredHistory = globalHistoryData.filter(d => new Date(d.x) >= cutoffDate);
    renderChart(filteredHistory, globalFutureData);
}

// --- 4. Render Functions ---

// Standard Chart (Day Candles)
function renderChart(history, future) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    
    if (chartInstance) chartInstance.destroy();

    // Check which boxes are ticked
    const showSMA50 = document.getElementById('toggleSMA50').checked;
    const showSMA200 = document.getElementById('toggleSMA200').checked;
    const showAI = document.getElementById('toggleAI').checked;

    const labels = history.map(d => d.x);
    const prices = history.map(d => d.y);
    const sma50 = history.map(d => d.sma50); 
    const sma200 = history.map(d => d.sma200); // Ensure this data exists

    const stitchPoint = prices[prices.length - 1]; 
    const futurePrices = future.map(d => d.price);
    const combinedLabels = [...labels, ...future.map(d => d.date)];

    // Define Datasets
    const datasets = [
        {
            label: 'Price',
            data: [...prices, ...new Array(future.length).fill(null)],
            borderColor: '#38bdf8', 
            backgroundColor: 'rgba(56, 189, 248, 0.1)',
            borderWidth: 2, 
            pointRadius: 0, 
            fill: true,
            order: 1
        }
    ];

    // Conditionally Add SMA 50
    if (showSMA50) {
        datasets.push({
            label: 'SMA 50',
            data: [...sma50, ...new Array(future.length).fill(null)],
            borderColor: '#4ade80', // Green
            borderWidth: 1.5, 
            pointRadius: 0,
            fill: false,
            tension: 0.1,
            order: 2
        });
    }

    // Conditionally Add SMA 200
    if (showSMA200) {
        datasets.push({
            label: 'SMA 200',
            data: [...sma200, ...new Array(future.length).fill(null)],
            borderColor: '#f87171', // Red
            borderWidth: 1.5, 
            pointRadius: 0,
            fill: false,
            tension: 0.1,
            order: 3
        });
    }

    // Conditionally Add AI Forecast
    if (showAI) {
        datasets.push({
            label: 'AI Forecast',
            data: [...new Array(labels.length - 1).fill(null), stitchPoint, ...futurePrices],
            borderColor: '#a855f7', 
            borderDash: [5, 5], 
            borderWidth: 2, 
            pointRadius: 2,
            fill: false,
            order: 0
        });
    }

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: combinedLabels,
            datasets: datasets
        },
        options: {
            responsive: true, 
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: { 
                x: { grid: { color: '#334155' } }, 
                y: { grid: { color: '#334155' } } 
            },
            plugins: {
                legend: { display: false } // Hiding default legend since we have custom toggles
            }
        }
    });
}
// New Intraday Chart (Minute Candles)
function renderIntradayChart(data) {
    const ctx = document.getElementById('mainChart').getContext('2d');
    if (chartInstance) chartInstance.destroy();

    const labels = data.map(d => d.t);
    const prices = data.map(d => d.y);
    
    // Color logic: Green if close > open, Red if close < open
    const isGreen = prices[prices.length - 1] >= prices[0];
    const color = isGreen ? '#4ade80' : '#f87171';
    const bgColor = isGreen ? 'rgba(74, 222, 128, 0.1)' : 'rgba(248, 113, 113, 0.1)';

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Today',
                data: prices,
                borderColor: color,
                backgroundColor: bgColor,
                borderWidth: 2,
                pointRadius: 0, // Smooth line like Groww
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: { legend: { display: false }, tooltip: { intersect: false } },
            scales: {
                x: { display: true, grid: { display: false } }, // Hide grid for clean look
                y: { grid: { color: '#334155' } }
            }
        }
    });
}

function updateStrategyTooltip(maSignal) {
    const badge = document.getElementById('strategyBadge');
    const desc = document.getElementById('strategyDesc');

    // Reset Badge Classes
    badge.className = 'strategy-badge';

    if (maSignal.includes("BUY")) {
        badge.innerText = 'BULLISH';
        badge.classList.add('strong-buy');
        desc.innerHTML = `
            ✅ <strong>Golden Cross Detected:</strong> 
            The short-term moving average (50) has crossed <em>above</em> the long-term average (200). 
            <br><br>
            This indicates strong <strong>Buying Pressure</strong>. Historical data suggests the price may continue to rise.
        `;
    } 
    else if (maSignal.includes("SELL")) {
        badge.innerText = 'BEARISH';
        badge.classList.add('strong-sell');
        desc.innerHTML = `
            🔻 <strong>Death Cross Detected:</strong> 
            The short-term moving average (50) has crossed <em>below</em> the long-term average (200). 
            <br><br>
            This indicates strong <strong>Selling Pressure</strong>. Historical data suggests the price may fall further.
        `;
    }
    else {
        badge.innerText = 'NEUTRAL';
        desc.innerHTML = `
            ⚖️ <strong>Market Consolidation:</strong> 
            No clear crossover detected. The market is likely moving sideways (ranging). 
            Wait for a clearer breakout signal before entering a position.
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // ... existing listeners ...
    updateWallet(); // Fetch balance on load

    document.getElementById('btnBuy').addEventListener('click', () => executeTrade('BUY'));
    document.getElementById('btnSell').addEventListener('click', () => executeTrade('SELL'));
});

async function updateWallet() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/wallet`);
        if (res.ok) {
            const data = await res.json();
            document.getElementById('walletBalance').innerText = `$${data.balance.toFixed(2)}`;
        }
    } catch (e) { console.error(e); }
}

async function executeTrade(action) {
    const pair = document.getElementById('currencySelect').value;
    const amount = document.getElementById('tradeAmount').value;
    
    // Replaces alert("Select a pair first!")
    if (!pair) { showToast("Please select a currency pair first!", "error"); return; }
    if (!amount || amount < 10) { showToast("Minimum trade amount is $10", "error"); return; }

    const msgEl = document.getElementById('tradeMessage');
    msgEl.innerText = "Processing...";
    msgEl.classList.remove('hidden');

    try {
        const res = await fetch(`${API_BASE_URL}/api/trade`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pair, action, amount })
        });

        const data = await res.json();

        if (res.ok) {
            // SUCCESS TOAST
            showToast(`Success! ${action} order placed for ${pair}`, "success");
            
            document.getElementById('walletBalance').innerText = `$${data.new_balance.toFixed(2)}`;
            updateWallet(); 
        } else {
            // ERROR TOAST
            showToast(data.error || "Trade Failed", "error");
        }
    } catch (err) {
        showToast("Network Error: Could not connect to server", "error");
    } finally {
        msgEl.classList.add('hidden');
    }
}
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    
    // Icon selection
    const icon = type === 'success' ? '✅' : '⚠️';
    
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icon}</span> <span>${message}</span>`;
    
    container.appendChild(toast);

    // Remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
