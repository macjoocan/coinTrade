# upbit_web_dashboard.py - Upbit Web Dashboard
# Flask 기반 웹 대시보드 (NAS/Docker에서 실행)

import os
import sys
import json
import pyupbit
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
import logging

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================
# 경로 설정
# ============================================================

def get_base_path():
    """기본 경로"""
    if os.path.exists('/app/data'):
        return '/app'
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)

BASE_PATH = get_base_path()
DATA_PATH = '/app/data' if os.path.exists('/app/data') else BASE_PATH

def load_env():
    """.env 파일에서 환경변수 로드"""
    env_file = os.path.join(BASE_PATH, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env()

# ============================================================
# 데이터 로드 함수
# ============================================================

def load_settings():
    """설정 파일 로드"""
    for path in [os.path.join(BASE_PATH, 'settings.json'), os.path.join(DATA_PATH, 'settings.json')]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}

def load_positions():
    """포지션 파일 로드"""
    for path in [os.path.join(DATA_PATH, 'active_positions.json'), os.path.join(BASE_PATH, 'active_positions.json')]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('positions', {})
            except:
                pass
    return {}

def load_history():
    """거래 히스토리 로드"""
    for path in [os.path.join(DATA_PATH, 'trade_history.json'), os.path.join(BASE_PATH, 'trade_history.json')]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
    return []

# ============================================================
# 거래소 API
# ============================================================

_upbit = None

def get_upbit():
    """업비트 인스턴스"""
    global _upbit
    if _upbit is None:
        access_key = os.getenv('UPBIT_ACCESS_KEY', '')
        secret_key = os.getenv('UPBIT_SECRET_KEY', '')
        if access_key and secret_key:
            _upbit = pyupbit.Upbit(access_key, secret_key)
        else:
            # settings.json에서 시도
            settings = load_settings()
            ak = settings.get('api', {}).get('access_key', '')
            sk = settings.get('api', {}).get('secret_key', '')
            if ak and sk:
                _upbit = pyupbit.Upbit(ak, sk)
    return _upbit

def get_balance():
    """KRW 잔고 조회"""
    try:
        upbit = get_upbit()
        if upbit:
            return upbit.get_balance("KRW")
        return 0
    except Exception as e:
        logger.error(f"Balance error: {e}")
        return 0

def get_prices(coins):
    """가격 조회"""
    prices = {}
    try:
        tickers = ["KRW-" + c for c in coins]
        ticker_data = pyupbit.get_current_price(tickers)
        if isinstance(ticker_data, dict):
            for ticker, price in ticker_data.items():
                coin = ticker.replace("KRW-", "")
                # 전일 대비 변동률
                try:
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                    if df is not None and len(df) >= 2:
                        prev_close = df.iloc[-2]['close']
                        change = ((price - prev_close) / prev_close) * 100
                    else:
                        change = 0
                except:
                    change = 0
                prices[coin] = {'price': price, 'change': round(change, 2)}
    except Exception as e:
        logger.error(f"Price error: {e}")
    return prices

# ============================================================
# 통계 계산
# ============================================================

def calculate_stats(days):
    """기간별 통계"""
    history = load_history()
    if not history:
        return {'trades': 0, 'wins': 0, 'win_rate': 0, 'pnl': 0, 'avg_pnl': 0}

    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for trade in history:
        try:
            t = trade.get('exit_time') or trade.get('sell_time', '')
            if t:
                trade_time = datetime.fromisoformat(t)
                if trade_time >= cutoff:
                    filtered.append(trade)
        except:
            continue

    if not filtered:
        return {'trades': 0, 'wins': 0, 'win_rate': 0, 'pnl': 0, 'avg_pnl': 0}

    wins = [t for t in filtered if (t.get('profit_rate', 0) or t.get('pnl', 0)) > 0]
    total_pnl = sum(t.get('profit_krw', 0) or t.get('pnl', 0) for t in filtered)

    return {
        'trades': len(filtered),
        'wins': len(wins),
        'win_rate': round(len(wins) / len(filtered) * 100, 1),
        'pnl': round(total_pnl),
        'avg_pnl': round(total_pnl / len(filtered))
    }

# ============================================================
# API 엔드포인트
# ============================================================

@app.route('/api/logs')
def api_logs():
    """로그 데이터 API"""
    lines_count = int(request.args.get('lines', 100))
    log_paths = [
        os.path.join(DATA_PATH, 'trading.log'),
        os.path.join(BASE_PATH, 'trading.log'),
    ]
    for path in log_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                recent = all_lines[-lines_count:]
                return jsonify({'logs': [line.rstrip() for line in recent], 'total': len(all_lines)})
            except Exception as e:
                return jsonify({'logs': [f'Error reading log: {e}'], 'total': 0})
    return jsonify({'logs': ['No log file found'], 'total': 0})

@app.route('/api/data')
def api_data():
    """전체 데이터 API"""
    settings = load_settings()
    positions = load_positions()
    history = load_history()

    coins = settings.get('trading', {}).get('pairs', ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'])
    prices = get_prices(coins)
    balance = get_balance()

    # 포지션에 현재가 추가
    positions_with_pnl = {}
    for coin, pos in positions.items():
        current_price = prices.get(coin, {}).get('price', 0)
        entry_price = pos.get('entry_price', 0)
        quantity = pos.get('quantity', 0)

        if current_price and entry_price:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_val = (current_price - entry_price) * quantity
        else:
            pnl_pct = 0
            pnl_val = 0

        positions_with_pnl[coin] = {
            **pos,
            'current_price': current_price,
            'pnl_pct': round(pnl_pct, 2),
            'pnl_val': round(pnl_val)
        }

    # 최근 거래 10개
    recent_trades = sorted(history,
        key=lambda x: x.get('exit_time') or x.get('sell_time', ''), reverse=True)[:10]

    return jsonify({
        'balance': round(balance),
        'prices': prices,
        'positions': positions_with_pnl,
        'recent_trades': recent_trades,
        'stats': {
            'today': calculate_stats(1),
            'week': calculate_stats(7),
            'month': calculate_stats(30)
        },
        'settings': {
            'stop_loss': settings.get('risk', {}).get('stop_loss', 0.015),
            'max_positions': settings.get('risk', {}).get('max_positions', 5),
            'max_position_size': settings.get('risk', {}).get('max_position_size', 0.2),
            'daily_loss_limit': settings.get('risk', {}).get('daily_loss_limit', 0.03)
        },
        'timestamp': datetime.now().isoformat()
    })

# ============================================================
# HTML 템플릿
# ============================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upbit Trader Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }

        header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
        }
        header h1 { color: #3b82f6; font-size: 2em; }
        header .info { color: #888; margin-top: 10px; }

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
            color: #3b82f6;
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .balance { font-size: 2em; color: #3b82f6; font-weight: bold; }

        .price-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .price-row:last-child { border-bottom: none; }
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

        .trade-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.9em;
        }

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

        .settings-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
        }

        .no-data { color: #666; text-align: center; padding: 20px; }

        .log-container { margin-top: 20px; }
        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .log-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .log-controls button {
            background: rgba(59,130,246,0.2);
            color: #3b82f6;
            border: 1px solid rgba(59,130,246,0.3);
            padding: 4px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
        }
        .log-controls button:hover { background: rgba(59,130,246,0.3); }
        .log-controls button.active { background: rgba(59,130,246,0.4); }
        .log-controls select {
            background: rgba(255,255,255,0.1);
            color: #eee;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.85em;
        }
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
            .grid { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Upbit Trader Dashboard</h1>
            <div class="info">
                <span id="timestamp">Loading...</span> |
                Auto-refresh: 5s
            </div>
        </header>

        <div class="grid">
            <!-- Balance -->
            <div class="card">
                <h2>KRW Balance</h2>
                <div class="balance" id="balance">0 KRW</div>
            </div>

            <!-- Prices -->
            <div class="card">
                <h2>Watchlist</h2>
                <div id="prices">
                    <div class="no-data">Loading prices...</div>
                </div>
            </div>
        </div>

        <div class="grid">
            <!-- Positions -->
            <div class="card">
                <h2>Active Positions</h2>
                <div id="positions">
                    <div class="no-data">No active positions</div>
                </div>
            </div>

            <!-- Recent Trades -->
            <div class="card">
                <h2>Recent Trades</h2>
                <div id="trades">
                    <div class="no-data">No trade history</div>
                </div>
            </div>
        </div>

        <!-- Stats -->
        <div class="card">
            <h2>Performance Statistics</h2>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Today</div>
                    <div class="stat-value" id="stat-today-pnl">0</div>
                    <div class="stat-label" id="stat-today-trades">0 trades</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">7 Days</div>
                    <div class="stat-value" id="stat-week-pnl">0</div>
                    <div class="stat-label" id="stat-week-trades">0 trades</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">30 Days</div>
                    <div class="stat-value" id="stat-month-pnl">0</div>
                    <div class="stat-label" id="stat-month-trades">0 trades</div>
                </div>
            </div>
        </div>

        <!-- Settings -->
        <div class="card" style="margin-top: 20px;">
            <h2>Risk Settings</h2>
            <div class="settings-row">
                <span>Stop Loss</span>
                <span id="setting-sl" class="negative">1.5%</span>
            </div>
            <div class="settings-row">
                <span>Max Position Size</span>
                <span id="setting-size">20%</span>
            </div>
            <div class="settings-row">
                <span>Max Positions</span>
                <span id="setting-max-pos">5</span>
            </div>
            <div class="settings-row">
                <span>Daily Loss Limit</span>
                <span id="setting-daily" class="negative">3%</span>
            </div>
        </div>

        <!-- Logs -->
        <div class="card log-container">
            <div class="log-header">
                <h2>Trading Logs</h2>
                <div class="log-controls">
                    <select id="log-filter">
                        <option value="ALL">All</option>
                        <option value="ERROR">Errors</option>
                        <option value="WARNING">Warnings</option>
                    </select>
                    <select id="log-lines">
                        <option value="50">50 lines</option>
                        <option value="100" selected>100 lines</option>
                        <option value="200">200 lines</option>
                        <option value="500">500 lines</option>
                    </select>
                    <button id="log-autoscroll" class="active" onclick="toggleAutoScroll()">Auto-scroll</button>
                </div>
            </div>
            <div class="log-box" id="log-box">
                <div class="no-data">Loading logs...</div>
            </div>
        </div>

        <footer>
            Upbit Trader v2.3 | Web Dashboard
        </footer>
    </div>

    <script>
        function formatNumber(num) {
            return Number(num).toLocaleString('ko-KR');
        }

        function formatTime(isoString) {
            if (!isoString) return '-';
            const d = new Date(isoString);
            return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        }

        function formatPrice(price) {
            if (price >= 1000) return formatNumber(Math.round(price));
            if (price >= 1) return price.toFixed(2);
            return price.toFixed(4);
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();

                document.getElementById('timestamp').textContent = formatTime(data.timestamp);
                document.getElementById('balance').textContent = formatNumber(data.balance) + ' KRW';

                // Prices
                const pricesEl = document.getElementById('prices');
                if (Object.keys(data.prices).length > 0) {
                    let html = '';
                    for (const [coin, info] of Object.entries(data.prices)) {
                        const changeClass = info.change >= 0 ? 'positive' : 'negative';
                        const sign = info.change >= 0 ? '+' : '';
                        html += `
                            <div class="price-row">
                                <span class="symbol">${coin}</span>
                                <span>${formatPrice(info.price)} KRW</span>
                                <span class="${changeClass}">${sign}${info.change.toFixed(2)}%</span>
                            </div>
                        `;
                    }
                    pricesEl.innerHTML = html;
                }

                // Positions
                const positionsEl = document.getElementById('positions');
                const positions = Object.entries(data.positions);
                if (positions.length > 0) {
                    let html = '';
                    for (const [coin, pos] of positions) {
                        const pnlClass = pos.pnl_val >= 0 ? 'positive' : 'negative';
                        const sign = pos.pnl_val >= 0 ? '+' : '';
                        html += `
                            <div class="position">
                                <div class="position-header">
                                    <span class="position-symbol">${coin}</span>
                                    <span class="${pnlClass}">${sign}${pos.pnl_pct.toFixed(2)}% (${sign}${formatNumber(pos.pnl_val)} KRW)</span>
                                </div>
                                <div class="position-details">
                                    Entry: ${formatPrice(pos.entry_price)} | Current: ${formatPrice(pos.current_price)} | Qty: ${pos.quantity}
                                </div>
                            </div>
                        `;
                    }
                    positionsEl.innerHTML = html;
                } else {
                    positionsEl.innerHTML = '<div class="no-data">No active positions</div>';
                }

                // Recent Trades
                const tradesEl = document.getElementById('trades');
                if (data.recent_trades.length > 0) {
                    let html = '';
                    for (const trade of data.recent_trades) {
                        const coin = trade.coin || trade.symbol || '-';
                        const pnl = trade.profit_krw || trade.pnl || 0;
                        const rate = trade.profit_rate || 0;
                        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                        const sign = pnl >= 0 ? '+' : '';
                        const exitTime = trade.exit_time || trade.sell_time || '';
                        html += `
                            <div class="trade-row">
                                <span>${formatTime(exitTime)}</span>
                                <span class="symbol">${coin}</span>
                                <span class="${pnlClass}">${sign}${formatNumber(Math.round(pnl))} KRW (${sign}${(rate*100).toFixed(1)}%)</span>
                            </div>
                        `;
                    }
                    tradesEl.innerHTML = html;
                } else {
                    tradesEl.innerHTML = '<div class="no-data">No trade history</div>';
                }

                // Stats
                const updateStat = (period, stats) => {
                    const pnlEl = document.getElementById(`stat-${period}-pnl`);
                    const tradesEl = document.getElementById(`stat-${period}-trades`);
                    const sign = stats.pnl >= 0 ? '+' : '';
                    pnlEl.textContent = sign + formatNumber(stats.pnl) + ' KRW';
                    pnlEl.className = 'stat-value ' + (stats.pnl >= 0 ? 'positive' : 'negative');
                    tradesEl.textContent = `${stats.trades} trades (${stats.win_rate}% win)`;
                };
                updateStat('today', data.stats.today);
                updateStat('week', data.stats.week);
                updateStat('month', data.stats.month);

                // Settings
                document.getElementById('setting-sl').textContent = (data.settings.stop_loss * 100).toFixed(1) + '%';
                document.getElementById('setting-size').textContent = (data.settings.max_position_size * 100).toFixed(0) + '%';
                document.getElementById('setting-max-pos').textContent = data.settings.max_positions;
                document.getElementById('setting-daily').textContent = (data.settings.daily_loss_limit * 100).toFixed(0) + '%';

            } catch (error) {
                console.error('Update error:', error);
            }
        }

        // === Logs ===
        let autoScroll = true;

        function toggleAutoScroll() {
            autoScroll = !autoScroll;
            document.getElementById('log-autoscroll').classList.toggle('active', autoScroll);
        }

        function getLogClass(line) {
            if (line.includes('ERROR')) return 'log-error';
            if (line.includes('WARNING')) return 'log-warning';
            if (line.includes('SUCCESS') || line.includes('매수') || line.includes('매도')) return 'log-success';
            return 'log-info';
        }

        async function updateLogs() {
            try {
                const lines = document.getElementById('log-lines').value;
                const response = await fetch('/api/logs?lines=' + lines);
                const data = await response.json();
                const filter = document.getElementById('log-filter').value;
                const logBox = document.getElementById('log-box');

                let filtered = data.logs;
                if (filter !== 'ALL') {
                    filtered = filtered.filter(l => l.toUpperCase().includes(filter));
                }

                if (filtered.length === 0) {
                    logBox.innerHTML = '<div class="no-data">No logs matching filter</div>';
                    return;
                }

                logBox.innerHTML = filtered.map(line => {
                    const cls = getLogClass(line);
                    const escaped = line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                    return '<div class="log-line ' + cls + '">' + escaped + '</div>';
                }).join('');

                if (autoScroll) logBox.scrollTop = logBox.scrollHeight;
            } catch (e) {
                console.error('Log update error:', e);
            }
        }

        updateDashboard();
        updateLogs();
        setInterval(updateDashboard, 5000);
        setInterval(updateLogs, 5000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("=" * 50)
    print("Upbit Trader Web Dashboard")
    print("=" * 50)
    print(f"Data path: {DATA_PATH}")
    print(f"Access: http://0.0.0.0:5001")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=False)
