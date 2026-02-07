# binance_web_dashboard.py - Binance Futures Web Dashboard
# Flask 기반 웹 대시보드 (NAS/Docker에서 실행)

import os
import sys
import json
import ccxt
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify
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
    # Docker 환경
    if os.path.exists('/app/data'):
        return '/app'
    # exe 환경
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # 개발 환경
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
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

load_env()

# ============================================================
# 데이터 로드 함수
# ============================================================

def load_settings():
    """설정 파일 로드"""
    paths = [
        os.path.join(BASE_PATH, 'binance_settings.json'),
        os.path.join(DATA_PATH, 'binance_settings.json'),
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return {}

def load_positions():
    """포지션 파일 로드"""
    paths = [
        os.path.join(DATA_PATH, 'binance_positions.json'),
        os.path.join(BASE_PATH, 'binance_positions.json'),
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('positions', {})
    return {}

def load_history():
    """거래 히스토리 로드"""
    paths = [
        os.path.join(DATA_PATH, 'binance_history.json'),
        os.path.join(BASE_PATH, 'binance_history.json'),
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return []

# ============================================================
# 거래소 API
# ============================================================

_exchange = None

def get_exchange():
    """거래소 인스턴스"""
    global _exchange
    if _exchange is None:
        api_key = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_API_SECRET', '')

        _exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
            }
        })

        if api_key:
            try:
                _exchange.load_time_difference()
            except:
                pass

    return _exchange

def get_balance():
    """잔고 조회"""
    try:
        settings = load_settings()
        mode = settings.get('mode', 'simulation')

        if mode == 'live':
            exchange = get_exchange()
            balance = exchange.fetch_balance()
            return balance['USDT']['free']
        else:
            return settings.get('simulation', {}).get('initial_balance', 10000)
    except Exception as e:
        logger.error(f"Balance error: {e}")
        return 0

def get_prices(symbols):
    """가격 조회"""
    prices = {}
    try:
        exchange = get_exchange()
        for symbol in symbols:
            try:
                ticker = exchange.fetch_ticker(symbol)
                prices[symbol] = {
                    'price': ticker['last'],
                    'change': ticker.get('percentage', 0) or 0
                }
            except:
                prices[symbol] = {'price': 0, 'change': 0}
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
            t = trade.get('exit_time') or trade.get('timestamp', '')
            if t:
                trade_time = datetime.fromisoformat(t)
                if trade_time >= cutoff:
                    filtered.append(trade)
        except:
            continue

    if not filtered:
        return {'trades': 0, 'wins': 0, 'win_rate': 0, 'pnl': 0, 'avg_pnl': 0}

    wins = [t for t in filtered if (t.get('pnl_amount') or t.get('pnl', 0)) > 0]
    total_pnl = sum(t.get('pnl_amount') or t.get('pnl', 0) for t in filtered)

    return {
        'trades': len(filtered),
        'wins': len(wins),
        'win_rate': round(len(wins) / len(filtered) * 100, 1) if filtered else 0,
        'pnl': round(total_pnl, 2),
        'avg_pnl': round(total_pnl / len(filtered), 2) if filtered else 0
    }

# ============================================================
# API 엔드포인트
# ============================================================

@app.route('/api/logs')
def api_logs():
    """로그 데이터 API"""
    from flask import request
    lines_count = int(request.args.get('lines', 100))
    log_paths = [
        os.path.join(DATA_PATH, 'binance_trading.log'),
        os.path.join(BASE_PATH, 'binance_trading.log'),
    ]
    for path in log_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                # 마지막 N줄만 반환
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

    symbols = settings.get('trading', {}).get('symbols', ['BTC/USDT', 'ETH/USDT'])
    prices = get_prices(symbols)
    balance = get_balance()

    # 포지션에 현재가 추가
    positions_with_pnl = {}
    for symbol, pos in positions.items():
        current_price = prices.get(symbol, {}).get('price', 0)
        entry_price = pos.get('entry_price', 0)
        quantity = pos.get('quantity', 0)
        side = pos.get('side', 'BUY')

        if current_price and entry_price:
            if side == 'BUY':
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                pnl_val = (current_price - entry_price) * quantity
            else:
                pnl_pct = ((entry_price - current_price) / entry_price) * 100
                pnl_val = (entry_price - current_price) * quantity
        else:
            pnl_pct = 0
            pnl_val = 0

        positions_with_pnl[symbol] = {
            **pos,
            'current_price': current_price,
            'pnl_pct': round(pnl_pct, 2),
            'pnl_val': round(pnl_val, 2)
        }

    # 최근 거래 5개
    recent_trades = sorted(history, key=lambda x: x.get('exit_time') or x.get('timestamp', ''), reverse=True)[:5]

    return jsonify({
        'balance': round(balance, 2),
        'mode': settings.get('mode', 'simulation'),
        'prices': prices,
        'positions': positions_with_pnl,
        'recent_trades': recent_trades,
        'stats': {
            'today': calculate_stats(1),
            'week': calculate_stats(7),
            'month': calculate_stats(30)
        },
        'settings': {
            'leverage': settings.get('risk', {}).get('leverage', 3),
            'stop_loss': settings.get('risk', {}).get('stop_loss', 0.02),
            'take_profit': settings.get('risk', {}).get('take_profit', 0.04),
            'max_positions': settings.get('risk', {}).get('max_positions', 4)
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
    <title>Binance Trader Dashboard</title>
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
        header h1 { color: #00d4ff; font-size: 2em; }
        header .info { color: #888; margin-top: 10px; }
        .mode-live { color: #00ff88; }
        .mode-simulation { color: #ffaa00; }

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
            color: #00d4ff;
            font-size: 1.1em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .balance { font-size: 2em; color: #00ff88; font-weight: bold; }

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
        .side-buy { color: #00ff88; }
        .side-sell { color: #ff4444; }
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

        .log-container {
            margin-top: 20px;
        }
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
            background: rgba(0,212,255,0.2);
            color: #00d4ff;
            border: 1px solid rgba(0,212,255,0.3);
            padding: 4px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
        }
        .log-controls button:hover { background: rgba(0,212,255,0.3); }
        .log-controls button.active { background: rgba(0,212,255,0.4); }
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
            <h1>Binance Futures Dashboard</h1>
            <div class="info">
                <span id="timestamp">Loading...</span> |
                Mode: <span id="mode" class="mode-simulation">-</span> |
                Auto-refresh: 5s
            </div>
        </header>

        <div class="grid">
            <!-- Balance -->
            <div class="card">
                <h2>Account Balance</h2>
                <div class="balance" id="balance">0.00 USDT</div>
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
                    <div class="stat-value" id="stat-today-pnl">0.00</div>
                    <div class="stat-label" id="stat-today-trades">0 trades</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">7 Days</div>
                    <div class="stat-value" id="stat-week-pnl">0.00</div>
                    <div class="stat-label" id="stat-week-trades">0 trades</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">30 Days</div>
                    <div class="stat-value" id="stat-month-pnl">0.00</div>
                    <div class="stat-label" id="stat-month-trades">0 trades</div>
                </div>
            </div>
        </div>

        <!-- Settings -->
        <div class="card" style="margin-top: 20px;">
            <h2>Risk Settings</h2>
            <div class="settings-row">
                <span>Leverage</span>
                <span id="setting-leverage">3x</span>
            </div>
            <div class="settings-row">
                <span>Stop Loss</span>
                <span id="setting-sl" class="negative">2.0%</span>
            </div>
            <div class="settings-row">
                <span>Take Profit</span>
                <span id="setting-tp" class="positive">4.0%</span>
            </div>
            <div class="settings-row">
                <span>Max Positions</span>
                <span id="setting-max-pos">4</span>
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
                        <option value="SUCCESS">Success</option>
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
            Binance Trader v2.3 | Web Dashboard
        </footer>
    </div>

    <script>
        function formatNumber(num, decimals = 2) {
            return Number(num).toFixed(decimals);
        }

        function formatTime(isoString) {
            if (!isoString) return '-';
            const d = new Date(isoString);
            return d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();

                // Timestamp & Mode
                document.getElementById('timestamp').textContent = formatTime(data.timestamp);
                const modeEl = document.getElementById('mode');
                modeEl.textContent = data.mode.toUpperCase();
                modeEl.className = data.mode === 'live' ? 'mode-live' : 'mode-simulation';

                // Balance
                document.getElementById('balance').textContent = formatNumber(data.balance) + ' USDT';

                // Prices
                const pricesEl = document.getElementById('prices');
                if (Object.keys(data.prices).length > 0) {
                    let html = '';
                    for (const [symbol, info] of Object.entries(data.prices)) {
                        const shortSymbol = symbol.replace('/USDT', '');
                        const changeClass = info.change >= 0 ? 'positive' : 'negative';
                        const sign = info.change >= 0 ? '+' : '';
                        const price = info.price > 1000 ? formatNumber(info.price) : info.price.toFixed(4);
                        html += `
                            <div class="price-row">
                                <span class="symbol">${shortSymbol}</span>
                                <span>${price}</span>
                                <span class="${changeClass}">${sign}${formatNumber(info.change)}%</span>
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
                    for (const [symbol, pos] of positions) {
                        const shortSymbol = symbol.replace('/USDT', '');
                        const sideClass = pos.side === 'BUY' ? 'side-buy' : 'side-sell';
                        const pnlClass = pos.pnl_val >= 0 ? 'positive' : 'negative';
                        const sign = pos.pnl_val >= 0 ? '+' : '';
                        html += `
                            <div class="position">
                                <div class="position-header">
                                    <span class="position-symbol">${shortSymbol}</span>
                                    <span class="${sideClass}">${pos.side}</span>
                                    <span class="${pnlClass}">${sign}${formatNumber(pos.pnl_pct)}% (${sign}${formatNumber(pos.pnl_val)} USDT)</span>
                                </div>
                                <div class="position-details">
                                    Entry: ${pos.entry_price?.toFixed(4)} | Current: ${pos.current_price?.toFixed(4)} | Qty: ${pos.quantity}
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
                        const shortSymbol = trade.symbol?.replace('/USDT', '') || '-';
                        const sideClass = trade.side === 'BUY' ? 'side-buy' : 'side-sell';
                        const pnl = trade.pnl_amount ?? trade.pnl ?? 0;
                        const pnlPct = trade.pnl_pct ?? 0;
                        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
                        const sign = pnl >= 0 ? '+' : '';
                        const tradeTime = trade.exit_time || trade.timestamp || '';
                        const reason = trade.reason ? ` (${trade.reason})` : '';
                        html += `
                            <div class="trade-row">
                                <span>${formatTime(tradeTime)}</span>
                                <span class="symbol">${shortSymbol}</span>
                                <span class="${sideClass}">${trade.side}</span>
                                <span class="${pnlClass}">${sign}${formatNumber(pnl)} USDT (${sign}${formatNumber(pnlPct)}%)${reason}</span>
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
                    pnlEl.textContent = sign + formatNumber(stats.pnl) + ' USDT';
                    pnlEl.className = 'stat-value ' + (stats.pnl >= 0 ? 'positive' : 'negative');
                    tradesEl.textContent = `${stats.trades} trades (${stats.win_rate}% win)`;
                };
                updateStat('today', data.stats.today);
                updateStat('week', data.stats.week);
                updateStat('month', data.stats.month);

                // Settings
                document.getElementById('setting-leverage').textContent = data.settings.leverage + 'x';
                document.getElementById('setting-sl').textContent = (data.settings.stop_loss * 100).toFixed(1) + '%';
                document.getElementById('setting-tp').textContent = (data.settings.take_profit * 100).toFixed(1) + '%';
                document.getElementById('setting-max-pos').textContent = data.settings.max_positions;

            } catch (error) {
                console.error('Update error:', error);
            }
        }

        // === 로그 관련 ===
        let autoScroll = true;

        function toggleAutoScroll() {
            autoScroll = !autoScroll;
            const btn = document.getElementById('log-autoscroll');
            btn.classList.toggle('active', autoScroll);
        }

        function getLogClass(line) {
            if (line.includes('[ERROR]')) return 'log-error';
            if (line.includes('[WARNING]')) return 'log-warning';
            if (line.includes('[SUCCESS]')) return 'log-success';
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
                    filtered = filtered.filter(l => l.includes('[' + filter + ']'));
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

                if (autoScroll) {
                    logBox.scrollTop = logBox.scrollHeight;
                }
            } catch (e) {
                console.error('Log update error:', e);
            }
        }

        // 초기 로드 + 5초마다 갱신
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
    """메인 페이지"""
    return render_template_string(HTML_TEMPLATE)

# ============================================================
# 메인
# ============================================================

if __name__ == '__main__':
    print("=" * 50)
    print("Binance Futures Web Dashboard")
    print("=" * 50)
    print(f"Data path: {DATA_PATH}")
    print(f"Access: http://0.0.0.0:5000")
    print("=" * 50)

    # Flask 서버 시작 (0.0.0.0으로 외부 접속 허용)
    app.run(host='0.0.0.0', port=5000, debug=False)
