# web_dashboard.py - 웹 브라우저에서 보는 대시보드

from flask import Flask, render_template, jsonify
import pyupbit
import json
import threading
import time
from datetime import datetime
from collections import deque
from config import TRADING_PAIRS

app = Flask(__name__)

# 데이터 저장소
price_history = {symbol: deque(maxlen=100) for symbol in TRADING_PAIRS}
trade_history = deque(maxlen=50)
current_positions = {}

class DataCollector(threading.Thread):
    """백그라운드 데이터 수집"""
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
    
    def run(self):
        while self.running:
            for symbol in TRADING_PAIRS:
                ticker = f"KRW-{symbol}"
                try:
                    price = pyupbit.get_current_price(ticker)
                    if price:
                        price_history[symbol].append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'price': price
                        })
                except:
                    pass
            time.sleep(5)

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('dashboard.html')

@app.route('/api/prices')
def get_prices():
    """실시간 가격 API"""
    data = {}
    for symbol in TRADING_PAIRS:
        ticker = f"KRW-{symbol}"
        try:
            ticker_info = pyupbit.get_ticker(ticker)
            if ticker_info:
                info = ticker_info[0]
                data[symbol] = {
                    'price': info['trade_price'],
                    'change': info['signed_change_rate'] * 100,
                    'volume': info['acc_trade_volume_24h']
                }
        except:
            data[symbol] = {'price': 0, 'change': 0, 'volume': 0}
    
    return jsonify(data)

@app.route('/api/indicators/<symbol>')
def get_indicators(symbol):
    """기술적 지표 API"""
    ticker = f"KRW-{symbol}"
    try:
        df = pyupbit.get_ohlcv(ticker, interval="minute60", count=50)
        if df is not None and len(df) > 14:
            # RSI 계산
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 이동평균
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            ma50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else ma20
            
            return jsonify({
                'rsi': float(rsi),
                'ma20': float(ma20),
                'ma50': float(ma50),
                'current': float(df['close'].iloc[-1])
            })
    except:
        pass
    
    return jsonify({'error': 'Failed to calculate indicators'})

@app.route('/api/chart/<symbol>')
def get_chart_data(symbol):
    """차트 데이터 API"""
    if symbol in price_history:
        return jsonify(list(price_history[symbol]))
    return jsonify([])

# HTML 템플릿 (templates/dashboard.html)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Trading Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            background: #1a1a1a;
            color: #fff;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }
        .card {
            background: #2a2a2a;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .price-card {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            margin: 10px 0;
            background: #333;
            border-radius: 5px;
        }
        .price-up { color: #4caf50; }
        .price-down { color: #f44336; }
        .price-neutral { color: #ffeb3b; }
        h2 { margin-top: 0; color: #64b5f6; }
        .chart-container { height: 300px; }
    </style>
</head>
<body>
    <h1>🤖 업비트 트레이딩 대시보드</h1>
    
    <div class="dashboard">
        <div class="card">
            <h2>📈 실시간 가격</h2>
            <div id="prices"></div>
        </div>
        
        <div class="card">
            <h2>📊 차트</h2>
            <canvas id="priceChart"></canvas>
        </div>
        
        <div class="card">
            <h2>🎯 기술적 지표</h2>
            <div id="indicators"></div>
        </div>
        
        <div class="card">
            <h2>📦 포지션</h2>
            <div id="positions">
                <p>활성 포지션 없음</p>
            </div>
        </div>
    </div>
    
    <script>
        // 차트 초기화
        const ctx = document.getElementById('priceChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: false }
                }
            }
        });
        
        // 가격 업데이트
        function updatePrices() {
            fetch('/api/prices')
                .then(response => response.json())
                .then(data => {
                    let html = '';
                    for (const [symbol, info] of Object.entries(data)) {
                        const changeClass = info.change > 0 ? 'price-up' : 
                                          info.change < 0 ? 'price-down' : 'price-neutral';
                        const arrow = info.change > 0 ? '▲' : info.change < 0 ? '▼' : '=';
                        
                        html += `
                            <div class="price-card">
                                <strong>${symbol}</strong>
                                <span>${info.price.toLocaleString()} KRW</span>
                                <span class="${changeClass}">${arrow} ${Math.abs(info.change).toFixed(2)}%</span>
                            </div>
                        `;
                    }
                    document.getElementById('prices').innerHTML = html;
                });
        }
        
        // 지표 업데이트
        function updateIndicators() {
            const symbols = ['ETH', 'SOL', 'XRP'];
            let html = '';
            
            symbols.forEach(symbol => {
                fetch(`/api/indicators/${symbol}`)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.error) {
                            const rsiClass = data.rsi > 70 ? 'price-down' : 
                                           data.rsi < 30 ? 'price-up' : 'price-neutral';
                            
                            html += `
                                <div class="price-card">
                                    <strong>${symbol}</strong>
                                    <span class="${rsiClass}">RSI: ${data.rsi.toFixed(1)}</span>
                                    <span>MA20: ${data.ma20.toLocaleString()}</span>
                                </div>
                            `;
                            document.getElementById('indicators').innerHTML = html;
                        }
                    });
            });
        }
        
        // 주기적 업데이트
        setInterval(updatePrices, 2000);
        setInterval(updateIndicators, 5000);
        
        // 초기 로드
        updatePrices();
        updateIndicators();
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    # 데이터 수집 시작
    collector = DataCollector()
    collector.start()
    
    # templates 폴더 생성
    import os
    os.makedirs('templates', exist_ok=True)
    
    # HTML 템플릿 저장
    with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(HTML_TEMPLATE)
    
    # 웹 서버 시작
    print("🌐 웹 대시보드 시작: http://localhost:5000")
    app.run(debug=False, port=5000)