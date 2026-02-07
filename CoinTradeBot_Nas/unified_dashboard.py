# unified_dashboard.py - 통합 웹 대시보드
# 업비트 + 바이낸스를 하나의 페이지에서 모니터링

import os
import requests
from flask import Flask, render_template_string, jsonify, request as flask_request
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 기존 대시보드 주소 (Docker 내부 네트워크)
UPBIT_API = os.getenv('UPBIT_API_URL', 'http://upbit-web:5001')
BINANCE_API = os.getenv('BINANCE_API_URL', 'http://binance-web:5000')

executor = ThreadPoolExecutor(max_workers=4)


def fetch_api(url, timeout=5):
    """API 호출 (에러 시 None 반환)"""
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.json()
    except Exception as e:
        logger.warning(f"API fetch failed: {url} - {e}")
        return None


@app.route('/api/unified')
def api_unified():
    """양쪽 데이터 통합"""
    upbit_future = executor.submit(fetch_api, f'{UPBIT_API}/api/data')
    binance_future = executor.submit(fetch_api, f'{BINANCE_API}/api/data')

    upbit = upbit_future.result()
    binance = binance_future.result()

    return jsonify({
        'upbit': upbit,
        'binance': binance,
    })


@app.route('/api/logs/<exchange>')
def api_logs(exchange):
    """각 거래소 로그 프록시"""
    lines = flask_request.args.get('lines', 100)
    if exchange == 'upbit':
        url = f'{UPBIT_API}/api/logs?lines={lines}'
    elif exchange == 'binance':
        url = f'{BINANCE_API}/api/logs?lines={lines}'
    else:
        return jsonify({'logs': [], 'total': 0})

    data = fetch_api(url)
    return jsonify(data or {'logs': ['Service unavailable'], 'total': 0})


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CoinTrade Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }

        /* Tab Navigation */
        .tab-nav {
            display: flex;
            background: rgba(0,0,0,0.3);
            border-bottom: 1px solid rgba(255,255,255,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .tab-btn {
            flex: 1;
            padding: 16px 20px;
            background: none;
            border: none;
            color: #888;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }
        .tab-btn:hover { color: #ccc; background: rgba(255,255,255,0.03); }
        .tab-btn.active-overview { color: #a78bfa; border-bottom-color: #a78bfa; }
        .tab-btn.active-upbit { color: #3b82f6; border-bottom-color: #3b82f6; }
        .tab-btn.active-binance { color: #00d4ff; border-bottom-color: #00d4ff; }

        .tab-btn .status-dot {
            display: inline-block;
            width: 8px; height: 8px;
            border-radius: 50%;
            margin-left: 6px;
            background: #444;
        }
        .tab-btn .status-dot.online { background: #00ff88; }
        .tab-btn .status-dot.offline { background: #ff4444; }

        /* Tab Content */
        .tab-content { display: none; padding: 20px; }
        .tab-content.active { display: block; }

        .container { max-width: 1400px; margin: 0 auto; }

        /* Overview */
        .overview-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .overview-card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            text-align: center;
        }
        .overview-card h3 { color: #888; font-size: 0.9em; margin-bottom: 10px; }
        .overview-card .value { font-size: 1.8em; font-weight: bold; }
        .overview-card .sub { color: #888; font-size: 0.85em; margin-top: 5px; }

        .exchange-summary {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .exchange-box {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .exchange-box h2 {
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .exchange-box.upbit h2 { color: #3b82f6; }
        .exchange-box.binance h2 { color: #00d4ff; }

        /* Common card/grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .card h2 {
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .upbit-tab .card h2 { color: #3b82f6; }
        .binance-tab .card h2 { color: #00d4ff; }

        .balance { font-size: 2em; font-weight: bold; }
        .balance.upbit-color { color: #3b82f6; }
        .balance.binance-color { color: #00d4ff; }

        .price-row, .trade-row, .settings-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .price-row:last-child, .trade-row:last-child { border-bottom: none; }
        .symbol { font-weight: bold; }
        .positive { color: #00ff88; }
        .negative { color: #ff4444; }

        .position {
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .position-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .position-symbol { font-size: 1.2em; font-weight: bold; }
        .position-details { color: #888; font-size: 0.9em; }

        .side-buy { color: #00ff88; font-weight: bold; }
        .side-sell { color: #ff4444; font-weight: bold; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }
        .stat-box {
            text-align: center;
            padding: 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
        }
        .stat-label { color: #888; font-size: 0.85em; margin-bottom: 5px; }
        .stat-value { font-size: 1.3em; font-weight: bold; }

        .no-data { color: #666; text-align: center; padding: 20px; }

        /* Logs */
        .log-container { margin-top: 20px; }
        .log-header { display: flex; justify-content: space-between; align-items: center; }
        .log-controls { display: flex; gap: 10px; align-items: center; }
        .log-controls button, .log-controls select {
            background: rgba(255,255,255,0.1);
            color: #eee;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 4px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
        }
        .log-controls button:hover { background: rgba(255,255,255,0.15); }
        .log-controls button.active { background: rgba(59,130,246,0.4); color: #3b82f6; }
        .log-box {
            background: #0d1117;
            border-radius: 10px;
            padding: 15px;
            margin-top: 10px;
            max-height: 500px;
            overflow-y: auto;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 0.82em;
            line-height: 1.6;
        }
        .log-line { white-space: pre-wrap; word-break: break-all; }
        .log-line.log-error { color: #ff4444; }
        .log-line.log-warning { color: #ffaa00; }
        .log-line.log-success { color: #00ff88; }
        .log-line.log-info { color: #aaa; }

        footer {
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }

        @media (max-width: 768px) {
            .grid, .exchange-summary { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: 1fr; }
            .overview-grid { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
    <!-- Tab Navigation -->
    <nav class="tab-nav">
        <button class="tab-btn active-overview" onclick="switchTab('overview')" id="tab-overview">
            Overview <span class="status-dot" id="dot-overview"></span>
        </button>
        <button class="tab-btn" onclick="switchTab('upbit')" id="tab-upbit">
            Upbit <span class="status-dot" id="dot-upbit"></span>
        </button>
        <button class="tab-btn" onclick="switchTab('binance')" id="tab-binance">
            Binance <span class="status-dot" id="dot-binance"></span>
        </button>
    </nav>

    <!-- ==================== OVERVIEW TAB ==================== -->
    <div class="tab-content active" id="content-overview">
        <div class="container">
            <div class="overview-grid">
                <div class="overview-card">
                    <h3>Upbit Balance</h3>
                    <div class="value" style="color:#3b82f6" id="ov-upbit-balance">-</div>
                </div>
                <div class="overview-card">
                    <h3>Binance Balance</h3>
                    <div class="value" style="color:#00d4ff" id="ov-binance-balance">-</div>
                </div>
                <div class="overview-card">
                    <h3>Active Positions</h3>
                    <div class="value" style="color:#a78bfa" id="ov-positions">0</div>
                    <div class="sub" id="ov-positions-detail">Upbit: 0 / Binance: 0</div>
                </div>
                <div class="overview-card">
                    <h3>Today P&L</h3>
                    <div class="value" id="ov-today-pnl">-</div>
                    <div class="sub" id="ov-today-detail">-</div>
                </div>
            </div>

            <div class="exchange-summary">
                <!-- Upbit Summary -->
                <div class="exchange-box upbit">
                    <h2>Upbit (Spot)</h2>
                    <div id="ov-upbit-positions"><div class="no-data">No positions</div></div>
                </div>
                <!-- Binance Summary -->
                <div class="exchange-box binance">
                    <h2>Binance (Futures)</h2>
                    <div id="ov-binance-positions"><div class="no-data">No positions</div></div>
                </div>
            </div>

            <div class="exchange-summary">
                <div class="exchange-box upbit">
                    <h2>Upbit Recent Trades</h2>
                    <div id="ov-upbit-trades"><div class="no-data">No trades</div></div>
                </div>
                <div class="exchange-box binance">
                    <h2>Binance Recent Trades</h2>
                    <div id="ov-binance-trades"><div class="no-data">No trades</div></div>
                </div>
            </div>

            <footer>Last updated: <span id="ov-timestamp">-</span> | Auto-refresh: 5s</footer>
        </div>
    </div>

    <!-- ==================== UPBIT TAB ==================== -->
    <div class="tab-content upbit-tab" id="content-upbit">
        <div class="container">
            <div class="grid">
                <div class="card">
                    <h2>KRW Balance</h2>
                    <div class="balance upbit-color" id="u-balance">-</div>
                </div>
                <div class="card">
                    <h2>Watchlist</h2>
                    <div id="u-prices"><div class="no-data">Loading...</div></div>
                </div>
            </div>
            <div class="grid">
                <div class="card">
                    <h2>Active Positions</h2>
                    <div id="u-positions"><div class="no-data">No positions</div></div>
                </div>
                <div class="card">
                    <h2>Recent Trades</h2>
                    <div id="u-trades"><div class="no-data">No trades</div></div>
                </div>
            </div>
            <div class="card">
                <h2>Performance</h2>
                <div class="stats-grid">
                    <div class="stat-box"><div class="stat-label">Today</div><div class="stat-value" id="u-stat-today">-</div><div class="stat-label" id="u-stat-today-trades">-</div></div>
                    <div class="stat-box"><div class="stat-label">7 Days</div><div class="stat-value" id="u-stat-week">-</div><div class="stat-label" id="u-stat-week-trades">-</div></div>
                    <div class="stat-box"><div class="stat-label">30 Days</div><div class="stat-value" id="u-stat-month">-</div><div class="stat-label" id="u-stat-month-trades">-</div></div>
                </div>
            </div>
            <div class="card log-container">
                <div class="log-header">
                    <h2>Upbit Logs</h2>
                    <div class="log-controls">
                        <select id="u-log-filter"><option value="ALL">All</option><option value="ERROR">Errors</option><option value="WARNING">Warnings</option></select>
                        <select id="u-log-lines"><option value="50">50</option><option value="100" selected>100</option><option value="200">200</option></select>
                        <button id="u-log-scroll" class="active" onclick="toggleScroll('u')">Auto-scroll</button>
                    </div>
                </div>
                <div class="log-box" id="u-log-box"><div class="no-data">Loading logs...</div></div>
            </div>
        </div>
    </div>

    <!-- ==================== BINANCE TAB ==================== -->
    <div class="tab-content binance-tab" id="content-binance">
        <div class="container">
            <div class="grid">
                <div class="card">
                    <h2>USDT Balance</h2>
                    <div class="balance binance-color" id="b-balance">-</div>
                    <div style="color:#888;margin-top:5px" id="b-mode">-</div>
                </div>
                <div class="card">
                    <h2>Watchlist</h2>
                    <div id="b-prices"><div class="no-data">Loading...</div></div>
                </div>
            </div>
            <div class="grid">
                <div class="card">
                    <h2>Active Positions</h2>
                    <div id="b-positions"><div class="no-data">No positions</div></div>
                </div>
                <div class="card">
                    <h2>Recent Trades</h2>
                    <div id="b-trades"><div class="no-data">No trades</div></div>
                </div>
            </div>
            <div class="card">
                <h2>Performance</h2>
                <div class="stats-grid">
                    <div class="stat-box"><div class="stat-label">Today</div><div class="stat-value" id="b-stat-today">-</div><div class="stat-label" id="b-stat-today-trades">-</div></div>
                    <div class="stat-box"><div class="stat-label">7 Days</div><div class="stat-value" id="b-stat-week">-</div><div class="stat-label" id="b-stat-week-trades">-</div></div>
                    <div class="stat-box"><div class="stat-label">30 Days</div><div class="stat-value" id="b-stat-month">-</div><div class="stat-label" id="b-stat-month-trades">-</div></div>
                </div>
            </div>
            <div class="card log-container">
                <div class="log-header">
                    <h2>Binance Logs</h2>
                    <div class="log-controls">
                        <select id="b-log-filter"><option value="ALL">All</option><option value="ERROR">Errors</option><option value="WARNING">Warnings</option></select>
                        <select id="b-log-lines"><option value="50">50</option><option value="100" selected>100</option><option value="200">200</option></select>
                        <button id="b-log-scroll" class="active" onclick="toggleScroll('b')">Auto-scroll</button>
                    </div>
                </div>
                <div class="log-box" id="b-log-box"><div class="no-data">Loading logs...</div></div>
            </div>
        </div>
    </div>

    <script>
        // ==================== TAB SWITCHING ====================
        let currentTab = 'overview';

        function switchTab(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => {
                el.classList.remove('active-overview', 'active-upbit', 'active-binance');
            });
            document.getElementById('content-' + tab).classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active-' + tab);
            currentTab = tab;
        }

        // ==================== FORMATTERS ====================
        function fmtKRW(num) {
            return Number(num).toLocaleString('ko-KR') + ' KRW';
        }
        function fmtUSDT(num) {
            return Number(num).toFixed(2) + ' USDT';
        }
        function fmtNum(num) {
            return Number(num).toLocaleString('ko-KR');
        }
        function fmtPrice(price) {
            if (price >= 1000) return fmtNum(Math.round(price));
            if (price >= 1) return Number(price).toFixed(2);
            return Number(price).toFixed(4);
        }
        function fmtTime(iso) {
            if (!iso) return '-';
            const d = new Date(iso);
            return d.toLocaleString('ko-KR', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
        }
        function pnlClass(val) { return val >= 0 ? 'positive' : 'negative'; }
        function pnlSign(val) { return val >= 0 ? '+' : ''; }

        // ==================== DATA STATE ====================
        let upbitData = null;
        let binanceData = null;

        // ==================== OVERVIEW UPDATE ====================
        function updateOverview() {
            // Status dots
            document.getElementById('dot-upbit').className = 'status-dot ' + (upbitData ? 'online' : 'offline');
            document.getElementById('dot-binance').className = 'status-dot ' + (binanceData ? 'online' : 'offline');
            document.getElementById('dot-overview').className = 'status-dot ' + ((upbitData || binanceData) ? 'online' : 'offline');

            // Balances
            document.getElementById('ov-upbit-balance').textContent = upbitData ? fmtKRW(upbitData.balance) : 'Offline';
            document.getElementById('ov-binance-balance').textContent = binanceData ? fmtUSDT(binanceData.balance) : 'Offline';

            // Positions count
            const uPos = upbitData ? Object.keys(upbitData.positions || {}).length : 0;
            const bPos = binanceData ? Object.keys(binanceData.positions || {}).length : 0;
            document.getElementById('ov-positions').textContent = uPos + bPos;
            document.getElementById('ov-positions-detail').textContent = `Upbit: ${uPos} / Binance: ${bPos}`;

            // Today PnL
            const uPnl = upbitData?.stats?.today?.pnl || 0;
            const bPnl = binanceData?.stats?.today?.pnl || 0;
            const pnlEl = document.getElementById('ov-today-pnl');
            pnlEl.innerHTML = `<span class="${pnlClass(uPnl)}">${pnlSign(uPnl)}${fmtKRW(uPnl)}</span> / <span class="${pnlClass(bPnl)}">${pnlSign(bPnl)}${fmtUSDT(bPnl)}</span>`;
            document.getElementById('ov-today-detail').textContent =
                `Upbit: ${upbitData?.stats?.today?.trades || 0} trades | Binance: ${binanceData?.stats?.today?.trades || 0} trades`;

            // Upbit positions summary
            renderPositionsSummary('ov-upbit-positions', upbitData?.positions, 'KRW');
            renderPositionsSummary('ov-binance-positions', binanceData?.positions, 'USDT');

            // Recent trades summary
            renderTradesSummary('ov-upbit-trades', upbitData?.recent_trades, 'upbit');
            renderTradesSummary('ov-binance-trades', binanceData?.recent_trades, 'binance');

            document.getElementById('ov-timestamp').textContent = fmtTime(new Date().toISOString());
        }

        function renderPositionsSummary(elId, positions, currency) {
            const el = document.getElementById(elId);
            if (!positions || Object.keys(positions).length === 0) {
                el.innerHTML = '<div class="no-data">No positions</div>';
                return;
            }
            let html = '';
            for (const [sym, pos] of Object.entries(positions)) {
                const pnl = pos.pnl_pct || 0;
                const val = pos.pnl_val || 0;
                const side = pos.side ? `<span class="${pos.side === 'BUY' ? 'side-buy' : 'side-sell'}">${pos.side}</span> ` : '';
                const unit = currency === 'KRW' ? fmtKRW(Math.round(val)) : fmtUSDT(val);
                html += `<div class="price-row">
                    <span class="symbol">${side}${sym}</span>
                    <span class="${pnlClass(pnl)}">${pnlSign(pnl)}${pnl.toFixed(2)}% (${pnlSign(val)}${unit})</span>
                </div>`;
            }
            el.innerHTML = html;
        }

        function renderTradesSummary(elId, trades, exchange) {
            const el = document.getElementById(elId);
            if (!trades || trades.length === 0) {
                el.innerHTML = '<div class="no-data">No trades</div>';
                return;
            }
            let html = '';
            const shown = trades.slice(0, 5);
            for (const t of shown) {
                let coin, pnl, pnlPct, time, reason;
                if (exchange === 'upbit') {
                    coin = t.coin || t.symbol || '-';
                    pnl = t.profit_krw || t.pnl || 0;
                    pnlPct = (t.profit_rate || 0) * 100;
                    time = t.exit_time || t.sell_time || '';
                    reason = t.reason || '';
                } else {
                    coin = (t.symbol || '-').replace('/USDT', '');
                    pnl = t.pnl_amount ?? t.pnl ?? 0;
                    pnlPct = t.pnl_pct ?? 0;
                    time = t.exit_time || t.timestamp || '';
                    reason = t.reason || '';
                }
                const reasonStr = reason ? ` (${reason})` : '';
                const unit = exchange === 'upbit' ? fmtNum(Math.round(pnl)) + ' KRW' : Number(pnl).toFixed(2) + ' USDT';
                html += `<div class="trade-row">
                    <span>${fmtTime(time)}</span>
                    <span class="symbol">${coin}</span>
                    <span class="${pnlClass(pnl)}">${pnlSign(pnl)}${unit} (${pnlSign(pnlPct)}${pnlPct.toFixed(1)}%)${reasonStr}</span>
                </div>`;
            }
            el.innerHTML = html;
        }

        // ==================== UPBIT TAB UPDATE ====================
        function updateUpbitTab() {
            if (!upbitData) return;
            const d = upbitData;

            document.getElementById('u-balance').textContent = fmtKRW(d.balance);

            // Prices
            const pricesEl = document.getElementById('u-prices');
            if (d.prices && Object.keys(d.prices).length > 0) {
                let html = '';
                for (const [coin, info] of Object.entries(d.prices)) {
                    html += `<div class="price-row">
                        <span class="symbol">${coin}</span>
                        <span>${fmtPrice(info.price)} KRW</span>
                        <span class="${pnlClass(info.change)}">${pnlSign(info.change)}${info.change.toFixed(2)}%</span>
                    </div>`;
                }
                pricesEl.innerHTML = html;
            }

            // Positions
            const posEl = document.getElementById('u-positions');
            const positions = Object.entries(d.positions || {});
            if (positions.length > 0) {
                let html = '';
                for (const [coin, pos] of positions) {
                    html += `<div class="position">
                        <div class="position-header">
                            <span class="position-symbol">${coin}</span>
                            <span class="${pnlClass(pos.pnl_val)}">${pnlSign(pos.pnl_pct)}${pos.pnl_pct.toFixed(2)}% (${pnlSign(pos.pnl_val)}${fmtKRW(Math.round(pos.pnl_val))})</span>
                        </div>
                        <div class="position-details">Entry: ${fmtPrice(pos.entry_price)} | Current: ${fmtPrice(pos.current_price)} | Qty: ${pos.quantity}</div>
                    </div>`;
                }
                posEl.innerHTML = html;
            } else {
                posEl.innerHTML = '<div class="no-data">No positions</div>';
            }

            // Trades
            renderTradesSummary('u-trades', d.recent_trades, 'upbit');

            // Stats
            for (const [period, key] of [['today','today'],['week','week'],['month','month']]) {
                const s = d.stats?.[key] || {};
                const el = document.getElementById('u-stat-' + period);
                el.textContent = pnlSign(s.pnl || 0) + fmtKRW(s.pnl || 0);
                el.className = 'stat-value ' + pnlClass(s.pnl || 0);
                document.getElementById('u-stat-' + period + '-trades').textContent = `${s.trades || 0} trades (${s.win_rate || 0}% win)`;
            }
        }

        // ==================== BINANCE TAB UPDATE ====================
        function updateBinanceTab() {
            if (!binanceData) return;
            const d = binanceData;

            document.getElementById('b-balance').textContent = fmtUSDT(d.balance);
            document.getElementById('b-mode').textContent = 'Mode: ' + (d.mode || '-');

            // Prices
            const pricesEl = document.getElementById('b-prices');
            if (d.prices && Object.keys(d.prices).length > 0) {
                let html = '';
                for (const [sym, info] of Object.entries(d.prices)) {
                    const short = sym.replace('/USDT', '');
                    html += `<div class="price-row">
                        <span class="symbol">${short}</span>
                        <span>${fmtPrice(info.price)} USDT</span>
                        <span class="${pnlClass(info.change)}">${pnlSign(info.change)}${info.change.toFixed(2)}%</span>
                    </div>`;
                }
                pricesEl.innerHTML = html;
            }

            // Positions
            const posEl = document.getElementById('b-positions');
            const positions = Object.entries(d.positions || {});
            if (positions.length > 0) {
                let html = '';
                for (const [sym, pos] of positions) {
                    const short = sym.replace('/USDT', '');
                    const side = pos.side || 'BUY';
                    html += `<div class="position">
                        <div class="position-header">
                            <span class="position-symbol"><span class="${side === 'BUY' ? 'side-buy' : 'side-sell'}">${side}</span> ${short}</span>
                            <span class="${pnlClass(pos.pnl_val)}">${pnlSign(pos.pnl_pct)}${pos.pnl_pct.toFixed(2)}% (${pnlSign(pos.pnl_val)}${fmtUSDT(pos.pnl_val)})</span>
                        </div>
                        <div class="position-details">Entry: ${fmtPrice(pos.entry_price)} | Current: ${fmtPrice(pos.current_price)} | Qty: ${pos.quantity}</div>
                    </div>`;
                }
                posEl.innerHTML = html;
            } else {
                posEl.innerHTML = '<div class="no-data">No positions</div>';
            }

            // Trades
            renderTradesSummary('b-trades', d.recent_trades, 'binance');

            // Stats
            for (const [period, key] of [['today','today'],['week','week'],['month','month']]) {
                const s = d.stats?.[key] || {};
                const el = document.getElementById('b-stat-' + period);
                el.textContent = pnlSign(s.pnl || 0) + fmtUSDT(s.pnl || 0);
                el.className = 'stat-value ' + pnlClass(s.pnl || 0);
                document.getElementById('b-stat-' + period + '-trades').textContent = `${s.trades || 0} trades (${s.win_rate || 0}% win)`;
            }
        }

        // ==================== LOGS ====================
        const autoScroll = { u: true, b: true };

        function toggleScroll(prefix) {
            autoScroll[prefix] = !autoScroll[prefix];
            document.getElementById(prefix + '-log-scroll').classList.toggle('active', autoScroll[prefix]);
        }

        function getLogClass(line) {
            if (line.includes('ERROR') || line.includes('[ERROR]')) return 'log-error';
            if (line.includes('WARNING') || line.includes('[WARNING]')) return 'log-warning';
            if (line.includes('SUCCESS') || line.includes('[SUCCESS]') || line.includes('매수') || line.includes('매도')) return 'log-success';
            return 'log-info';
        }

        async function updateLogs(prefix, exchange) {
            try {
                const lines = document.getElementById(prefix + '-log-lines').value;
                const resp = await fetch('/api/logs/' + exchange + '?lines=' + lines);
                const data = await resp.json();
                const filter = document.getElementById(prefix + '-log-filter').value;
                const box = document.getElementById(prefix + '-log-box');

                let filtered = data.logs || [];
                if (filter !== 'ALL') filtered = filtered.filter(l => l.toUpperCase().includes(filter));

                if (filtered.length === 0) {
                    box.innerHTML = '<div class="no-data">No logs</div>';
                    return;
                }

                box.innerHTML = filtered.map(line => {
                    const cls = getLogClass(line);
                    const esc = line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                    return '<div class="log-line ' + cls + '">' + esc + '</div>';
                }).join('');

                if (autoScroll[prefix]) box.scrollTop = box.scrollHeight;
            } catch(e) {
                console.error('Log error:', e);
            }
        }

        // ==================== MAIN LOOP ====================
        async function updateAll() {
            try {
                const resp = await fetch('/api/unified');
                const data = await resp.json();
                upbitData = data.upbit;
                binanceData = data.binance;

                updateOverview();
                updateUpbitTab();
                updateBinanceTab();
            } catch(e) {
                console.error('Update error:', e);
            }
        }

        async function updateAllLogs() {
            if (currentTab === 'upbit' || currentTab === 'overview') {
                updateLogs('u', 'upbit');
            }
            if (currentTab === 'binance' || currentTab === 'overview') {
                updateLogs('b', 'binance');
            }
        }

        updateAll();
        updateAllLogs();
        setInterval(updateAll, 5000);
        setInterval(updateAllLogs, 5000);
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


if __name__ == '__main__':
    print("=" * 50)
    print("CoinTrade Unified Dashboard")
    print("=" * 50)
    print(f"Upbit API:   {UPBIT_API}")
    print(f"Binance API: {BINANCE_API}")
    print(f"Access:      http://0.0.0.0:5002")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5002, debug=False)
