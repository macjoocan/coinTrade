# dashboard.py - pyupbit 함수 수정 버전

import os
import time
import pyupbit
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from config import TRADING_PAIRS, RISK_CONFIG

console = Console()

class TradingDashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.setup_layout()
        
    def setup_layout(self):
        """레이아웃 구성"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=4)
        )
        
        self.layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        self.layout["left"].split(
            Layout(name="prices"),
            Layout(name="positions")
        )
        
        self.layout["right"].split(
            Layout(name="indicators"),
            Layout(name="trades")
        )
    
    def get_header(self):
        """헤더 생성"""
        return Panel(
            f"[bold cyan]Upbit Trading Dashboard[/bold cyan]\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style="bold on dark_blue"
        )
    
    def get_price_table(self):
        """가격 테이블 - pyupbit 올바른 함수 사용"""
        table = Table(title="Real-time Prices", show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Price", justify="right", style="white")
        table.add_column("Change", justify="right")
        
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            try:
                # 현재가 조회
                current_price = pyupbit.get_current_price(ticker)
                
                # 24시간 전 대비 변동률 계산 (orderbook 사용)
                orderbook = pyupbit.get_orderbook(ticker)
                if orderbook and len(orderbook) > 0:
                    change_rate = orderbook[0].get('change_rate', 0) * 100
                    change_price = orderbook[0].get('change_price', 0)
                    
                    # 색상 설정
                    if change_price > 0:
                        change_style = "green"
                        arrow = "↑"
                    elif change_price < 0:
                        change_style = "red"
                        arrow = "↓"
                    else:
                        change_style = "yellow"
                        arrow = "="
                else:
                    change_rate = 0
                    change_style = "yellow"
                    arrow = "="
                
                if current_price:
                    table.add_row(
                        symbol,
                        f"{current_price:,.0f}",
                        f"[{change_style}]{arrow} {abs(change_rate):.2f}%[/{change_style}]"
                    )
                else:
                    table.add_row(symbol, "N/A", "-")
                    
            except Exception as e:
                # 에러 발생 시 심플하게 표시
                table.add_row(symbol, "Error", "-")
        
        return Panel(table, title="Market Status", border_style="cyan")
    
    def get_position_status(self):
        """포지션 상태"""
        positions_text = ["No active positions"]
        
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-20:]
                    
                positions = []
                for line in reversed(lines):
                    if "매수 완료" in line or "[BUY]" in line:
                        positions.append(line.strip()[-50:])
                    if len(positions) >= 3:
                        break
                
                if positions:
                    positions_text = positions
                    
        except:
            pass
        
        return Panel(
            "\n".join(positions_text),
            title="Positions",
            border_style="green"
        )
    
    def get_indicators_panel(self):
        """기술적 지표"""
        indicators_text = []
        
        for symbol in TRADING_PAIRS[:2]:
            ticker = f"KRW-{symbol}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="minute60", count=20)
                if df is not None and len(df) >= 14:
                    # RSI 계산
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs)).iloc[-1]
                    
                    # MA20
                    ma20 = df['close'].rolling(20).mean().iloc[-1]
                    current = df['close'].iloc[-1]
                    
                    # RSI 색상
                    if rsi > 70:
                        rsi_color = "red"
                    elif rsi < 30:
                        rsi_color = "green"
                    else:
                        rsi_color = "yellow"
                    
                    indicators_text.append(
                        f"[bold]{symbol}[/bold]\n"
                        f"  RSI: [{rsi_color}]{rsi:.1f}[/{rsi_color}]\n"
                        f"  MA20: {ma20:,.0f}"
                    )
            except:
                pass
        
        return Panel(
            "\n\n".join(indicators_text) if indicators_text else "Loading...",
            title="Indicators",
            border_style="yellow"
        )
    
    def get_recent_trades(self):
        """최근 거래"""
        return Panel(
            "Recent trades will appear here",
            title="Trades",
            border_style="magenta"
        )
    
    def get_footer(self):
        """푸터"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        stats_text = (
            f"Daily Limit: 10 trades | "
            f"Max Positions: {RISK_CONFIG.get('max_positions', 2)} | "
            f"Stop Loss: {RISK_CONFIG.get('stop_loss', 0.02)*100:.0f}%"
        )
        
        return Panel(stats_text, title="Settings", border_style="dim")
    
    def update(self):
        """업데이트"""
        try:
            self.layout["header"].update(self.get_header())
            self.layout["prices"].update(self.get_price_table())
            self.layout["positions"].update(self.get_position_status())
            self.layout["indicators"].update(self.get_indicators_panel())
            self.layout["trades"].update(self.get_recent_trades())
            self.layout["footer"].update(self.get_footer())
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        
        return self.layout

def main():
    dashboard = TradingDashboard()
    
    console.print("[bold cyan]Starting Dashboard...[/bold cyan]")
    console.print("Press Ctrl+C to exit\n")
    
    try:
        with Live(dashboard.update(), refresh_per_second=0.5, console=console) as live:
            while True:
                time.sleep(2)
                live.update(dashboard.update())
    except KeyboardInterrupt:
        console.print("\n[bold red]Dashboard Stopped[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")

if __name__ == "__main__":
    main()