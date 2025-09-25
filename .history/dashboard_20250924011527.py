# dashboard.py - 터미널에서 실시간 모니터링

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
from rich.progress import Progress, BarColumn, TextColumn
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
            f"[bold cyan]🤖 업비트 트레이딩 대시보드[/bold cyan]\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style="bold on dark_blue"
        )
    
    def get_price_table(self):
        """가격 테이블 생성"""
        table = Table(title="📈 실시간 가격", show_header=True, header_style="bold magenta")
        table.add_column("종목", style="cyan", width=8)
        table.add_column("현재가", justify="right", style="white")
        table.add_column("변동률", justify="right")
        table.add_column("거래량", justify="right", style="dim")
        
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
                        arrow = "▲"
                    elif change_rate < 0:
                        change_style = "red"
                        arrow = "▼"
                    else:
                        change_style = "yellow"
                        arrow = "="
                    
                    table.add_row(
                        symbol,
                        f"{current_price:,.0f}",
                        f"[{change_style}]{arrow} {abs(change_rate):.2f}%[/{change_style}]",
                        f"{volume:.0f}"
                    )
            except:
                table.add_row(symbol, "-", "-", "-")
        
        return Panel(table, title="💹 시장 현황", border_style="cyan")
    
    def get_position_status(self):
        """포지션 상태 표시"""
        # 실제 포지션 정보를 읽어옴 (파일이나 API에서)
        try:
            with open('trading.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()[-20:]  # 최근 20줄
                
            positions = []
            for line in lines:
                if "포지션 추가" in line:
                    positions.append(line.strip())
            
            if positions:
                text = "\n".join(positions[-5:])  # 최근 5개
            else:
                text = "활성 포지션 없음"
        except:
            text = "포지션 정보 없음"
        
        return Panel(
            text,
            title="📦 포지션 현황",
            border_style="green"
        )
    
    def get_indicators_panel(self):
        """기술적 지표 패널"""
        indicators_text = []
        
        for symbol in TRADING_PAIRS[:2]:  # 상위 2개만 표시
            ticker = f"KRW-{symbol}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="minute60", count=20)
                if df is not None and len(df) > 14:
                    # RSI 계산
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs)).iloc[-1]
                    
                    # 이동평균
                    ma20 = df['close'].rolling(20).mean().iloc[-1]
                    current = df['close'].iloc[-1]
                    
                    # RSI 색상
                    if rsi > 70:
                        rsi_color = "red"
                        rsi_status = "과매수"
                    elif rsi < 30:
                        rsi_color = "green"
                        rsi_status = "과매도"
                    else:
                        rsi_color = "yellow"
                        rsi_status = "중립"
                    
                    indicators_text.append(
                        f"[bold]{symbol}[/bold]\n"
                        f"  RSI: [{rsi_color}]{rsi:.1f} ({rsi_status})[/{rsi_color}]\n"
                        f"  MA20: {ma20:,.0f}\n"
                        f"  현재가/MA20: {(current/ma20-1)*100:+.1f}%"
                    )
            except:
                pass
        
        return Panel(
            "\n\n".join(indicators_text) if indicators_text else "지표 계산 중...",
            title="📊 기술적 지표",
            border_style="yellow"
        )
    
    def get_recent_trades(self):
        """최근 거래 내역"""
        try:
            with open('trading.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            trades = []
            for line in reversed(lines):
                if "매수 완료" in line or "매도 완료" in line:
                    # 시간 추출
                    parts = line.split(' - ')
                    if len(parts) >= 2:
                        time_part = parts[0].strip()
                        trade_part = parts[-1].strip()
                        
                        if "매수" in trade_part:
                            icon = "🟢"
                        else:
                            icon = "🔴"
                        
                        trades.append(f"{icon} {time_part[-8:]}: {trade_part}")
                        
                        if len(trades) >= 5:
                            break
            
            return Panel(
                "\n".join(trades) if trades else "거래 내역 없음",
                title="📜 최근 거래",
                border_style="magenta"
            )
        except:
            return Panel("거래 내역 없음", title="📜 최근 거래", border_style="magenta")
    
    def get_footer(self):
        """푸터 정보"""
        try:
            # 로그에서 통계 추출
            with open('trading.log', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 오늘 거래 횟수 계산
            today = datetime.now().strftime('%Y-%m-%d')
            today_trades = content.count(f"{today}") // 2  # 대략적인 계산
            
            stats_text = (
                f"📅 일일 거래: {today_trades}/10 | "
                f"💼 최대 포지션: {RISK_CONFIG['max_positions']} | "
                f"🛑 손절선: {RISK_CONFIG['stop_loss']*100:.0f}% | "
                f"🎯 목표 수익: 1.5%"
            )
        except:
            stats_text = "통계 로딩 중..."
        
        return Panel(
            stats_text,
            title="📊 거래 통계",
            border_style="dim"
        )
    
    def update(self):
        """대시보드 업데이트"""
        self.layout["header"].update(self.get_header())
        self.layout["prices"].update(self.get_price_table())
        self.layout["positions"].update(self.get_position_status())
        self.layout["indicators"].update(self.get_indicators_panel())
        self.layout["trades"].update(self.get_recent_trades())
        self.layout["footer"].update(self.get_footer())
        
        return self.layout

def main():
    """메인 실행"""
    dashboard = TradingDashboard()
    
    print("\033[2J\033[H")  # 화면 클리어
    console.print("[bold cyan]업비트 트레이딩 대시보드 시작[/bold cyan]")
    console.print("종료: Ctrl+C\n")
    
    with Live(dashboard.update(), refresh_per_second=0.5, console=console) as live:
        try:
            while True:
                time.sleep(2)
                live.update(dashboard.update())
        except KeyboardInterrupt:
            console.print("\n[bold red]대시보드 종료[/bold red]")

if __name__ == "__main__":
    main()