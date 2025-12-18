# dashboard.py - trade_history_manager 연동 및 통계 보강 버전

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
from market_condition_check import MarketAnalyzer

# 프리셋 및 로깅 설정 적용
apply_preset(ACTIVE_PRESET)
console = Console()

class MarketDataCache:
    """시장 데이터 캐싱 및 최적화 클래스"""
    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.top_movers = {'gainers': [], 'losers': []}
        self.last_movers_update = datetime.now() - timedelta(minutes=10)
        self.market_analyzer = MarketAnalyzer()
        
    def get_prices_batch(self, tickers):
        try:
            full_tickers = [f"KRW-{t}" for t in tickers]
            prices = pyupbit.get_current_price(full_tickers)
            if isinstance(prices, dict): return prices
            elif isinstance(prices, float): return {full_tickers[0]: prices}
            return {}
        except: return {}

    def get_rsi(self, ticker):
        now = datetime.now()
        cache_key = f"{ticker}_rsi"
        if cache_key in self.last_update:
            if (now - self.last_update[cache_key]).total_seconds() < 60:
                return self.cache.get(cache_key, 50)
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is not None:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1]
                self.cache[cache_key] = current_rsi
                self.last_update[cache_key] = now
                return current_rsi
        except: pass
        return 50

    def get_top_movers_optimized(self):
        now = datetime.now()
        if (now - self.last_movers_update).total_seconds() < 300 and self.top_movers['gainers']:
            return self.top_movers
        try:
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            if len(all_tickers) > 100: all_tickers = all_tickers[:100]
            tickers_data = pyupbit.get_ticker(all_tickers)
            market_data = []
            for data in tickers_data:
                market_data.append({
                    'symbol': data['market'].replace('KRW-', ''),
                    'price': data['trade_price'],
                    'change': data['signed_change_rate'] * 100
                })
            market_data.sort(key=lambda x: x['change'], reverse=True)
            self.top_movers = {'gainers': market_data[:5], 'losers': market_data[-5:][::-1]}
            self.last_movers_update = now
        except: pass
        return self.top_movers

class TradingDashboard:
    def __init__(self):
        self.layout = Layout()
        self.cache = MarketDataCache()
        self.trade_history = TradeHistoryManager()
        self.api_calls = deque(maxlen=100)
        self.upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
        self.total_assets = 0
        self.last_asset_update = datetime.now() - timedelta(minutes=1)
        self.setup_layout()

    def setup_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="stats", size=10), # 통계 패널 크기 보강
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=1),
            Layout(name="right", ratio=1)
        )
        self.layout["left"].split(Layout(name="watchlist", ratio=3), Layout(name="recent_trades", ratio=2))
        self.layout["center"].split(Layout(name="market_movers", ratio=1), Layout(name="active_positions", ratio=1))
        self.layout["right"].split(Layout(name="analysis", ratio=1), Layout(name="prediction", ratio=1))
        self.layout["stats"].split_row(Layout(name="stats_24h"), Layout(name="stats_7d"), Layout(name="stats_30d"))

    def get_header(self):
        try:
            market = self.cache.market_analyzer.analyze_market(TRADING_PAIRS)
            color = "green" if market == 'bullish' else "red" if market == 'bearish' else "yellow"
            emoji = "🐂" if market == 'bullish' else "🐻" if market == 'bearish' else "🦀"
            
            # 총 자산 계산 (현금 + 코인 평가금)
            now = datetime.now()
            if (now - self.last_asset_update).total_seconds() > 60:
                balances = self.upbit.get_balances()
                total = sum(float(b['balance']) if b['currency'] == 'KRW' else float(b['balance']) * (pyupbit.get_current_price(f"KRW-{b['currency']}") or 0) for b in balances)
                self.total_assets = total
                self.last_asset_update = now

            return Panel(f"[bold cyan]🚀 Trading Bot V2[/bold cyan] | Market: [{color}]{emoji} {market.upper()}[/{color}] | Assets: [bold gold1]{self.total_assets:,.0f} KRW[/bold gold1] | [dim]{now.strftime('%H:%M:%S')}[/dim]", style="bold on dark_blue")
        except: return Panel("Loading Header...", style="bold on red")

    def get_stats_panel(self, days, title):
        """✅ trade_history_manager 기반 통계 보강"""
        try:
            stats = self.trade_history.get_period_stats(days) #
            pnl = stats['net_pnl']
            color = "green" if pnl > 0 else "red"
            
            # 보강된 지표들
            lines = [
                f"Net PnL: [{color}]{pnl:+,.0f} KRW[/{color}]",
                f"Win Rate: [bold]{stats['win_rate']:.1f}%[/bold] ({stats['win_count']}W {stats['loss_count']}L)",
                f"Profit Factor: [yellow]{stats['profit_factor']:.2f}[/yellow]", #
                f"Trades: {stats['trade_count']}"
            ]
            
            # 7일 이상의 통계에는 최고/최악 종목 추가
            if days >= 7:
                lines.append(f"Best: [green]{stats['best_symbol']}[/green]") #
                lines.append(f"Worst: [red]{stats['worst_symbol']}[/red]") #

            return Panel("\n".join(lines), title=title, border_style="cyan")
        except: return Panel("Stats Loading...", title=title, border_style="red")

    def get_recent_trades_panel(self):
        """최근 거래 내역 패널"""
        try:
            trades = self.trade_history.get_recent_trades(5) #
            if not trades: return Panel("No recent trades", title="📜 Last Trades")
            
            table = Table(show_header=False, box=None, padding=(0,1), expand=True)
            for t in trades:
                color = "green" if t['pnl'] > 0 else "red"
                # 수익률(pnl_rate)이 있으면 같이 표시
                pnl_rate_str = f"({t.get('pnl_rate', 0)*100:+.1f}%)" if 'pnl_rate' in t else ""
                table.add_row(f"{t['symbol']}", f"[{color}]{t['pnl']:+,.0f}{pnl_rate_str}[/]")
            return Panel(table, title="📜 Recent Trades", border_style="white")
        except: return Panel("Error loading trades", title="📜 Last Trades")

    def get_active_positions_panel(self):
        """현재 포지션 패널"""
        try:
            import json
            if not os.path.exists('active_positions.json'): return Panel("No Positions", title="📦 Positions")
            with open('active_positions.json', 'r') as f: data = json.load(f)
            positions = data.get('positions', {})
            if not positions: return Panel("No Positions", title="📦 Positions")
            
            prices = self.cache.get_prices_batch(list(positions.keys()))
            lines = []
            for sym, pos in positions.items():
                cur = prices.get(f"KRW-{sym}", pos['entry_price'])
                rate = (cur - pos['entry_price']) / pos['entry_price'] * 100
                color = "green" if rate > 0 else "red"
                lines.append(f"{sym}: [{color}]{rate:+.2f}%[/{color}] [dim]({cur*pos['quantity']:,.0f}원)[/dim]")
            return Panel("\n".join(lines), title="📦 Active Positions", border_style="green")
        except: return Panel("Position Error", title="📦 Positions")

    def get_watchlist_table(self):
        try:
            table = Table(show_header=True, header_style="bold magenta", expand=True)
            table.add_column("Coin", width=6); table.add_column("Price", justify="right"); table.add_column("RSI", justify="center")
            prices = self.cache.get_prices_batch(TRADING_PAIRS[:8])
            for sym in TRADING_PAIRS[:8]:
                p = prices.get(f"KRW-{sym}", 0)
                rsi = self.cache.get_rsi(f"KRW-{sym}")
                rsi_col = "green" if rsi <= 30 else "red" if rsi >= 70 else "white"
                table.add_row(sym, f"{p:,.0f}" if p >= 100 else f"{p:.2f}", f"[{rsi_col}]{rsi:.0f}[/{rsi_col}]")
            return Panel(table, title="💰 Watchlist", border_style="cyan")
        except: return Panel("Watchlist Error", title="💰 Watchlist")

    def get_market_movers_panel(self):
        try:
            m = self.cache.get_top_movers_optimized()
            if not m['gainers']: return Panel("Fetching...", title="📊 Movers")
            lines = ["[bold green]▲ Top Gainers[/bold green]"] + [f"{c['symbol']}: +{c['change']:.1f}%" for c in m['gainers'][:3]]
            lines += ["\n[bold red]▼ Top Losers[/bold red]"] + [f"{c['symbol']}: {c['change']:.1f}%" for c in m['losers'][:3]]
            return Panel("\n".join(lines), title="📊 Market Movers", border_style="yellow")
        except: return Panel("Movers Error", title="📊 Movers")

    def get_mtf_panel(self):
        try:
            from multi_timeframe_analyzer import MultiTimeframeAnalyzer
            res = MultiTimeframeAnalyzer().analyze(TRADING_PAIRS[0])
            if not res: return Panel("Loading...", title="📈 MTF")
            score = res['final_score']
            color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
            return Panel(f"Target: {TRADING_PAIRS[0]}\nScore: [{color}]{score:.1f}/10[/{color}]\nTrend: {res['dominant_trend']}\nSignal: {res['signal_strength'].upper()}", title="📈 MTF Analysis", border_style="blue")
        except: return Panel("MTF Error", title="📈 MTF")

    def get_ml_panel(self):
        try:
            from ml_signal_generator import MLSignalGenerator
            ml = MLSignalGenerator()
            if not ml.is_trained: return Panel("Training...", title="🤖 ML")
            pred = ml.predict(TRADING_PAIRS[0])
            if not pred: return Panel("No Data", title="🤖 ML")
            prob = pred['buy_probability']
            color = "green" if prob > 0.6 else "red"
            return Panel(f"Target: {TRADING_PAIRS[0]}\nProb: [{color}]{prob:.1%}[/{color}]\nConf: {pred['confidence']:.1%}\nSignal: {'BUY' if pred['prediction'] else 'WAIT'}", title="🤖 ML Prediction", border_style="magenta")
        except: return Panel("ML Error", title="🤖 ML")

    def update(self):
        """각 섹션 업데이트 (에러 격리)"""
        try: self.layout["header"].update(self.get_header())
        except: pass
        try: self.layout["watchlist"].update(self.get_watchlist_table())
        except: pass
        try: self.layout["market_movers"].update(self.get_market_movers_panel())
        except: pass
        try: self.layout["active_positions"].update(self.get_active_positions_panel())
        except: pass
        try: self.layout["analysis"].update(self.get_mtf_panel())
        except: pass
        try: self.layout["prediction"].update(self.get_ml_panel())
        except: pass
        try: self.layout["recent_trades"].update(self.get_recent_trades_panel())
        except: pass
        try:
            self.layout["stats_24h"].update(self.get_stats_panel(1, "📊 24H Stats"))
            self.layout["stats_7d"].update(self.get_stats_panel(7, "📊 7D Stats"))
            self.layout["stats_30d"].update(self.get_stats_panel(30, "📊 30D Stats"))
        except: pass
        return self.layout

def main():
    db = TradingDashboard()
    with Live(db.update(), refresh_per_second=1, console=console) as live:
        while True:
            live.update(db.update())
            time.sleep(1)

if __name__ == "__main__":
    main()