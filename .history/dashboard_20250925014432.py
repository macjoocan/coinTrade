# dashboard.py - 터미널 대시보드 (인코딩 문제 해결)

import os
import time
import json
import pyupbit
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from config import TRADING_PAIRS, RISK_CONFIG

# Rich 콘솔 초기화
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
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style="bold on dark_blue"
        )
    
    def get_price_table(self):
        """가격 테이블 생성"""
        table = Table(title="Real-time Prices", show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Price", justify="right", style="white")
        table.add_column("Change", justify="right")
        table.add_column("Volume", justify="right", style="dim")
        
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            try:
                price_info = pyupbit.get_ticker(ticker)
                if price_info and len(price_info) > 0:
                    info = price_info[0]
                    current_price = info['trade_price']
                    change_rate = info['signed_change_rate'] * 100
                    volume = info['acc_trade_volume_24h']
                    
                    # 색상 설정
                    if change_rate > 0:
                        change_style = "green"
                        arrow = "↑"
                    elif change_rate < 0:
                        change_style = "red"
                        arrow = "↓"
                    else:
                        change_style = "yellow"
                        arrow = "="
                    
                    table.add_row(
                        symbol,
                        f"{current_price:,.0f}",
                        f"[{change_style}]{arrow} {abs(change_rate):.2f}%[/{change_style}]",
                        f"{volume:.2f}"
                    )
            except Exception as e:
                table.add_row(symbol, "N/A", "N/A", "N/A")
        
        return Panel(table, title="Market Status", border_style="cyan")
    
    def get_position_status(self):
        """포지션 상태 표시"""
        positions_text = []
        
        # trading.log 파일에서 포지션 정보 읽기
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-50:]  # 최근 50줄
                
                for line in reversed(lines):
                    if "[BUY]" in line or "매수 완료" in line:
                        # 시간과 내용 추출
                        if " - " in line:
                            parts = line.split(" - ")
                            if len(parts) >= 3:
                                time_str = parts[0].split(",")[0][-8:]
                                content = parts[-1].strip()
                                positions_text.append(f"BUY: {content}")
                    elif "[SELL]" in line or "매도 완료" in line:
                        if " - " in line:
                            parts = line.split(" - ")
                            if len(parts) >= 3:
                                time_str = parts[0].split(",")[0][-8:]
                                content = parts[-1].strip()
                                positions_text.append(f"SELL: {content}")
                    
                    if len(positions_text) >= 5:
                        break
                
                if not positions_text:
                    positions_text = ["No active positions"]
            else:
                positions_text = ["Log file not found"]
                
        except Exception as e:
            positions_text = [f"Error reading positions: {str(e)}"]
        
        return Panel(
            "\n".join(positions_text[:5]),
            title="Position Status",
            border_style="green"
        )
    
    def get_indicators_panel(self):
        """기술적 지표 패널"""
        indicators_text = []
        
        for symbol in TRADING_PAIRS[:3]:  # 상위 3개만 표시
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
                    
                    # 이동평균
                    ma20 = df['close'].rolling(20).mean().iloc[-1]
                    current = df['close'].iloc[-1]
                    
                    # RSI 상태
                    if rsi > 70:
                        rsi_status = "Overbought"
                        rsi_color = "red"
                    elif rsi < 30:
                        rsi_status = "Oversold"
                        rsi_color = "green"
                    else:
                        rsi_status = "Neutral"
                        rsi_color = "yellow"
                    
                    ma_diff = (current/ma20-1)*100
                    
                    indicators_text.append(
                        f"[bold]{symbol}[/bold]\n"
                        f"  RSI: [{rsi_color}]{rsi:.1f}[/{rsi_color}] ({rsi_status})\n"
                        f"  MA20: {ma20:,.0f}\n"
                        f"  Price/MA20: {ma_diff:+.1f}%"
                    )
            except Exception as e:
                indicators_text.append(f"{symbol}: Error - {str(e)[:30]}")
        
        return Panel(
            "\n\n".join(indicators_text) if indicators_text else "Calculating indicators...",
            title="Technical Indicators",
            border_style="yellow"
        )
    
    def get_recent_trades(self):
        """최근 거래 내역"""
        trades = []
        
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line in reversed(lines):
                    if "진입 점수:" in line or "entry score:" in line:
                        # 점수 정보 추출
                        if "점수:" in line:
                            score_part = line.split("점수:")[1].split("/")[0].strip()
                            trades.append(f"Score: {score_part}")
                    
                    if len(trades) >= 5:
                        break
                
                if not trades:
                    trades = ["No recent signals"]
            else:
                trades = ["Log file not found"]
                
        except Exception as e:
            trades = [f"Error: {str(e)[:50]}"]
        
        return Panel(
            "\n".join(trades[:5]),
            title="Recent Signals",
            border_style="magenta"
        )
    
    def get_footer(self):
        """푸터 정보"""
        try:
            # 오늘 날짜
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 거래 통계
            today_trades = 0
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    content = f.read()
                    today_trades = content.count(today) // 3  # 대략적인 계산
            
            stats_text = (
                f"Daily Trades: {today_trades}/10 | "
                f"Max Positions: {RISK_CONFIG.get('max_positions', 2)} | "
                f"Stop Loss: {RISK_CONFIG.get('stop_loss', 0.02)*100:.0f}% | "
                f"Target: 1.5%"
            )
        except Exception as e:
            stats_text = f"Error loading stats: {str(e)[:50]}"
        
        return Panel(
            stats_text,
            title="Trading Statistics",
            border_style="dim"
        )
    
    def update(self):
        """대시보드 업데이트"""
        try:
            self.layout["header"].update(self.get_header())
            self.layout["prices"].update(self.get_price_table())
            self.layout["positions"].update(self.get_position_status())
            self.layout["indicators"].update(self.get_indicators_panel())
            self.layout["trades"].update(self.get_recent_trades())
            self.layout["footer"].update(self.get_footer())
        except Exception as e:
            console.print(f"[red]Update error: {e}[/red]")
        
        return self.layout

def main():
    """메인 실행"""
    dashboard = TradingDashboard()
    
    print("\033[2J\033[H")  # 화면 클리어
    console.print("[bold cyan]Upbit Trading Dashboard Started[/bold cyan]")
    console.print("Exit: Ctrl+C\n")
    
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