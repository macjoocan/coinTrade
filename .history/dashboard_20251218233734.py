# dashboard.py - API 키 로드 및 에러 핸들링 수정 버전

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
from dotenv import load_dotenv  # ✅ 추가: .env 파일 로드용
from trade_history_manager import TradeHistoryManager
from config import TRADING_PAIRS, RISK_CONFIG, apply_preset, ACTIVE_PRESET
from market_condition_check import MarketAnalyzer

# ✅ 실행 전 환경 변수 로드 (가장 중요!)
load_dotenv()

# 프리셋 적용
apply_preset(ACTIVE_PRESET)
console = Console()

class MarketDataCache:
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
            elif isinstance(prices, float): return {f"KRW-{tickers[0]}": prices}
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
        
        # ✅ API 키 확인 및 Upbit 객체 초기화
        access = os.getenv("UPBIT_ACCESS_KEY")
        secret = os.getenv("UPBIT_SECRET_KEY")
        if not access or not secret:
            console.print("[bold red]❌ 에러: .env 파일에서 API 키를 찾을 수 없습니다![/bold red]")
            self.upbit = None
        else:
            self.upbit = pyupbit.Upbit(access, secret)
            
        self.total_assets = 0
        self.last_asset_update = datetime.now() - timedelta(minutes=1)
        self.setup_layout()

    def setup_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="stats", size=10),
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

    def get_total_assets(self):
        if not self.upbit: return 0
        now = datetime.now()
        if (now - self.last_asset_update).total_seconds() < 60 and self.total_assets > 0:
            return self.total_assets
        try:
            balances = self.upbit.get_balances()
            total = 0
            for b in balances:
                if b['currency'] == 'KRW': total += float(b['balance'])
                else:
                    price = pyupbit.get_current_price(f"KRW-{b['currency']}")
                    if price: total += float(b['balance']) * price
            self.total_assets = total
            self.last_asset_update = now
            return total
        except: return self.total_assets

    def get_header(self):
        try:
            market = self.cache.market_analyzer.analyze_market(TRADING_PAIRS)
            color = "green" if market == 'bullish' else "red" if market == 'bearish' else "yellow"
            emoji = "🐂" if market == 'bullish' else "🐻" if market == 'bearish' else "🦀"
            
            assets = self.get_total_assets()
            asset_str = f"{assets:,.0f} KRW" if assets > 0 else "API Key Error"

            return Panel(f"[bold cyan]🚀 Trading Bot V2[/bold cyan] | Market: [{color}]{emoji} {market.upper()}[/{color}] | Assets: [bold gold1]{asset_str}[/bold gold1] | [dim]{datetime.now().strftime('%H:%M:%S')}[/dim]", style="bold on dark_blue")
        except: return Panel("[bold red]Header Error (Check API Keys)[/bold red]", style="bold on black")

    def get_footer(self):
        # API 호출 횟수 추적 로직 생략 (간소화)
        return Panel(f"상태: 정상 작동 중 | [dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim] | Press Ctrl+C to Exit", border_style="dim")

    def get_stats_panel(self, days, title):
        try:
            stats = self.trade_history.get_period_stats(days)
            pnl = stats['net_pnl']
            color = "green" if pnl > 0 else "red"
            lines = [
                f"Net PnL: [{color}]{pnl:+,.0f} KRW[/{color}]",
                f"Win Rate: {stats['win_rate']:.1f}% ({stats['win_count']}W {stats['loss_count']}L)",
                f"Profit Factor: {stats['profit_factor']:.2f}",
                f"Trades: {stats['trade_count']}"
            ]
            return Panel("\n".join(lines), title=title, border_style="cyan")
        except: return Panel("N/A", title=title)

    def get_recent_trades_panel(self):
        try:
            trades = self.trade_history.get_recent_trades(5)
            if not trades: return Panel("No recent trades", title="📜 Recent Trades")
            table = Table(show_header=False, box=None, expand=True)
            for t in trades:
                color = "green" if t['pnl'] > 0 else "red"
                table.add_row(f"{t['symbol']}", f"[{color}]{t['pnl']:+,.0f}[/]")
            return Panel(table, title="📜 Recent Trades", border_style="white")
        except: return Panel("N/A", title="📜 Recent Trades")

    def get_active_positions_panel(self):
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
                lines.append(f"{sym}: [{color}]{rate:+.2f}%[/{color}]")
            return Panel("\n".join(lines), title="📦 Positions", border_style="green")
        except: return Panel("N/A", title="📦 Positions")

    def get_watchlist_table(self):
        try:
            table = Table(show_header=True, header_style="bold magenta", expand=True)
            table.add_column("Coin"); table.add_column("Price", justify="right"); table.add_column("RSI", justify="center")
            prices = self.cache.get_prices_batch(TRADING_PAIRS[:8])
            for sym in TRADING_PAIRS[:8]:
                p = prices.get(f"KRW-{sym}", 0)
                rsi = self.cache.get_rsi(f"KRW-{sym}")
                table.add_row(sym, f"{p:,.0f}", f"{rsi:.0f}")
            return Panel(table, title="💰 Watchlist", border_style="cyan")
        except: return Panel("N/A", title="💰 Watchlist")

    def get_market_movers_panel(self):
        try:
            m = self.cache.get_top_movers_optimized()
            if not m['gainers']: return Panel("Loading...", title="📊 Movers")
            lines = ["[green]▲ Gainers[/green]"] + [f"{c['symbol']}: +{c['change']:.1f}%" for c in m['gainers'][:3]]
            lines += ["\n[red]▼ Losers[/red]"] + [f"{c['symbol']}: {c['change']:.1f}%" for c in m['losers'][:3]]
            return Panel("\n".join(lines), title="📊 Movers", border_style="yellow")
        except: return Panel("N/A", title="📊 Movers")

    def update(self):
        # ✅ 각 섹션을 업데이트하여 'Layout(name=...)'이 보이지 않게 방어
        try: self.layout["header"].update(self.get_header())
        except: pass
        try: self.layout["watchlist"].update(self.get_watchlist_table())
        except: pass
        try: self.layout["market_movers"].update(self.get_market_movers_panel())
        except: pass
        try: self.layout["active_positions"].update(self.get_active_positions_panel())
        except: pass
        try: self.layout["recent_trades"].update(self.get_recent_trades_panel())
        except: pass
        try: self.layout["footer"].update(self.get_footer())
        except: pass
        try:
            self.layout["stats_24h"].update(self.get_stats_panel(1, "24H"))
            self.layout["stats_7d"].update(self.get_stats_panel(7, "7D"))
            self.layout["stats_30d"].update(self.get_stats_panel(30, "30D"))
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