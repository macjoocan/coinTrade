# dashboard.py - 분석/예측 패널 로직 보강 버전

import os
import time
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import deque
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from dotenv import load_dotenv
from trade_history_manager import TradeHistoryManager
from config import TRADING_PAIRS, RISK_CONFIG, apply_preset, ACTIVE_PRESET
from market_condition_check import MarketAnalyzer

# 분석 도구들 가져오기
try:
    from multi_timeframe_analyzer import MultiTimeframeAnalyzer
    from ml_signal_generator import MLSignalGenerator
except ImportError:
    MultiTimeframeAnalyzer = None
    MLSignalGenerator = None

# 환경 변수 및 프리셋 로드
load_dotenv()
apply_preset(ACTIVE_PRESET)
console = Console()

class MarketDataCache:
    """시장 데이터 캐싱 및 분석 도구 통합 관리"""
    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.top_movers = {'gainers': [], 'losers': []}
        self.last_movers_update = datetime.now() - timedelta(minutes=10)
        self.market_analyzer = MarketAnalyzer()
        
        # ✅ 분석기 인스턴스를 한 번만 생성하여 성능 저하 방지
        self.mtf_analyzer = MultiTimeframeAnalyzer() if MultiTimeframeAnalyzer else None
        self.ml_generator = MLSignalGenerator() if MLSignalGenerator else None
        
    def get_prices_batch(self, tickers):
        try:
            full_tickers = [f"KRW-{t}" for t in tickers]
            prices = pyupbit.get_current_price(full_tickers)
            if isinstance(prices, dict): return prices
            elif isinstance(prices, float): return {f"KRW-{tickers[0]}": prices}
            return {}
        except: return {}

    def get_rsi(self, ticker):
        now = datetime.now()
        cache_key = f"{ticker}_rsi"
        if cache_key in self.last_update and (now - self.last_update[cache_key]).total_seconds() < 60:
            return self.cache.get(cache_key, 50)
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is not None:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                self.cache[cache_key] = rsi; self.last_update[cache_key] = now
                return rsi
        except: pass
        return 50
    def get_top_movers_optimized(self):
        """✅ 수정: 요청 개수를 줄여 안정성 확보 및 에러 방지"""
        now = datetime.now()
        
        # 데이터가 있고 5분이 안 지났으면 기존 데이터 사용 (캐시)
        if self.top_movers['gainers'] and (now - self.last_movers_update).total_seconds() < 300:
            return self.top_movers
            
        try:
            # 1. KRW 마켓 코인 목록 조회
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            if not all_tickers: return self.top_movers
            
            # 2. 성능을 위해 상위 50개 코인 정보만 우선적으로 가져옴
            target_tickers = all_tickers[:50] 
            tickers_data = pyupbit.get_ticker(target_tickers)
            
            if not tickers_data:
                return self.top_movers

            market_data = []
            for data in tickers_data:
                try:
                    # change 값이 None인 경우를 대비해 0으로 처리
                    change = data.get('signed_change_rate', 0)
                    if change is None: change = 0
                    
                    market_data.append({
                        'symbol': data['market'].replace('KRW-', ''),
                        'price': data['trade_price'],
                        'change': change * 100
                    })
                except: continue
            
            if market_data:
                # 3. 등락률 순 정렬 (오류 방지를 위해 0 기본값 설정)
                market_data.sort(key=lambda x: x.get('change', 0), reverse=True)
                
                self.top_movers = {
                    'gainers': market_data[:5],
                    'losers': market_data[-5:][::-1]
                }
                self.last_movers_update = now # 성공 시에만 시간 업데이트
                
        except Exception as e:
            # 오류 발생 시 로그를 남기지 않고 조용히 넘어가서 화면 멈춤 방지
            pass
            
        return self.top_movers
    

class TradingDashboard:
    def __init__(self):
        self.layout = Layout()
        self.cache = MarketDataCache()
        self.trade_history = TradeHistoryManager()
        self.api_calls = deque(maxlen=100)
        
        # API 초기화
        access = os.getenv("UPBIT_ACCESS_KEY"); secret = os.getenv("UPBIT_SECRET_KEY")
        self.upbit = pyupbit.Upbit(access, secret) if access and secret else None
            
        self.total_assets = 0
        self.last_asset_update = datetime.now() - timedelta(minutes=1)
        self.setup_layout()

    def setup_layout(self):
        # 화면 구조 설정
        self.layout.split(Layout(name="header", size=3), Layout(name="main"), Layout(name="stats", size=10), Layout(name="footer", size=3))
        self.layout["main"].split_row(Layout(name="left", ratio=1), Layout(name="center", ratio=1), Layout(name="right", ratio=1))
        self.layout["left"].split(Layout(name="watchlist", ratio=3), Layout(name="recent_trades", ratio=2))
        self.layout["center"].split(Layout(name="market_movers", ratio=1), Layout(name="active_positions", ratio=1))
        self.layout["right"].split(Layout(name="analysis", ratio=1), Layout(name="prediction", ratio=1))
        self.layout["stats"].split_row(Layout(name="stats_24h"), Layout(name="stats_7d"), Layout(name="stats_30d"))

    def get_header(self):
        try:
            market = self.cache.market_analyzer.analyze_market(TRADING_PAIRS)
            color = "green" if market == 'bullish' else "red" if market == 'bearish' else "yellow"
            emoji = "🐂" if market == 'bullish' else "🐻" if market == 'bearish' else "🦀"
            
            # 자산 계산
            now = datetime.now()
            if self.upbit and (now - self.last_asset_update).total_seconds() > 60:
                balances = self.upbit.get_balances()
                self.total_assets = sum(float(b['balance']) if b['currency'] == 'KRW' else float(b['balance']) * (pyupbit.get_current_price(f"KRW-{b['currency']}") or 0) for b in balances)
                self.last_asset_update = now

            return Panel(f"[bold cyan]🚀 Trading Bot V2[/bold cyan] | Market: [{color}]{emoji} {market.upper()}[/{color}] | Assets: [bold gold1]{self.total_assets:,.0f} KRW[/bold gold1] | [dim]{now.strftime('%H:%M:%S')}[/dim]", style="bold on dark_blue")
        except: return Panel("Header Loading...", style="bold on blue")

    def get_mtf_panel(self):
        """✅ MTF 분석 패널 보강"""
        if not self.cache.mtf_analyzer: return Panel("MTF Module Missing", title="📈 MTF Analysis", border_style="red")
        try:
            symbol = TRADING_PAIRS[0]
            res = self.cache.mtf_analyzer.analyze(symbol)
            if not res: return Panel(f"[yellow]Analyzing {symbol}...[/yellow]", title="📈 MTF Analysis")
            
            score = res['final_score']
            color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
            return Panel(f"Target: [bold]{symbol}[/bold]\nScore: [{color}]{score:.1f}/10[/{color}]\nTrend: [bold]{res['dominant_trend'].upper()}[/bold]\nSignal: {res['signal_strength'].upper()}", title="📈 MTF Analysis", border_style="blue")
        except Exception as e: return Panel(f"MTF Error: {e}", title="📈 MTF Analysis", border_style="red")

    def get_ml_panel(self):
        """✅ ML 예측 패널 보강"""
        if not self.cache.ml_generator: return Panel("ML Module Missing", title="🤖 ML Prediction", border_style="red")
        try:
            symbol = TRADING_PAIRS[0]
            if not self.cache.ml_generator.is_trained: return Panel("[yellow]Training Model...[/yellow]", title="🤖 ML Prediction")
            
            pred = self.cache.ml_generator.predict(symbol)
            if not pred: return Panel(f"[yellow]Predicting {symbol}...[/yellow]", title="🤖 ML Prediction")
            
            prob = pred['buy_probability']
            color = "green" if prob > 0.6 else "red"
            return Panel(f"Target: [bold]{symbol}[/bold]\nBuy Prob: [{color}]{prob:.1%}[/{color}]\nConf: {pred['confidence']:.1%}\nSignal: [bold]{'BUY' if pred['prediction'] else 'WAIT'}[/bold]", title="🤖 ML Prediction", border_style="magenta")
        except Exception as e: return Panel(f"ML Error: {e}", title="🤖 ML Prediction", border_style="red")

    # --- 기존의 다른 패널 함수들 (최소화된 형태) ---
    def get_watchlist(self):
        try:
            table = Table(show_header=True, header_style="bold magenta", expand=True)
            table.add_column("Coin"); table.add_column("Price", justify="right"); table.add_column("RSI", justify="center")
            prices = self.cache.get_prices_batch(TRADING_PAIRS[:8])
            for sym in TRADING_PAIRS[:8]:
                p = prices.get(f"KRW-{sym}", 0); rsi = self.cache.get_rsi(f"KRW-{sym}")
                table.add_row(sym, f"{p:,.0f}", f"{rsi:.0f}")
            return Panel(table, title="💰 Watchlist", border_style="cyan")
        except: return Panel("Loading...", title="💰 Watchlist")

    def get_market_movers(self):
        try:
            m = self.cache.get_top_movers_optimized()
            if not m['gainers']: return Panel("Loading...", title="📊 Movers")
            lines = ["[green]▲ Gainers[/green]"] + [f"{c['symbol']}: +{c['change']:.1f}%" for c in m['gainers'][:3]]
            lines += ["\n[red]▼ Losers[/red]"] + [f"{c['symbol']}: {c['change']:.1f}%" for c in m['losers'][:3]]
            return Panel("\n".join(lines), title="📊 Movers", border_style="yellow")
        except: return Panel("Loading...", title="📊 Movers")

    def get_active_positions(self):
        try:
            import json
            if not os.path.exists('active_positions.json'): return Panel("No Positions", title="📦 Positions")
            with open('active_positions.json', 'r') as f: data = json.load(f)
            positions = data.get('positions', {})
            if not positions: return Panel("No Positions", title="📦 Positions")
            lines = [f"{sym}: {pos['entry_price']:,.0f}" for sym, pos in positions.items()]
            return Panel("\n".join(lines), title="📦 Positions", border_style="green")
        except: return Panel("Loading...", title="📦 Positions")

    def get_recent_trades(self):
        try:
            trades = self.trade_history.get_recent_trades(5)
            table = Table(show_header=False, box=None, expand=True)
            for t in trades:
                color = "green" if t['pnl'] > 0 else "red"
                table.add_row(t['symbol'], f"[{color}]{t['pnl']:+,.0f}[/]")
            return Panel(table, title="📜 Recent Trades", border_style="white")
        except: return Panel("No history", title="📜 Recent Trades")

    def get_stats(self, days, title):
        try:
            stats = self.trade_history.get_period_stats(days)
            pnl = stats['net_pnl']; color = "green" if pnl > 0 else "red"
            lines = [f"Net PnL: [{color}]{pnl:+,.0f}[/]", f"Win Rate: {stats['win_rate']:.1f}%", f"Trades: {stats['trade_count']}"]
            return Panel("\n".join(lines), title=title, border_style="cyan")
        except: return Panel("N/A", title=title)

    def update(self):
        # ✅ 각 레이아웃 업데이트 (강제 할당)
        self.layout["header"].update(self.get_header())
        self.layout["watchlist"].update(self.get_watchlist())
        self.layout["recent_trades"].update(self.get_recent_trades())
        self.layout["market_movers"].update(self.get_market_movers())
        self.layout["active_positions"].update(self.get_active_positions())
        self.layout["analysis"].update(self.get_mtf_panel())    # ✅ 여기 확인
        self.layout["prediction"].update(self.get_ml_panel())   # ✅ 여기 확인
        self.layout["stats_24h"].update(self.get_stats(1, "24H"))
        self.layout["stats_7d"].update(self.get_stats(7, "7D"))
        self.layout["stats_30d"].update(self.get_stats(30, "30D"))
        self.layout["footer"].update(Panel(f"상태: 정상 | {datetime.now().strftime('%H:%M:%S')}", border_style="dim"))
        return self.layout

def main():
    db = TradingDashboard()
    with Live(db.update(), refresh_per_second=1, console=console) as live:
        while True:
            live.update(db.update())
            time.sleep(1)

if __name__ == "__main__":
    main()