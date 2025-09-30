# dashboard.py - 24시간 변동률 표시 수정

import os
import time
import pyupbit
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from config import TRADING_PAIRS, RISK_CONFIG
from collections import deque

console = Console()

class MarketDataCache:
    """시장 데이터 캐싱 클래스"""
    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.daily_change_cache = {}  # 24시간 변동률 캐시 추가
        self.update_interval = 30  # 30초마다 가격 업데이트
        self.change_update_interval = 300  # 5분마다 변동률 업데이트
        self.top_movers = {'gainers': [], 'losers': []}
        self.last_movers_update = datetime.now() - timedelta(minutes=5)
        
    def get_price_with_change(self, ticker, force_update=False):
        """가격과 24시간 변동률 함께 반환"""
        now = datetime.now()
        symbol = ticker.replace("KRW-", "")
        
        # 가격 캐시 확인
        if not force_update and ticker in self.cache:
            if ticker in self.last_update:
                elapsed = (now - self.last_update[ticker]).total_seconds()
                if elapsed < self.update_interval:
                    # 캐시된 가격 사용
                    price = self.cache[ticker]
                else:
                    # 새로 가져오기
                    price = self._fetch_price(ticker)
            else:
                price = self._fetch_price(ticker)
        else:
            price = self._fetch_price(ticker)
        
        # 24시간 변동률 캐시 확인
        change_key = f"{ticker}_change"
        change_update_key = f"{ticker}_change_time"
        
        if change_key in self.daily_change_cache:
            if change_update_key in self.last_update:
                elapsed = (now - self.last_update[change_update_key]).total_seconds()
                if elapsed < self.change_update_interval:
                    # 캐시된 변동률 사용
                    change_rate = self.daily_change_cache[change_key]
                else:
                    # 새로 계산
                    change_rate = self._calculate_change(ticker)
            else:
                change_rate = self._calculate_change(ticker)
        else:
            change_rate = self._calculate_change(ticker)
        
        return price, change_rate
    
    def _fetch_price(self, ticker):
        """가격 가져오기"""
        try:
            price = pyupbit.get_current_price(ticker)
            if price:
                self.cache[ticker] = price
                self.last_update[ticker] = datetime.now()
                return price
        except:
            pass
        return self.cache.get(ticker, 0)
    
    def _calculate_change(self, ticker):
        """24시간 변동률 계산"""
        try:
            # 일봉 데이터로 계산 (API 호출 최소화)
            df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
            if df is not None and len(df) >= 2:
                yesterday_close = df['close'].iloc[-2]
                current_close = df['close'].iloc[-1]
                change_rate = ((current_close - yesterday_close) / yesterday_close) * 100
                
                # 캐시 저장
                change_key = f"{ticker}_change"
                change_update_key = f"{ticker}_change_time"
                self.daily_change_cache[change_key] = change_rate
                self.last_update[change_update_key] = datetime.now()
                
                return change_rate
        except:
            pass
        
        # 오류 시 캐시된 값 반환 또는 0
        change_key = f"{ticker}_change"
        return self.daily_change_cache.get(change_key, 0)
    
    def get_top_movers(self):
        """TOP 5 상승/하락 - 5분마다만 업데이트"""
        now = datetime.now()
        elapsed = (now - self.last_movers_update).total_seconds()
        
        # 5분 이내면 캐시 반환
        if elapsed < 300:
            return self.top_movers
        
        # 업데이트
        try:
            # 주요 30개 코인만 체크
            major_coins = [
                'BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX',
                'DOT', 'MATIC', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM',
                'TRX', 'SHIB', 'NEAR', 'BCH', 'APT', 'ARB', 'OP'
            ]
            
            market_data = []
            
            for i, symbol in enumerate(major_coins):
                ticker = f"KRW-{symbol}"
                try:
                    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                    
                    if df is not None and len(df) >= 2:
                        current_price = df['close'].iloc[-1]
                        yesterday_close = df['close'].iloc[-2]
                        change_rate = ((current_price - yesterday_close) / yesterday_close) * 100
                        
                        market_data.append({
                            'symbol': symbol,
                            'price': current_price,
                            'change': change_rate
                        })
                    
                    # API 호출 제한 방지
                    if i % 5 == 0:  # 5개마다 잠시 대기
                        time.sleep(0.1)
                    
                except:
                    continue
            
            # 정렬
            market_data.sort(key=lambda x: x['change'], reverse=True)
            
            self.top_movers = {
                'gainers': market_data[:5],
                'losers': market_data[-5:][::-1]
            }
            self.last_movers_update = now
            
        except Exception as e:
            console.print(f"[red]Error updating movers: {e}[/red]")
        
        return self.top_movers

class TradingDashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.cache = MarketDataCache()
        self.api_calls = deque(maxlen=100)
        self.setup_layout()
        
    def setup_layout(self):
        """레이아웃 구성"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5)
        )
        
        self.layout["body"].split_row(
            Layout(name="left"),
            Layout(name="center"),
            Layout(name="right")
        )
        
        self.layout["left"].split(
            Layout(name="prices"),
            Layout(name="positions")
        )
        
        self.layout["center"].split(
            Layout(name="top_movers"),
            Layout(name="api_status")
        )
        
        self.layout["right"].split(
            Layout(name="indicators"),
            Layout(name="trades")
        )
    
    def track_api_call(self):
        """API 호출 추적"""
        self.api_calls.append(datetime.now())
    
    def get_api_status(self):
        """API 호출 상태"""
        now = datetime.now()
        
        # 최근 1분간 호출 횟수
        recent_calls = [t for t in self.api_calls if (now - t).total_seconds() < 60]
        calls_per_minute = len(recent_calls)
        
        # 상태 판단
        if calls_per_minute > 500:
            status_color = "red"
            status_text = "CRITICAL"
        elif calls_per_minute > 300:
            status_color = "yellow"
            status_text = "WARNING"
        else:
            status_color = "green"
            status_text = "NORMAL"
        
        text = (
            f"API Calls/min: [{status_color}]{calls_per_minute}/600[/{status_color}]\n"
            f"Status: [{status_color}]{status_text}[/{status_color}]\n"
            f"Price Cache: {len(self.cache.cache)} items\n"
            f"Update: 30s (price), 5m (change)"
        )
        
        return Panel(text, title="API Status", border_style=status_color)
    
    def get_header(self):
        """헤더"""
        return Panel(
            f"[bold cyan]Upbit Dashboard - {', '.join(TRADING_PAIRS)}[/bold cyan]\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style="bold on dark_blue"
        )
    
    def get_price_table(self):
        """가격 테이블 - 24시간 변동률 포함"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Price", justify="right")
        table.add_column("24h Change", justify="right")
        
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            try:
                # 가격과 변동률 함께 가져오기
                price, change_rate = self.cache.get_price_with_change(ticker)
                self.track_api_call()
                
                if price:
                    # 색상 설정
                    if change_rate > 0:
                        change_color = "green"
                        arrow = "↑"
                        sign = "+"
                    elif change_rate < 0:
                        change_color = "red"
                        arrow = "↓"
                        sign = ""
                    else:
                        change_color = "yellow"
                        arrow = "→"
                        sign = ""
                    
                    # 가격 포맷팅
                    if price > 1000:
                        price_str = f"{price:,.0f}"
                    elif price > 1:
                        price_str = f"{price:.2f}"
                    else:
                        price_str = f"{price:.4f}"
                    
                    table.add_row(
                        symbol,
                        price_str,
                        f"[{change_color}]{arrow} {sign}{change_rate:.2f}%[/{change_color}]"
                    )
                else:
                    table.add_row(symbol, "N/A", "-")
                    
            except Exception as e:
                console.print(f"[dim]Error {symbol}: {str(e)[:30]}[/dim]")
                table.add_row(symbol, "Error", "-")
        
        return Panel(table, title="Watchlist", border_style="cyan")
    
    def get_top_movers_panel(self):
        """TOP 5 통합 패널"""
        movers = self.cache.get_top_movers()
        
        text_lines = ["[bold green]📈 Top Gainers[/bold green]"]
        for i, coin in enumerate(movers['gainers'][:3], 1):
            text_lines.append(
                f"{i}. {coin['symbol']}: [green]+{coin['change']:.1f}%[/green]"
            )
        
        text_lines.append("")
        text_lines.append("[bold red]📉 Top Losers[/bold red]")
        for i, coin in enumerate(movers['losers'][:3], 1):
            text_lines.append(
                f"{i}. {coin['symbol']}: [red]{coin['change']:.1f}%[/red]"
            )
        
        update_time = self.cache.last_movers_update.strftime('%H:%M:%S')
        text_lines.append(f"\n[dim]Updated: {update_time}[/dim]")
        
        return Panel(
            "\n".join(text_lines),
            title="Market Movers (5min cache)",
            border_style="yellow"
        )
    
    def get_position_status(self):
        """포지션 상태"""
        positions_text = ["No recent trades"]
        
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-20:]
                    positions = []
                    
                    for line in reversed(lines):
                        if "[BUY]" in line or "[SELL]" in line:
                            positions.append(line.strip()[-40:])
                        if len(positions) >= 3:
                            break
                    
                    if positions:
                        positions_text = positions
        except:
            pass
        
        return Panel(
            "\n".join(positions_text[:3]),
            title="Recent Trades",
            border_style="green"
        )
    
    def get_indicators_panel(self):
        """간단한 지표"""
        return Panel(
            "RSI indicators\nUpdated every 5min\nfor performance",
            title="Indicators",
            border_style="yellow"
        )
    
    def get_recent_trades(self):
        """신호"""
        return Panel(
            "Trading signals\nMonitoring...",
            title="Signals",
            border_style="magenta"
        )
    
    def get_footer(self):
        """푸터"""
        cache_info = (
            f"Cache: {len(self.cache.cache)} prices, "
            f"{len(self.cache.daily_change_cache)} changes\n"
            f"Update intervals: 30s (price), 5m (24h change)\n"
            f"Max Positions: {RISK_CONFIG.get('max_positions', 2)} | "
            f"Stop Loss: {RISK_CONFIG.get('stop_loss', 0.02)*100:.0f}%"
        )
        
        return Panel(cache_info, title="Settings", border_style="dim")
    
    def update(self):
        """업데이트"""
        try:
            self.layout["header"].update(self.get_header())
            self.layout["prices"].update(self.get_price_table())
            self.layout["positions"].update(self.get_position_status())
            self.layout["top_movers"].update(self.get_top_movers_panel())
            self.layout["api_status"].update(self.get_api_status())
            self.layout["indicators"].update(self.get_indicators_panel())
            self.layout["trades"].update(self.get_recent_trades())
            self.layout["footer"].update(self.get_footer())
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        
        return self.layout

def main():
    dashboard = TradingDashboard()
    
    console.clear()
    console.print("[bold cyan]Upbit Dashboard - Optimized Version[/bold cyan]")
    console.print("[yellow]Loading... First update may take a few seconds.[/yellow]")
    console.print("Press Ctrl+C to exit\n")
    
    try:
        with Live(dashboard.update(), refresh_per_second=0.5, console=console) as live:
            while True:
                time.sleep(5)  # 5초마다 화면 업데이트
                live.update(dashboard.update())
    except KeyboardInterrupt:
        console.print("\n[bold red]Dashboard stopped[/bold red]")

if __name__ == "__main__":
    main()