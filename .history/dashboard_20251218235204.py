# dashboard.py - Positions 수익률 및 수익금 표시 완전 복구 버전

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

# 분석 도구 임포트 (파일이 없을 경우 대비 예외처리)
try:
    from multi_timeframe_analyzer import MultiTimeframeAnalyzer
    from ml_signal_generator import MLSignalGenerator
except ImportError:
    MultiTimeframeAnalyzer = None
    MLSignalGenerator = None

# ✅ .env 파일 로드 및 프리셋 설정
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
        
        # 분석기 인스턴스 재사용 (속도 향상)
        self.mtf_analyzer = MultiTimeframeAnalyzer() if MultiTimeframeAnalyzer else None
        self.ml_generator = MLSignalGenerator() if MLSignalGenerator else None
        
    def get_prices_batch(self, tickers):
        """여러 코인 가격 한 번에 조회"""
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
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
                self.cache[cache_key] = rsi; self.last_update[cache_key] = now
                return rsi
        except: pass
        return 50

    def get_top_movers_optimized(self):
        """Movers 실시간 등락률 조회 (상위 15개로 제한하여 속도 개선)"""
        now = datetime.now()
        if self.top_movers['gainers'] and (now - self.last_movers_update).total_seconds() < 120:
            return self.top_movers
        try:
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            target_tickers = all_tickers[:15]
            tickers_data = pyupbit.get_ticker(target_tickers)
            market_data = []
            for data in tickers_data:
                change = data.get('signed_change_rate', 0) or 0
                market_data.append({'symbol': data['market'].replace('KRW-', ''), 'price': data['trade_price'], 'change': change * 100})
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
        
        # API 초기화
        access = os.getenv("UPBIT_ACCESS_KEY"); secret = os.getenv("UPBIT_SECRET_KEY")
        self.upbit = pyupbit.Upbit(access, secret) if access and secret else None
            
        self.total_assets = 0
        self.last_asset_update = datetime.now() - timedelta(minutes=1)
        self.setup_layout()

    def setup_layout(self):
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
            
            now = datetime.now()
            if self.upbit and (now - self.last_asset_update).total_seconds() > 60:
                balances = self.upbit.get_balances()
                self.total_assets = sum(float(b['balance']) if b['currency'] == 'KRW' else float(b['balance']) * (pyupbit.get_current_price(f"KRW-{b['currency']}") or 0) for b in balances)
                self.last_asset_update = now

            return Panel(f"[bold cyan]🚀 Trading Bot V2[/bold cyan] | Market: [{color}]{emoji} {market.upper()}[/{color}] | Assets: [bold gold1]{self.total_assets:,.0f} KRW[/bold gold1] | [dim]{now.strftime('%H:%M:%S')}[/dim]", style="bold on dark_blue")
        except: return Panel("Header Loading...", style="bold on blue")

    def get_active_positions(self):
        """✅ 복구 완료: 보유 종목의 실시간 수익률 및 수익금 표시"""
        try:
            import json
            if not os.path.exists('active_positions.json'):
                return Panel("보유 포지션 없음", title="📦 Positions", border_style="green")
            
            with open('active_positions.json', 'r') as f:
                data = json.load(f)
            
            positions = data.get('positions', {})
            if not positions:
                return Panel("보유 포지션 없음", title="📦 Positions", border_style="green")
            
            # 실시간 가격 배치 조회
            symbols = list(positions.keys())
            current_prices = self.cache.get_prices_batch(symbols)
            
            lines = []
            total_eval_pnl = 0
            
            for sym, pos in positions.items():
                entry_price = pos['entry_price']
                quantity = pos.get('quantity', 0)
                # 실시간 가격 매칭 (없으면 진입가 기준)
                cur_price = current_prices.get(f"KRW-{sym}", entry_price)
                
                # 수익률 및 수익금 계산
                pnl_rate = (cur_price - entry_price) / entry_price * 100
                pnl_val = (cur_price - entry_price) * quantity
                total_eval_pnl += pnl_val
                
                color = "green" if pnl_rate >= 0 else "red"
                # 표시 형식: 코인명: +1.23% (+1,234원)
                lines.append(f"{sym:<5}: [{color}]{pnl_rate:>+6.2f}%[/{color}] [dim]({pnl_val:+,.0f}원)[/dim]")
            
            # 상단에 총 평가 손익 요약 추가
            summary_color = "green" if total_eval_pnl >= 0 else "red"
            lines.insert(0, f"Total PnL: [bold {summary_color}]{total_eval_pnl:+,.0f} KRW[/bold {summary_color}]\n" + "─" * 32)
            
            return Panel("\n".join(lines), title=f"📦 Positions ({len(positions)})", border_style="green")
        except: 
            return Panel("데이터 로딩 중...", title="📦 Positions")

    def get_market_movers(self):
        try:
            m = self.cache.get_top_movers_optimized()
            if not m['gainers']: return Panel("[dim]Loading... (조회 대상을 줄여 속도를 개선했습니다)[/dim]", title="📊 Market Movers")
            lines = ["[bold green]▲ 상승 상위[/bold green]"]
            for c in m['gainers'][:3]:
                lines.append(f"{c['symbol']:<6}: [bold green]+{c['change']:>5.2f}%[/bold green]")
            lines.append("\n[bold red]▼ 하락 상위[/bold red]")
            for c in m['losers'][:3]:
                lines.append(f"{c['symbol']:<6}: [bold red]{c['change']:>6.2f}%[/bold red]")
            return Panel("\n".join(lines), title="📊 Market Movers", border_style="yellow")
        except: return Panel("Movers Error", title="📊 Market Movers")

    def get_watchlist(self):
        try:
            table = Table(show_header=True, header_style="bold magenta", expand=True)
            table.add_column("Coin"); table.add_column("Price", justify="right"); table.add_column("RSI", justify="center")
            prices = self.cache.get_prices_batch(TRADING_PAIRS[:8])
            for sym in TRADING_PAIRS[:8]:
                p = prices.get(f"KRW-{sym}", 0); rsi = self.cache.get_rsi(f"KRW-{sym}")
                rsi_col = "green" if rsi <= 30 else "red" if rsi >= 70 else "white"
                table.add_row(sym, f"{p:,.0f}" if p >= 100 else f"{p:.2f}", f"[{rsi_col}]{rsi:.0f}[/{rsi_col}]")
            return Panel(table, title="💰 Watchlist", border_style="cyan")
        except: return Panel("Watchlist Error", title="💰 Watchlist")

    def get_recent_trades(self):
        try:
            trades = self.trade_history.get_recent_trades(5)
            table = Table(show_header=False, box=None, expand=True)
            for t in trades:
                color = "green" if t['pnl'] > 0 else "red"
                table.add_row(t['symbol'], f"[{color}]{t['pnl']:+,.0f}[/]")
            return Panel(table, title="📜 Recent Trades", border_style="white")
        except: return Panel("기록 없음", title="📜 Recent Trades")

    def get_stats(self, days, title):
        try:
            stats = self.trade_history.get_period_stats(days)
            pnl = stats['net_pnl']; color = "green" if pnl > 0 else "red"
            lines = [f"Net PnL: [{color}]{pnl:+,.0f}[/]", f"Win Rate: {stats['win_rate']:.1f}%", f"Trades: {stats['trade_count']}"]
            return Panel("\n".join(lines), title=title, border_style="cyan")
        except: return Panel("N/A", title=title)

    def update(self):
        # 각 레이아웃 섹션 업데이트
        try: self.layout["header"].update(self.get_header())
        except: pass
        try: self.layout["watchlist"].update(self.get_watchlist())
        except: pass
        try: self.layout["recent_trades"].update(self.get_recent_trades())
        except: pass
        try: self.layout["market_movers"].update(self.get_market_movers())
        except: pass
        try: self.layout["active_positions"].update(self.get_active_positions())
        except: pass
        
        # 분석 및 예측 패널 업데이트
        try:
            if self.cache.mtf_analyzer:
                res = self.cache.mtf_analyzer.analyze(TRADING_PAIRS[0])
                if res:
                    score = res['final_score']; color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
                    self.layout["analysis"].update(Panel(f"Target: {TRADING_PAIRS[0]}\nScore: [{color}]{score:.1f}/10[/{color}]\nTrend: {res['dominant_trend'].upper()}\nSignal: {res['signal_strength'].upper()}", title="📈 Analysis", border_style="blue"))
        except: pass
        
        try:
            if self.cache.ml_generator and self.cache.ml_generator.is_trained:
                pred = self.cache.ml_generator.predict(TRADING_PAIRS[0])
                if pred:
                    prob = pred['buy_probability']; color = "green" if prob > 0.6 else "red"
                    self.layout["prediction"].update(Panel(f"Target: {TRADING_PAIRS[0]}\nBuy Prob: [{color}]{prob:.1%}[/{color}]\nSignal: {'BUY' if pred['prediction'] else 'WAIT'}", title="🤖 Prediction", border_style="magenta"))
        except: pass

        try:
            self.layout["stats_24h"].update(self.get_stats(1, "24H Stats"))
            self.layout["stats_7d"].update(self.get_stats(7, "7D Stats"))
            self.layout["stats_30d"].update(self.get_stats(30, "30D Stats"))
        except: pass
        
        self.layout["footer"].update(Panel(f"상태: 정상 가동 중 | {datetime.now().strftime('%H:%M:%S')} | 데이터 캐시 활성화됨", border_style="dim"))
        return self.layout

def main():
    db = TradingDashboard()
    with Live(db.update(), refresh_per_second=1, console=console) as live:
        while True:
            live.update(db.update())
            time.sleep(1)

if __name__ == "__main__":
    main()