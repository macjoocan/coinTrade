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

    def get_monthly_stats_panel(self):
        """월간 통계 패널"""
        try:
            from daily_summary import DailySummary
            summary = DailySummary()
            stats = summary.get_statistics(30)
            
            lines = []
            lines.append("[bold cyan]30일 통계[/bold cyan]")
            lines.append("")
            
            pnl_color = "green" if stats['total_pnl'] > 0 else "red"
            lines.append(f"총 손익: [{pnl_color}]{stats['total_pnl']:+,.0f}[/{pnl_color}]")
            lines.append(f"일 평균: {stats['avg_daily_pnl']:+,.0f}")
            lines.append(f"평균 승률: {stats['avg_win_rate']:.1f}%")
            lines.append(f"수익일: {stats['winning_days']}일")
            lines.append(f"손실일: {stats['losing_days']}일")
            
            return Panel("\n".join(lines), title="Monthly Stats", border_style="cyan")
            
        except:
            return Panel("Loading...", title="Monthly Stats")
    
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
        self.dynamic_coins = []
        self.setup_layout()

    def setup_layout(self):
        """레이아웃 구성 - 수정"""
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
        
        # ▶ 여기 수정: left에 monthly 섹션 추가
        self.layout["left"].split(
            Layout(name="prices"),
            Layout(name="positions"),
            Layout(name="monthly")      # ← 추가
        )
        
        self.layout["center"].split(
            Layout(name="top_movers"),
            Layout(name="dynamic_coins")
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

    def get_dynamic_coins_panel(self):
        """동적 코인 상태 패널 - 개선된 스캐너 사용"""
        lines = []
        
        try:
            from momentum_scanner_improved import ImprovedMomentumScanner  # ✅ 변경
            scanner = ImprovedMomentumScanner()  # ✅ 변경
            dynamic_coins = scanner.scan_top_performers(top_n=3)
            
            if dynamic_coins:
                lines.append("[bold yellow]🔥 Momentum Coins[/bold yellow]")
                lines.append("")
                
                for coin in dynamic_coins:
                    ticker = f"KRW-{coin}"
                    try:
                        df = pyupbit.get_ohlcv(ticker, "day", 2)
                        if df is not None and len(df) >= 2:
                            change = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / 
                                    df['close'].iloc[-2] * 100)
                            
                            color = "green" if change > 0 else "red"
                            lines.append(f"{coin}: [{color}]{change:+.1f}%[/{color}]")
                    except:
                        lines.append(f"{coin}: [dim]데이터 없음[/dim]")
            else:
                lines.append("[dim]조건 충족 코인 없음[/dim]")
                lines.append("[dim]기준: 2% 이상, 점수 4점[/dim]")  # ✅ 기준 표시
                    
        except Exception as e:
            lines.append(f"[dim]로딩 실패: {str(e)[:20]}[/dim]")
        
        if not lines:
            lines.append("[dim]대기 중...[/dim]")
            
        return Panel(
            "\n".join(lines),
            title="🚀 Dynamic Coins (Improved)",  # ✅ 제목 변경
            border_style="yellow"
        )
    # def get_position_status(self):
    #     """포지션 상태"""
    #     positions_text = ["No recent trades"]
        
    #     try:
    #         if os.path.exists('trading.log'):
    #             with open('trading.log', 'r', encoding='utf-8') as f:
    #                 lines = f.readlines()[-20:]
    #                 positions = []
                    
    #                 for line in reversed(lines):
    #                     if "[BUY]" in line or "[SELL]" in line:
    #                         positions.append(line.strip()[-40:])
    #                     if len(positions) >= 3:
    #                         break
                    
    #                 if positions:
    #                     positions_text = positions
    #     except:
    #         pass
        
    #     return Panel(
    #         "\n".join(positions_text[:3]),
    #         title="Recent Trades",
    #         border_style="green"
    #     )

    def get_daily_profit_panel(self):
        """24시간 수익률 패널"""
        try:
            # trading.log 파일에서 24시간 내 거래 분석
            profit_data = self.calculate_24h_profit()
            
            lines = []
            lines.append(f"[bold cyan]24시간 수익률[/bold cyan]")
            lines.append("")
            
            # 총 수익률
            total_return = profit_data['total_return']
            if total_return > 0:
                color = "green"
                emoji = "📈"
            elif total_return < 0:
                color = "red"
                emoji = "📉"
            else:
                color = "yellow"
                emoji = "➡️"
            
            lines.append(f"{emoji} 총 수익률: [{color}]{total_return:+.2f}%[/{color}]")
            lines.append(f"💰 실현 손익: {profit_data['realized_pnl']:+,.0f} KRW")
            lines.append(f"📊 거래 횟수: {profit_data['trade_count']}회")
            
            # 승률
            if profit_data['trade_count'] > 0:
                win_rate = profit_data['win_rate']
                win_color = "green" if win_rate >= 50 else "red"
                lines.append(f"🎯 승률: [{win_color}]{win_rate:.1f}%[/{win_color}]")
            
            lines.append("")
            lines.append("[dim]업데이트: 1분마다[/dim]")
            
            return Panel(
                "\n".join(lines),
                title="24H Performance",
                border_style="cyan"
            )
            
        except Exception as e:
            return Panel(
                f"데이터 로딩 중...\n{str(e)[:30]}",
                title="24H Performance",
                border_style="dim"
            )

    def calculate_24h_profit(self):
        """24시간 수익률 계산"""
        result = {
            'total_return': 0.0,
            'realized_pnl': 0,
            'trade_count': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.0
        }
        
        try:
            # 로그 파일 읽기
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                now = datetime.now()
                cutoff_time = now - timedelta(hours=24)
                
                trades = []
                
                # 24시간 내 거래 파싱
                for line in lines:
                    try:
                        # 시간 파싱 (로그 형식: 2025-09-30 00:33:19,xxx)
                        if '2025-' in line and ('매수 완료' in line or '매도 완료' in line):
                            time_str = line.split(',')[0]
                            trade_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            
                            if trade_time > cutoff_time:
                                # PnL 추출 시도
                                if 'PnL:' in line:
                                    pnl_str = line.split('PnL:')[1].split('(')[0]
                                    pnl = float(pnl_str.replace(',', '').replace(' ', '').replace('+', ''))
                                    
                                    trades.append(pnl)
                                    result['realized_pnl'] += pnl
                                    
                                    if pnl > 0:
                                        result['win_count'] += 1
                                    else:
                                        result['loss_count'] += 1
                    except:
                        continue
                
                result['trade_count'] = len(trades)
                
                if result['trade_count'] > 0:
                    result['win_rate'] = (result['win_count'] / result['trade_count']) * 100
                
                # 초기 자본을 100만원으로 가정
                initial_capital = 1000000
                result['total_return'] = (result['realized_pnl'] / initial_capital) * 100
                
        except Exception as e:
            console.print(f"[dim]24h 계산 오류: {e}[/dim]")
        
        return result

    def calculate_detailed_24h_stats(self):
        """상세한 24시간 통계 계산"""
        wins = []
        losses = []
        total_pnl = 0
        
        try:
            if os.path.exists('trading.log'):
                with open('trading.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                now = datetime.now()
                cutoff_time = now - timedelta(hours=24)
                
                for line in lines:
                    try:
                        if '2025-' in line and 'PnL:' in line:
                            time_str = line.split(',')[0]
                            trade_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            
                            if trade_time > cutoff_time:
                                pnl_str = line.split('PnL:')[1].split('(')[0]
                                pnl = float(pnl_str.replace(',', '').replace(' ', '').replace('+', ''))
                                
                                total_pnl += pnl
                                if pnl > 0:
                                    wins.append(pnl)
                                else:
                                    losses.append(abs(pnl))
                    except:
                        continue
                
                # 통계 계산
                trade_count = len(wins) + len(losses)
                win_rate = (len(wins) / trade_count * 100) if trade_count > 0 else 0
                
                return {
                    'total_return': (total_pnl / 1000000) * 100,  # 100만원 기준
                    'realized_pnl': total_pnl,
                    'trade_count': trade_count,
                    'win_rate': win_rate,
                    'avg_win': sum(wins) / len(wins) if wins else 0,
                    'avg_loss': sum(losses) / len(losses) if losses else 0,
                    'max_win': max(wins) if wins else 0,
                    'max_loss': max(losses) if losses else 0
                }
                
        except Exception as e:
            console.print(f"[dim]통계 계산 오류: {e}[/dim]")
            
        return {
            'total_return': 0.0,
            'realized_pnl': 0,
            'trade_count': 0,
            'win_rate': 0.0,
            'avg_win': 0,
            'avg_loss': 0,
            'max_win': 0,
            'max_loss': 0
        }

    def get_enhanced_daily_profit_panel(self):
        """향상된 24시간 수익률 패널"""
        try:
            profit_data = self.calculate_detailed_24h_stats()
            
            # 테이블 생성
            table = Table(show_header=False, box=None, padding=(0,1))
            table.add_column("지표", style="cyan", width=10)
            table.add_column("값", justify="right", style="white")
            
            # 수익률 색상
            return_color = "green" if profit_data['total_return'] > 0 else "red"
            pnl_color = "green" if profit_data['realized_pnl'] > 0 else "red"
            
            # 데이터 행 추가
            table.add_row("수익률", f"[{return_color}]{profit_data['total_return']:+.2f}%[/{return_color}]")
            table.add_row("실현손익", f"[{pnl_color}]{profit_data['realized_pnl']:+,.0f}[/{pnl_color}]")
            table.add_row("거래횟수", f"{profit_data['trade_count']}회")
            
            if profit_data['trade_count'] > 0:
                win_color = "green" if profit_data['win_rate'] >= 50 else "red"
                table.add_row("승률", f"[{win_color}]{profit_data['win_rate']:.1f}%[/{win_color}]")
                
                if profit_data['avg_win'] > 0:
                    table.add_row("평균수익", f"[green]+{profit_data['avg_win']:,.0f}[/green]")
                if profit_data['avg_loss'] > 0:
                    table.add_row("평균손실", f"[red]-{profit_data['avg_loss']:,.0f}[/red]")
            
            return Panel(
                table,
                title="📊 24H Performance",
                border_style="cyan"
            )
            
        except Exception as e:
            return Panel(
                f"Loading...\n{str(e)[:30]}",
                title="📊 24H Performance",
                border_style="dim"
            )
    
    def get_indicators_panel(self):
        """실시간 간단 지표(RSI/MACD/Trend)"""
        try:
            import pandas as pd
            import numpy as np
            import pyupbit

            symbol = TRADING_PAIRS[0]
            ticker = f"KRW-{symbol}"
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is None or len(df) < 50:
                return Panel("Loading...", title="Indicators", border_style="yellow")

            price = df['close'].iloc[-1]
            # MA
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            # MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            macd = (ema12 - ema26).iloc[-1]
            macd_signal = (ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1]
            # Trend
            if df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1] and price > df['sma_20'].iloc[-1]:
                trend = "strong_up"
            elif df['sma_20'].iloc[-1] > df['sma_50'].iloc[-1]:
                trend = "up"
            elif df['sma_20'].iloc[-1] < df['sma_50'].iloc[-1]:
                trend = "down"
            else:
                trend = "sideways"

            table = Table(show_header=False, box=None, padding=(0,1))
            table.add_column("Key", style="cyan")
            table.add_column("Value", justify="right")
            table.add_row("Symbol", symbol)
            table.add_row("Price", f"{price:,.0f}")
            table.add_row("RSI(14)", f"{rsi:.1f}")
            table.add_row("MACD", f"{macd:.4f}")
            table.add_row("Signal", f"{macd_signal:.4f}")
            table.add_row("Trend", trend)

            return Panel(table, title="Indicators", border_style="yellow")
        except Exception as e:
            return Panel(f"Error: {str(e)[:60]}", title="Indicators", border_style="red")
    
    def get_recent_trades(self):
        """간단 신호(룰 기반)"""
        try:
            import pandas as pd
            import numpy as np
            import pyupbit

            symbol = TRADING_PAIRS[0]
            ticker = f"KRW-{symbol}"
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is None or len(df) < 50:
                return Panel("Loading...", title="Signals", border_style="magenta")

            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi = (100 - (100 / (1 + (gain / loss)))).iloc[-1]

            # MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            macd_signal = macd.ewm(span=9, adjust=False).mean()

            lines = [f"[bold]Symbol[/bold]: {symbol}"]
            # 단순 조건 예시
            if rsi < 30:
                lines.append("[green]RSI < 30: 매수 관심[/green]")
            elif rsi > 70:
                lines.append("[red]RSI > 70: 매도 관심[/red]")
            else:
                lines.append("RSI 중립 구간")

            # MACD 크로스 체크
            if macd.iloc[-2] <= macd_signal.iloc[-2] and macd.iloc[-1] > macd_signal.iloc[-1]:
                lines.append("[green]MACD 상승 교차: 매수 관심[/green]")
            elif macd.iloc[-2] >= macd_signal.iloc[-2] and macd.iloc[-1] < macd_signal.iloc[-1]:
                lines.append("[red]MACD 하락 교차: 매도 관심[/red]")
            else:
                lines.append("MACD 변화 없음")

            return Panel("\n".join(lines), title="Signals", border_style="magenta")
        except Exception as e:
            return Panel(f"Error: {str(e)[:60]}", title="Signals", border_style="red")

    
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
            self.layout["positions"].update(self.get_enhanced_daily_profit_panel())
            self.layout["top_movers"].update(self.get_top_movers_panel())
            self.layout["dynamic_coins"].update(self.get_dynamic_coins_panel())
            self.layout["indicators"].update(self.get_indicators_panel())
            self.layout["trades"].update(self.get_recent_trades())
            self.layout["footer"].update(self.get_footer())
            self.layout["monthly"].update(self.cache.get_monthly_stats_panel())
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