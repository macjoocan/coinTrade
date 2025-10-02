# dashboard.py - TOP 5 상승/하락 코인 추가

import os
import time
import pyupbit
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from config import TRADING_PAIRS, RISK_CONFIG

console = Console()

class TradingDashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.setup_layout()
        self.price_cache = {}
        
    def setup_layout(self):
        """레이아웃 구성 - 확장된 버전"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=4)
        )
        
        # 3단 구조로 변경
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
            Layout(name="top_gainers"),  # 상승 TOP 5
            Layout(name="top_losers")    # 하락 TOP 5
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
    
    def get_market_movers(self):
        """전체 KRW 마켓 상승/하락 TOP 5 조회"""
        try:
            # 모든 KRW 마켓 티커 가져오기
            all_tickers = pyupbit.get_tickers(fiat="KRW")
            
            market_data = []
            
            for ticker in all_tickers[:100]:  # 상위 100개만 체크 (성능)
                try:
                    # 현재가 조회
                    current_price = pyupbit.get_current_price(ticker)
                    
                    if current_price:
                        # 일봉 데이터로 24시간 변동률 계산
                        df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                        
                        if df is not None and len(df) >= 2:
                            yesterday_close = df['close'].iloc[-2]
                            change_rate = ((current_price - yesterday_close) / yesterday_close) * 100
                            
                            # 거래량 확인 (너무 작은 코인 제외)
                            volume = df['volume'].iloc[-1] * current_price
                            
                            if volume > 1000000000:  # 10억원 이상 거래량
                                symbol = ticker.replace("KRW-", "")
                                market_data.append({
                                    'symbol': symbol,
                                    'price': current_price,
                                    'change': change_rate,
                                    'volume': volume
                                })
                except:
                    continue
            
            # 변동률 기준 정렬
            market_data.sort(key=lambda x: x['change'], reverse=True)
            
            return {
                'gainers': market_data[:5],    # 상승 TOP 5
                'losers': market_data[-5:][::-1]  # 하락 TOP 5 (역순)
            }
            
        except Exception as e:
            console.print(f"[red]Error getting market movers: {e}[/red]")
            return {'gainers': [], 'losers': []}
    
    def get_top_gainers_panel(self):
        """상승 TOP 5 패널"""
        movers = self.get_market_movers()
        
        table = Table(show_header=True, header_style="bold green")
        table.add_column("Rank", style="cyan", width=4)
        table.add_column("Symbol", style="white", width=8)
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right", style="green")
        
        for i, coin in enumerate(movers['gainers'], 1):
            # 가격 포맷팅
            if coin['price'] > 1000:
                price_str = f"{coin['price']:,.0f}"
            elif coin['price'] > 1:
                price_str = f"{coin['price']:.1f}"
            else:
                price_str = f"{coin['price']:.3f}"
            
            table.add_row(
                str(i),
                coin['symbol'][:8],  # 심볼 길이 제한
                price_str,
                f"↑ +{coin['change']:.2f}%"
            )
        
        # 데이터가 없을 경우
        if not movers['gainers']:
            table.add_row("-", "Loading...", "-", "-")
        
        return Panel(table, title="🚀 Top Gainers (24h)", border_style="green")
    
    def get_top_losers_panel(self):
        """하락 TOP 5 패널"""
        movers = self.get_market_movers()
        
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Rank", style="cyan", width=4)
        table.add_column("Symbol", style="white", width=8)
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right", style="red")
        
        for i, coin in enumerate(movers['losers'], 1):
            # 가격 포맷팅
            if coin['price'] > 1000:
                price_str = f"{coin['price']:,.0f}"
            elif coin['price'] > 1:
                price_str = f"{coin['price']:.1f}"
            else:
                price_str = f"{coin['price']:.3f}"
            
            table.add_row(
                str(i),
                coin['symbol'][:8],
                price_str,
                f"↓ {coin['change']:.2f}%"
            )
        
        # 데이터가 없을 경우
        if not movers['losers']:
            table.add_row("-", "Loading...", "-", "-")
        
        return Panel(table, title="📉 Top Losers (24h)", border_style="red")
    
    def get_price_table(self):
        """거래 대상 코인 가격 테이블"""
        table = Table(title="Trading Pairs", show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=6)
        table.add_column("Price", justify="right", style="white")
        table.add_column("24h", justify="right")
        
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            try:
                current_price = pyupbit.get_current_price(ticker)
                
                if current_price:
                    # 24시간 변동률
                    try:
                        df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                        if len(df) >= 2:
                            yesterday_close = df['close'].iloc[-2]
                            change_rate = ((current_price - yesterday_close) / yesterday_close) * 100
                        else:
                            change_rate = 0
                    except:
                        change_rate = 0
                    
                    # 색상 설정
                    if change_rate > 0:
                        change_style = "green"
                        arrow = "↑"
                        sign = "+"
                    elif change_rate < 0:
                        change_style = "red"
                        arrow = "↓"
                        sign = ""
                    else:
                        change_style = "yellow"
                        arrow = "="
                        sign = ""
                    
                    table.add_row(
                        symbol,
                        f"{current_price:,.0f}",
                        f"[{change_style}]{arrow}{sign}{change_rate:.1f}%[/{change_style}]"
                    )
                else:
                    table.add_row(symbol, "N/A", "-")
                    
            except Exception as e:
                table.add_row(symbol, "Error", "-")
        
        return Panel(table, title="Watchlist", border_style="cyan")
    
    def get_position_status(self):
        """포지션 상태"""
        positions_text = []
        
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        for line in reversed(lines[-50:]):
                            if "[BUY]" in line or "매수 완료" in line:
                                if " - " in line:
                                    content = line.split(" - ")[-1].strip()
                                    content = content.replace("[BUY]", "").replace("매수 완료:", "").strip()
                                    positions_text.append(f"BUY: {content[:30]}")
                            elif "[SELL]" in line or "매도 완료" in line:
                                if " - " in line:
                                    content = line.split(" - ")[-1].strip()
                                    content = content.replace("[SELL]", "").replace("매도 완료:", "").strip()
                                    positions_text.append(f"SELL: {content[:30]}")
                            
                            if len(positions_text) >= 4:
                                break
            
            if not positions_text:
                positions_text = ["No recent trades"]
                
        except Exception as e:
            positions_text = [f"Error: {str(e)[:30]}"]
        
        return Panel(
            "\n".join(positions_text[:4]),
            title="Recent Trades",
            border_style="green"
        )
    
    def get_indicators_panel(self):
        """기술적 지표"""
        indicators_text = []
        
        for symbol in TRADING_PAIRS[:3]:
            ticker = f"KRW-{symbol}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval="minute60", count=20)
                if df is not None and len(df) >= 14:
                    # RSI
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs)).iloc[-1]
                    
                    # RSI 상태
                    if rsi > 70:
                        rsi_color = "red"
                        status = "OB"
                    elif rsi < 30:
                        rsi_color = "green"
                        status = "OS"
                    else:
                        rsi_color = "yellow"
                        status = "N"
                    
                    indicators_text.append(
                        f"{symbol}: RSI[{rsi_color}]{rsi:.0f}({status})[/{rsi_color}]"
                    )
            except:
                pass
        
        return Panel(
            "\n".join(indicators_text) if indicators_text else "Loading...",
            title="Indicators",
            border_style="yellow"
        )
    
    def get_recent_trades(self):
        """거래 신호"""
        signals = []
        
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                    for line in reversed(lines[-100:]):
                        if "진입 점수:" in line:
                            try:
                                score_part = line.split("진입 점수:")[1].split("/")[0].strip()
                                time_part = line[:8] if len(line) > 8 else ""
                                signals.append(f"{time_part} S:{score_part}")
                            except:
                                pass
                        
                        if len(signals) >= 4:
                            break
            
            if not signals:
                signals = ["No signals"]
                
        except:
            signals = ["Error"]
        
        return Panel(
            "\n".join(signals[:4]),
            title="Signals",
            border_style="magenta"
        )
    
    def get_footer(self):
        """설정 정보"""
        stats_text = (
            f"Daily: 10 | Pos: {RISK_CONFIG.get('max_positions', 2)} | "
            f"Stop: {RISK_CONFIG.get('stop_loss', 0.02)*100:.0f}% | Target: 1.5%"
        )
        
        return Panel(stats_text, title="Config", border_style="dim")
    
    def update(self):
        """대시보드 업데이트"""
        try:
            self.layout["header"].update(self.get_header())
            self.layout["prices"].update(self.get_price_table())
            self.layout["positions"].update(self.get_position_status())
            self.layout["top_gainers"].update(self.get_top_gainers_panel())
            self.layout["top_losers"].update(self.get_top_losers_panel())
            self.layout["indicators"].update(self.get_indicators_panel())
            self.layout["trades"].update(self.get_recent_trades())
            self.layout["footer"].update(self.get_footer())
        except Exception as e:
            console.print(f"[red]Update error: {e}[/red]")
        
        return self.layout

def main():
    dashboard = TradingDashboard()
    
    console.clear()
    console.print("[bold cyan]Upbit Trading Dashboard with Market Movers[/bold cyan]")
    console.print("Press Ctrl+C to exit\n")
    
    try:
        # 초기 로딩 메시지
        console.print("[yellow]Loading market data... This may take a moment.[/yellow]")
        
        with Live(dashboard.update(), refresh_per_second=0.2, console=console) as live:
            while True:
                time.sleep(10)  # 10초마다 업데이트 (TOP 5는 API 호출이 많음)
                live.update(dashboard.update())
    except KeyboardInterrupt:
        console.print("\n[bold red]Dashboard stopped[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")

if __name__ == "__main__":
    main()