# dashboard.py - Market Movers 수정 및 안정화 버전

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

# 프리셋 적용
apply_preset(ACTIVE_PRESET)
console = Console()

class MarketDataCache:
    """시장 데이터 캐싱 및 최적화 클래스"""
    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.top_movers = {'gainers': [], 'losers': []}
        self.last_movers_update = datetime.now() - timedelta(minutes=10) # 즉시 업데이트 유도
        self.update_interval = 20
        self.market_analyzer = MarketAnalyzer()
        
    def get_prices_batch(self, tickers):
        """여러 코인 가격 한 번에 조회"""
        try:
            full_tickers = [f"KRW-{t}" for t in tickers]
            prices = pyupbit.get_current_price(full_tickers)
            if isinstance(prices, dict):
                return prices
            elif isinstance(prices, float):
                return {full_tickers[0]: prices}
            return {}
        except Exception as e:
            return {}

    def get_rsi(self, ticker):
        """RSI 계산"""
        now = datetime.now()
        cache_key = f"{ticker}_rsi"
        
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
        """✅ 수정됨: 전체 KRW 마켓 대상 조회 (안정성 강화)"""
        now = datetime.now()
        
        # 5분 캐시 (데이터가 있으면 리턴)
        if (now - self.last_movers_update).total_seconds() < 300 and self.top_movers['gainers']:
            return self.top_movers
            
        try:
            # 1. 전체 KRW 마켓 티커 조회
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            
            # 2. 업비트 API 제한을 고려하여 100개까지만 조회
            if len(all_tickers) > 100:
                all_tickers = all_tickers[:100]
            
            # 3. 전체 시세 조회
            tickers_data = pyupbit.get_ticker(all_tickers)
            
            if not tickers_data:
                return self.top_movers # 실패 시 기존 데이터 반환

            market_data = []
            for data in tickers_data:
                try:
                    symbol = data['market'].replace('KRW-', '')
                    change_rate = data['signed_change_rate'] * 100
                    trade_price = data['trade_price']
                    
                    market_data.append({
                        'symbol': symbol,
                        'price': trade_price,
                        'change': change_rate
                    })
                except:
                    continue
            
            # 4. 정렬 (상승률 순)
            market_data.sort(key=lambda x: x['change'], reverse=True)
            
            self.top_movers = {
                'gainers': market_data[:5],
                'losers': market_data[-5:][::-1]
            }
            self.last_movers_update = now
            
        except Exception as e:
            # 에러 발생 시 그냥 넘어감 (화면 멈춤 방지)
            pass
            
        return self.top_movers

class TradingDashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.cache = MarketDataCache()
        self.trade_history = TradeHistoryManager()
        self.api_calls = deque(maxlen=100)
        
        self.recent_trades_cache = []
        self.last_trades_update = datetime.now() - timedelta(minutes=1)
        self.stats_cache = {'24h': None, '7d': None, '30d': None}
        self.last_stats_update = datetime.now() - timedelta(minutes=5)
        
        # 총 자산 계산용
        self.total_assets = 0
        self.last_asset_update = datetime.now() - timedelta(minutes=1)
        self.upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))

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
        table = Table(show_header=True, header_style="bold magenta", expand=True)
        table.add_column("Coin", style="cyan", width=6)
        table.add_column("Price", justify="right")
        table.add_column("RSI", justify="center", width=6)
        table.add_column("Chg%", justify="right")
        
        prices = self.cache.get_prices_batch(TRADING_PAIRS[:8])
        self.track_api_call()

        for symbol in TRADING_PAIRS[:8]:
            ticker = f"KRW-{symbol}"
            price = prices.get(ticker, 0)
            rsi = self.cache.get_rsi(ticker)
            
            if rsi <= 30: rsi_str = f"[bold green]{rsi:.0f}[/bold green]"
            elif rsi >= 70: rsi_str = f"[bold red]{rsi:.0f}[/bold red]"
            else: rsi_str = f"{rsi:.0f}"
            
            if price > 0:
                price_fmt = f"{price:,.0f}" if price >= 100 else f"{price:.2f}"
                table.add_row(symbol, price_fmt, rsi_str, "-")
            else:
                table.add_row(symbol, "N/A", "-", "-")
                
        return Panel(table, title="💰 Watchlist", border_style="cyan")

    def get_market_movers_panel(self):
        """✅ 수정됨: 데이터 로딩 상태 표시 추가"""
        movers = self.cache.get_top_movers_optimized()
        
        lines = []
        if not movers['gainers']:
            lines.append("[dim]Loading data...[/dim]")
            lines.append("[dim](Fetching top 100 coins)[/dim]")
        else:
            lines = ["[bold]🔥 Top Gainers[/bold]"]
            for c in movers['gainers'][:3]:
                lines.append(f"[green]{c['symbol']}: +{c['change']:.1f}%[/green] ({c['price']:,.0f})")
                
            lines.append("\n[bold]💧 Top Losers[/bold]")
            for c in movers['losers'][:3]:
                lines.append(f"[red]{c['symbol']}: {c['change']:.1f}%[/red] ({c['price']:,.0f})")
            
        return Panel("\n".join(lines), title="📊 Market Movers", border_style="yellow")

    def get_active_positions_panel(self):
        try:
            import json
            if not os.path.exists('active_positions.json'):
                return Panel("No active positions", title="📦 Positions", border_style="green")
                
            with open('active_positions.json', 'r') as f:
                data = json.load(f)
                positions = data.get('positions', {})
            
            if not positions:
                return Panel("No active positions", title="📦 Positions", border_style="green")
                
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

    def get_mtf_analysis_panel(self):
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
            time.sleep(1)

if __name__ == "__main__":
    main()