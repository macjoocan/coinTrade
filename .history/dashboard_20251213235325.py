# dashboard.py - 최적화 및 RSI/시장상황 추가 버전

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
from trade_history_manager import TradeHistoryManager
from config import TRADING_PAIRS, RISK_CONFIG, apply_preset, ACTIVE_PRESET
from market_condition_check import MarketAnalyzer  # ✅ 시장 분석 추가

apply_preset(ACTIVE_PRESET)
console = Console()

class MarketDataCache:
    """시장 데이터 캐싱 및 최적화 클래스"""
    def __init__(self):
        self.cache = {}
        self.ohlcv_cache = {}
        self.last_update = {}
        self.top_movers = {'gainers': [], 'losers': []}
        self.last_movers_update = datetime.now() - timedelta(minutes=5)
        self.update_interval = 20  # 가격 업데이트 주기
        self.market_analyzer = MarketAnalyzer() # ✅ 시장 분석기 인스턴스
        
    def get_prices_batch(self, tickers):
        """✅ 최적화: 여러 코인 가격을 한 번에 조회"""
        try:
            full_tickers = [f"KRW-{t}" for t in tickers]
            prices = pyupbit.get_current_price(full_tickers)
            if isinstance(prices, dict):
                return prices
            elif isinstance(prices, float): # 코인이 1개일 경우
                return {full_tickers[0]: prices}
            return {}
        except Exception as e:
            return {}

    def get_rsi(self, ticker):
        """RSI 계산 및 캐싱"""
        now = datetime.now()
        cache_key = f"{ticker}_rsi"
        
        # 1분 이내면 캐시 사용
        if cache_key in self.last_update:
            if (now - self.last_update[cache_key]).total_seconds() < 60:
                return self.cache.get(cache_key, 50)

        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is not None:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]
                
                self.cache[cache_key] = current_rsi
                self.last_update[cache_key] = now
                return current_rsi
        except:
            pass
        
        return 50

    def get_top_movers_optimized(self):
        """✅ 최적화: get_ticker로 한 번에 조회"""
        now = datetime.now()
        if (now - self.last_movers_update).total_seconds() < 300:
            return self.top_movers
            
        try:
            major_coins = [
                'BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX', 'DOT', 
                'MATIC', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM', 'TRX', 'SHIB', 
                'NEAR', 'BCH', 'APT', 'ARB', 'OP', 'SUI', 'SEI'
            ]
            full_tickers = [f"KRW-{c}" for c in major_coins]
            
            # 한 번의 호출로 모든 데이터 가져오기
            tickers_data = pyupbit.get_ticker(full_tickers)
            
            market_data = []
            for data in tickers_data:
                symbol = data['market'].replace('KRW-', '')
                change_rate = data['signed_change_rate'] * 100
                market_data.append({
                    'symbol': symbol,
                    'price': data['trade_price'],
                    'change': change_rate
                })
            
            market_data.sort(key=lambda x: x['change'], reverse=True)
            
            self.top_movers = {
                'gainers': market_data[:5],
                'losers': market_data[-5:][::-1]
            }
            self.last_movers_update = now
            
        except Exception as e:
            pass
            
        return self.top_movers

class TradingDashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.cache = MarketDataCache()
        self.trade_history = TradeHistoryManager()
        
        # API 상태 추적
        self.api_calls = deque(maxlen=100)
        
        # 캐시 변수들
        self.recent_trades_cache = []
        self.last_trades_update = datetime.now() - timedelta(minutes=1)
        self.stats_cache = {'24h': None, '7d': None, '30d': None}
        self.last_stats_update = datetime.now() - timedelta(minutes=5)
        
        # ✅ 총 자산 계산용
        self.upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
        self.total_assets = 0
        self.last_asset_update = datetime.now() - timedelta(minutes=1)

        self.setup_layout()

    def setup_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="stats", size=10), # 높이 살짝 조정
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=1),
            Layout(name="right", ratio=1)
        )
        self.layout["left"].split(
            Layout(name="watchlist", ratio=3),
            Layout(name="recent_trades", ratio=2)
        )
        self.layout["center"].split(
            Layout(name="market_movers", ratio=1),
            Layout(name="active_positions", ratio=1)
        )
        self.layout["right"].split(
            Layout(name="analysis", ratio=1),
            Layout(name="prediction", ratio=1)
        )
        self.layout["stats"].split_row(
            Layout(name="stats_24h"),
            Layout(name="stats_7d"),
            Layout(name="stats_30d")
        )

    def track_api_call(self):
        self.api_calls.append(datetime.now())

    def get_total_assets(self):
        """✅ 총 자산(현금+평가금) 계산"""
        now = datetime.now()
        if (now - self.last_asset_update).total_seconds() < 60 and self.total_assets > 0:
            return self.total_assets

        try:
            balances = self.upbit.get_balances()
            total = 0
            for b in balances:
                if b['currency'] == 'KRW':
                    total += float(b['balance'])
                else:
                    ticker = f"KRW-{b['currency']}"
                    price = pyupbit.get_current_price(ticker)
                    if price:
                        total += float(b['balance']) * price
            self.total_assets = total
            self.last_asset_update = now
            return total
        except:
            return self.total_assets

    def get_header(self):
        """✅ 시장 상황 및 총 자산 포함 헤더"""
        # 시장 상황 분석
        market_condition = self.cache.market_analyzer.analyze_market(TRADING_PAIRS)
        
        condition_color = "green" if market_condition == 'bullish' else "red" if market_condition == 'bearish' else "yellow"
        emoji = "🐂" if market_condition == 'bullish' else "🐻" if market_condition == 'bearish' else "🦀"
        
        total_assets = self.get_total_assets()
        
        return Panel(
            f"[bold cyan]🚀 Trading Bot V2[/bold cyan] | "
            f"Market: [{condition_color}]{emoji} {market_condition.upper()}[/{condition_color}] | "
            f"Assets: [bold gold1]{total_assets:,.0f} KRW[/bold gold1] | "
            f"[dim]{datetime.now().strftime('%H:%M:%S')}[/dim]",
            style="bold on dark_blue"
        )

    def get_watchlist_table(self):
        """✅ RSI 컬럼 추가된 Watchlist"""
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Coin", style="cyan", width=6)
        table.add_column("Price", justify="right")
        table.add_column("RSI", justify="center", width=6) # ✅ 추가됨
        table.add_column("Chg%", justify="right")
        
        # 배치로 가격 조회
        prices = self.cache.get_prices_batch(TRADING_PAIRS[:8])
        self.track_api_call()

        for symbol in TRADING_PAIRS[:8]:
            ticker = f"KRW-{symbol}"
            price = prices.get(ticker, 0)
            
            # RSI 계산
            rsi = self.cache.get_rsi(ticker)
            
            # RSI 색상
            if rsi <= 30: rsi_str = f"[bold green]{rsi:.0f}[/bold green]"  # 매수 기회
            elif rsi >= 70: rsi_str = f"[bold red]{rsi:.0f}[/bold red]"    # 과매수
            else: rsi_str = f"{rsi:.0f}"
            
            # 등락률 (약식 계산 - 어제 종가 대신 캐시 활용하거나 get_ticker 사용 추천, 여기서는 간략화)
            # 정확도를 위해 여기서도 get_ticker를 쓰는게 좋지만, 일단 가격만 표시
            
            if price > 0:
                price_fmt = f"{price:,.0f}" if price >= 100 else f"{price:.2f}"
                table.add_row(symbol, price_fmt, rsi_str, "-")
            else:
                table.add_row(symbol, "N/A", "-", "-")
                
        return Panel(table, title="💰 Watchlist (w/ RSI)", border_style="cyan")

    def get_market_movers_panel(self):
        """최적화된 Movers 패널"""
        movers = self.cache.get_top_movers_optimized()
        
        lines = ["[bold]🔥 Top Gainers[/bold]"]
        for c in movers['gainers'][:3]:
            lines.append(f"[green]{c['symbol']}: +{c['change']:.1f}%[/green] ({c['price']:,.0f})")
            
        lines.append("\n[bold]💧 Top Losers[/bold]")
        for c in movers['losers'][:3]:
            lines.append(f"[red]{c['symbol']}: {c['change']:.1f}%[/red] ({c['price']:,.0f})")
            
        return Panel("\n".join(lines), title="📊 Market Movers", border_style="yellow")

    def get_active_positions_panel(self):
        """포지션 및 수익률 패널"""
        try:
            import json
            if not os.path.exists('active_positions.json'):
                return Panel("No active positions", title="📦 Positions", border_style="green")
                
            with open('active_positions.json', 'r') as f:
                data = json.load(f)
                positions = data.get('positions', {})
            
            if not positions:
                return Panel("No active positions", title="📦 Positions", border_style="green")
                
            # 현재가 배치 조회
            tickers = list(positions.keys())
            current_prices = self.cache.get_prices_batch(tickers)
            
            lines = []
            total_pnl = 0
            
            for symbol, pos in positions.items():
                ticker = f"KRW-{symbol}"
                cur_price = current_prices.get(ticker, pos['entry_price'])
                entry = pos['entry_price']
                qty = pos['quantity']
                
                pnl_rate = (cur_price - entry) / entry * 100
                pnl_val = (cur_price - entry) * qty
                total_pnl += pnl_val
                
                color = "green" if pnl_rate > 0 else "red"
                lines.append(f"{symbol}: [{color}]{pnl_rate:+.2f}%[/] [dim]({pnl_val:+,.0f})[/dim]")
                
            lines.insert(0, f"Total PnL: [bold {'green' if total_pnl>0 else 'red'}]{total_pnl:+,.0f} KRW[/]\n")
            
            return Panel("\n".join(lines), title=f"📦 Positions ({len(positions)})", border_style="green")
            
        except Exception as e:
            return Panel(f"Error: {e}", title="📦 Positions", border_style="red")

    # ... (MTF, ML, Stats, Recent Trades 패널은 기존 코드 유지하거나 위와 동일한 방식으로 통합) ...
    # 지면 관계상 핵심이 변경되지 않은 함수(MTF, ML 등)는 기존 코드를 그대로 사용하세요.
    
    def get_mtf_analysis_panel(self):
        # (기존 코드와 동일)
        # 단, 예외처리 강화 추천
        try:
            from multi_timeframe_analyzer import MultiTimeframeAnalyzer
            mtf = MultiTimeframeAnalyzer()
            symbol = TRADING_PAIRS[0]
            analysis = mtf.analyze(symbol)
            
            if not analysis: return Panel("Loading...", title="📈 MTF Analysis")
            
            score = analysis['final_score']
            color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
            
            return Panel(
                f"Symbol: {symbol}\n"
                f"Score: [{color}]{score:.1f}/10[/]\n"
                f"Trend: {analysis['dominant_trend']}\n"
                f"Strength: {analysis['signal_strength'].upper()}",
                title="📈 MTF Analysis", border_style="blue"
            )
        except:
            return Panel("MTF Error", title="📈 MTF Analysis")

    def get_ml_prediction_panel(self):
        # (기존 코드와 동일)
        try:
            from ml_signal_generator import MLSignalGenerator
            ml = MLSignalGenerator()
            symbol = TRADING_PAIRS[0]
            if not ml.is_trained: return Panel("Training Model...", title="🤖 ML AI")
            
            pred = ml.predict(symbol)
            if not pred: return Panel("No Prediction", title="🤖 ML AI")
            
            prob = pred['buy_probability']
            color = "green" if prob > 0.6 else "red"
            
            return Panel(
                f"Symbol: {symbol}\n"
                f"Buy Prob: [{color}]{prob:.1%}[/]\n"
                f"Confidence: {pred['confidence']:.1%}\n"
                f"Signal: {'BUY' if pred['prediction'] else 'WAIT'}",
                title="🤖 ML Prediction", border_style="magenta"
            )
        except:
            return Panel("ML Error", title="🤖 ML AI")

    def get_recent_trades_panel(self):
        # (기존 코드 활용하되 캐시 적용)
        now = datetime.now()
        if (now - self.last_trades_update).total_seconds() > 30:
            self.recent_trades_cache = self.trade_history.get_recent_trades(5)
            self.last_trades_update = now
            
        trades = self.recent_trades_cache
        if not trades: return Panel("No trades yet", title="Recent Trades")
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        for t in trades:
            color = "green" if t['pnl'] > 0 else "red"
            table.add_row(t['symbol'], f"[{color}]{t['pnl']:+,.0f}[/]")
            
        return Panel(table, title="📜 Last Trades", border_style="white")

    def get_stats_panel(self, days, title):
        # (기존 코드 활용)
        stats = self.trade_history.get_period_stats(days)
        pnl = stats['net_pnl']
        color = "green" if pnl > 0 else "red"
        
        return Panel(
            f"Net PnL: [{color}]{pnl:+,.0f}[/]\n"
            f"Win Rate: {stats['win_rate']:.1f}%\n"
            f"Trades: {stats['trade_count']}",
            title=title, border_style="cyan"
        )
    
    def get_footer(self):
        # (기존 코드 활용)
        calls = len([t for t in self.api_calls if (datetime.now() - t).total_seconds() < 60])
        return Panel(f"API Calls: {calls}/min | Press Ctrl+C to Exit", border_style="dim")

    def update(self):
        try:
            self.layout["header"].update(self.get_header())
            self.layout["watchlist"].update(self.get_watchlist_table())
            self.layout["market_movers"].update(self.get_market_movers_panel())
            self.layout["active_positions"].update(self.get_active_positions_panel())
            self.layout["analysis"].update(self.get_mtf_analysis_panel())
            self.layout["prediction"].update(self.get_ml_prediction_panel())
            self.layout["recent_trades"].update(self.get_recent_trades_panel())
            
            self.layout["stats_24h"].update(self.get_stats_panel(1, "24H Stats"))
            self.layout["stats_7d"].update(self.get_stats_panel(7, "7D Stats"))
            self.layout["stats_30d"].update(self.get_stats_panel(30, "30D Stats"))
            
            self.layout["footer"].update(self.get_footer())
        except Exception as e:
            console.print(f"Update Error: {e}")
        return self.layout

def main():
    dashboard = TradingDashboard()
    console.clear()
    console.print("[yellow]Loading Dashboard...[/yellow]")
    
    with Live(dashboard.update(), refresh_per_second=1, console=console) as live:
        while True:
            live.update(dashboard.update())
            time.sleep(1) # 부드러운 업데이트를 위해 1초 대기

if __name__ == "__main__":
    main()