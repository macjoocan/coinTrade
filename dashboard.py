# dashboard.py - 최근 거래 내역 추가

import os
import time
import pyupbit
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from config import TRADING_PAIRS, RISK_CONFIG
from collections import deque
from trade_history_manager import TradeHistoryManager  # ✅ 추가
from config import TRADING_PAIRS, RISK_CONFIG, apply_preset, ACTIVE_PRESET, UPBIT_CONFIG
import logging

apply_preset(ACTIVE_PRESET)
console = Console()

class MarketDataCache:
    """시장 데이터 캐싱 클래스"""
    def __init__(self):
        self.cache = {}
        self.last_update = {}
        self.daily_change_cache = {}
        self.rsi_cache = {}  # ✅ RSI 캐시 추가
        self.update_interval = 2
        self.change_update_interval = 300
        self.top_movers = {'gainers': [], 'losers': []}
        self.last_movers_update = datetime.now() - timedelta(minutes=5)
        self.stats_cache = {'24h': None, '7d': None, '30d': None}
        self.last_stats_update = datetime.now() - timedelta(minutes=5)
        self.stats_cache_interval = 300  # 5분
   
    def get_price_only(self, ticker):
        """✅ 24시간 변동률 없이 현재가만 즉시 반환 (포지션 갱신용)"""
        now = datetime.now()
        
        # 캐시된 가격이 있고 업데이트 주기가 지나지 않았다면 즉시 반환
        if ticker in self.cache:
            elapsed = (now - self.last_update.get(ticker, datetime.min)).total_seconds()
            if elapsed < self.update_interval:
                return self.cache[ticker]
        
        # 주기가 지났다면 API 호출
        return self._fetch_price(ticker)
        
    def get_price_with_change(self, ticker, force_update=False):
        """가격과 24시간 변동률 함께 반환"""
        now = datetime.now()
        symbol = ticker.replace("KRW-", "")
        
        if not force_update and ticker in self.cache:
            if ticker in self.last_update:
                elapsed = (now - self.last_update[ticker]).total_seconds()
                if elapsed < self.update_interval:
                    price = self.cache[ticker]
                else:
                    price = self._fetch_price(ticker)
            else:
                price = self._fetch_price(ticker)
        else:
            price = self._fetch_price(ticker)
        
        change_key = f"{ticker}_change"
        change_update_key = f"{ticker}_change_time"
        
        if change_key in self.daily_change_cache:
            if change_update_key in self.last_update:
                elapsed = (now - self.last_update[change_update_key]).total_seconds()
                if elapsed < self.change_update_interval:
                    change_rate = self.daily_change_cache[change_key]
                else:
                    change_rate = self._calculate_change(ticker)
            else:
                change_rate = self._calculate_change(ticker)
        else:
            change_rate = self._calculate_change(ticker)
        
        return price, change_rate

    def get_rsi(self, ticker):
        """✅ Watchlist용 RSI 지표 계산 (60분 봉 기준)"""
        now = datetime.now()
        cache_key = f"{ticker}_rsi"
        
        # 1분 이내 데이터는 캐시 사용
        if cache_key in self.rsi_cache and (now - self.last_update.get(cache_key, datetime.min)).total_seconds() < 60:
            return self.rsi_cache[cache_key]
            
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=50)
            if df is not None and len(df) >= 14:
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi_series = 100 - (100 / (1 + rs))
                current_rsi = rsi_series.iloc[-1]
                
                self.rsi_cache[cache_key] = current_rsi
                self.last_update[cache_key] = now
                return current_rsi
        except:
            pass
        return 50.0 # 기본값
    
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
            df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
            if df is not None and len(df) >= 2:
                yesterday_close = df['close'].iloc[-2]
                current_close = df['close'].iloc[-1]
                change_rate = ((current_close - yesterday_close) / yesterday_close) * 100
                
                change_key = f"{ticker}_change"
                change_update_key = f"{ticker}_change_time"
                self.daily_change_cache[change_key] = change_rate
                self.last_update[change_update_key] = datetime.now()
                
                return change_rate
        except:
            pass
        
        change_key = f"{ticker}_change"
        return self.daily_change_cache.get(change_key, 0)
    
    def get_top_movers(self):
        """TOP 5 상승/하락"""
        now = datetime.now()
        elapsed = (now - self.last_movers_update).total_seconds()
        
        if elapsed < 300:
            return self.top_movers
        
        try:
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
                    
                    if i % 5 == 0:
                        time.sleep(0.1)
                    
                except:
                    continue
            
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
        
        # ✅ 거래 기록 매니저 추가
        self.trade_history = TradeHistoryManager()
        
        # ✅✅✅ 캐시 추가 ✅✅✅
        self.recent_trades_cache = []
        self.last_trades_update = datetime.now() - timedelta(seconds=60)
        self.trades_cache_interval = 30  # 30초
        
        self.stats_cache = {'24h': None, '7d': None, '30d': None}
        self.last_stats_update = datetime.now() - timedelta(minutes=5)
        self.stats_cache_interval = 300  # 5분
        
        self.api_calls = deque(maxlen=100)
        self.dynamic_coins = []
        self.setup_layout()
        
        # ✅ 포지션 캐시 초기화
        self.cached_positions = {}
        self.last_pos_file_read = datetime.now() - timedelta(seconds=10)
        self.pos_cache_interval = 1 # 1초마다 파일 읽기

    def setup_layout(self):
        """✅ 레이아웃 구성 - Center 순서 조정"""
        # 메인 레이아웃: 상단(헤더) + 중단(메인 콘텐츠) + 하단(통계)
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="stats", size=12),
            Layout(name="footer", size=3)
        )
        
        # 메인 콘텐츠: 좌/중/우
        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # 좌측: 가격 + 최근 거래 (2분할)
        self.layout["left"].split(
            Layout(name="prices", ratio=3),
            Layout(name="recent_trades", ratio=2)
        )
        
        # ✅ 중앙: Top Movers → Dynamic Coins → Positions (3분할)
        self.layout["center"].split(
            Layout(name="top_movers", ratio=2),
            Layout(name="dynamic_coins", ratio=2),
            Layout(name="positions", ratio=2)
        )
        
        # 우측: MTF 분석 + ML 예측
        self.layout["right"].split(
            Layout(name="mtf_analysis"),
            Layout(name="ml_prediction")
        )
        
        # 하단 통계: 24h, 7d, 30d 가로 배치
        self.layout["stats"].split_row(
            Layout(name="stats_24h"),
            Layout(name="stats_7d"),
            Layout(name="stats_30d")
        )
        
    def track_api_call(self):
        """API 호출 추적"""
        self.api_calls.append(datetime.now())
    
    def get_header(self):
        """헤더"""
        return Panel(
            f"[bold cyan]🚀 Upbit Advanced Trading Dashboard[/bold cyan]\n"
            f"[yellow]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/yellow] | "
            f"Coins: {', '.join(TRADING_PAIRS[:5])}{'...' if len(TRADING_PAIRS) > 5 else ''}",
            style="bold on dark_blue"
        )
    
    def get_price_table(self):
        """가격 테이블 (RSI 지표 포함 버전)"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Price", justify="right")
        table.add_column("24h", justify="right", width=8)
        table.add_column("RSI", justify="center", width=6) # ✅ RSI 컬럼 추가
        
        for symbol in TRADING_PAIRS[:8]:  # 상위 8개만 표시
            ticker = f"KRW-{symbol}"
            try:
                price, change_rate = self.cache.get_price_with_change(ticker)
                rsi = self.cache.get_rsi(ticker) # ✅ RSI 지표 가져오기
                self.track_api_call()
                
                if price:
                    # 24시간 변동률 색상 및 화살표 설정
                    if change_rate > 0:
                        change_color, arrow, sign = "green", "↑", "+"
                    elif change_rate < 0:
                        change_color, arrow, sign = "red", "↓", ""
                    else:
                        change_color, arrow, sign = "yellow", "→", ""
                    
                    # RSI 색상 결정 (과매수/과매도 강조)
                    rsi_color = "red" if rsi >= 70 else "green" if rsi <= 30 else "white"
                    
                    # 가격 포맷팅
                    price_str = f"{price:,.0f}" if price > 1000 else f"{price:.2f}" if price > 1 else f"{price:.4f}"
                    
                    table.add_row(
                        symbol,
                        price_str,
                        f"[{change_color}]{arrow}{sign}{change_rate:.2f}%[/{change_color}]",
                        f"[{rsi_color}]{rsi:.0f}[/{rsi_color}]" # ✅ RSI 데이터 추가
                    )
                else:
                    table.add_row(symbol, "N/A", "-", "-")
                    
            except Exception as e:
                table.add_row(symbol, "Error", "-", "-")
        
        return Panel(table, title="💰 Watchlist", border_style="cyan")
    
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
            title="📊 Market Movers",
            border_style="yellow"
        )

    def get_dynamic_coins_panel(self):
        """동적 코인 상태 패널"""
        lines = []
        
        try:
            from momentum_scanner_improved import ImprovedMomentumScanner
            scanner = ImprovedMomentumScanner()
            
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
                            
                            volume = df['volume'].iloc[-1] * df['close'].iloc[-1]
                            volume_str = f"{volume/1e9:.0f}억" if volume > 1e9 else f"{volume/1e8:.0f}천만"
                            
                            lines.append(
                                f"{coin}: [{color}]{change:+.1f}%[/{color}] "
                                f"[dim]({volume_str})[/dim]"
                            )
                    except:
                        lines.append(f"{coin}: [dim]데이터 없음[/dim]")
            else:
                lines.append("[dim]모멘텀 코인 없음[/dim]")
                
        except Exception as e:
            lines.append(f"[dim]로딩 실패: {str(e)[:20]}[/dim]")
        
        if not lines:
            lines.append("[dim]대기 중...[/dim]")
            
        return Panel(
            "\n".join(lines),
            title="🚀 Dynamic Coins",
            border_style="yellow"
        )
    
    def get_mtf_analysis_panel(self):
        """멀티 타임프레임 분석 패널"""
        try:
            from multi_timeframe_analyzer import MultiTimeframeAnalyzer
            
            mtf = MultiTimeframeAnalyzer()
            symbol = TRADING_PAIRS[0]
            
            analysis = mtf.analyze(symbol)
            
            if not analysis:
                return Panel("Loading MTF...", title="📈 Multi-Timeframe", border_style="blue")
            
            lines = []
            lines.append(f"[bold cyan]{symbol} Analysis[/bold cyan]")
            lines.append("")
            
            score = analysis['final_score']
            score_color = "green" if score >= 7.0 else "yellow" if score >= 5.5 else "red"
            lines.append(f"Score: [{score_color}]{score:.1f}/10[/{score_color}]")
            
            consensus = analysis['consensus_level']
            consensus_color = "green" if consensus >= 0.65 else "yellow" if consensus >= 0.5 else "red"
            lines.append(f"Consensus: [{consensus_color}]{consensus:.0%}[/{consensus_color}]")
            
            trend = analysis['dominant_trend']
            trend_emoji = "📈" if 'up' in trend else "📉" if 'down' in trend else "➡️"
            lines.append(f"Trend: {trend_emoji} {trend}")
            
            strength = analysis['signal_strength']
            strength_color = "green" if strength == "strong" else "yellow" if strength == "moderate" else "red"
            lines.append(f"Strength: [{strength_color}]{strength.upper()}[/{strength_color}]")
            
            lines.append("\n[dim]Timeframes:[/dim]")
            for tf, data in analysis['timeframe_details'].items():
                lines.append(f"[dim]{tf}: {data['score']:.1f}, {data['trend']}[/dim]")
            
            return Panel(
                "\n".join(lines),
                title="📈 Multi-Timeframe Analysis",
                border_style="blue"
            )
            
        except Exception as e:
            return Panel(
                f"MTF Error:\n{str(e)[:50]}",
                title="📈 Multi-Timeframe",
                border_style="red"
            )
    
    def get_ml_prediction_panel(self):
        """ML 예측 패널"""
        try:
            from ml_signal_generator import MLSignalGenerator
            
            ml = MLSignalGenerator()
            
            if not ml.is_trained:
                return Panel(
                    "[yellow]Model not trained yet[/yellow]\n"
                    "[dim]Training on first run...[/dim]",
                    title="🤖 ML Prediction",
                    border_style="magenta"
                )
            
            symbol = TRADING_PAIRS[0]
            prediction = ml.predict(symbol)
            
            if not prediction:
                return Panel("Loading ML...", title="🤖 ML Prediction", border_style="magenta")
            
            lines = []
            lines.append(f"[bold magenta]{symbol} Prediction[/bold magenta]")
            lines.append("")
            
            prob = prediction['buy_probability']
            prob_color = "green" if prob >= 0.65 else "yellow" if prob >= 0.55 else "red"
            lines.append(f"Buy Probability: [{prob_color}]{prob:.1%}[/{prob_color}]")
            
            confidence = prediction['confidence']
            conf_color = "green" if confidence >= 0.70 else "yellow" if confidence >= 0.60 else "red"
            lines.append(f"Confidence: [{conf_color}]{confidence:.1%}[/{conf_color}]")
            
            if prediction['prediction']:
                lines.append("\n[green]✅ BUY Signal[/green]")
            else:
                lines.append("\n[red]❌ SELL/HOLD Signal[/red]")
            
            pred_time = prediction['timestamp'].strftime('%H:%M:%S')
            lines.append(f"\n[dim]Time: {pred_time}[/dim]")
            
            return Panel(
                "\n".join(lines),
                title="🤖 ML Prediction",
                border_style="magenta"
            )
            
        except Exception as e:
            return Panel(
                f"ML Error:\n{str(e)[:50]}",
                title="🤖 ML Prediction",
                border_style="red"
            )
    
    def get_positions_panel(self):
        """포지션 패널 (수수료 반영 + Trailing Stop 시각화)"""
        import json
        lines = []
        try:
            fee_rate = UPBIT_CONFIG.get('fee_rate', 0.0005) #
            now = datetime.now()
            
            # 성능 최적화: 5초 주기로 파일 읽기
            if (now - getattr(self, 'last_pos_file_read', datetime.min)).total_seconds() >= 5:
                if os.path.exists('active_positions.json'):
                    with open('active_positions.json', 'r') as f:
                        data = json.load(f)
                        self.cached_positions = data.get('positions', {})
                self.last_pos_file_read = now

            if hasattr(self, 'cached_positions') and self.cached_positions:
                total_eval_pnl = 0
                lines.append(f"[bold green]📦 Active Positions ({len(self.cached_positions)})[/bold green]\n")
                
                for symbol, pos in list(self.cached_positions.items()):
                    entry_price = pos['entry_price']
                    quantity = pos.get('quantity', 0)
                    highest_price = pos.get('highest_price', entry_price) # 고점 추적
                    ticker = f"KRW-{symbol}"
                    
                    #current_price, _ = self.cache.get_price_with_change(f"KRW-{symbol}")
                    current_price = self.cache.get_price_only(ticker)
                    
                    if current_price:
                        # ✅ 수수료 반영 Net PnL 계산
                        net_pnl_val = (current_price * quantity * (1 - fee_rate)) - (entry_price * quantity)
                        net_pnl_rate = (net_pnl_val / (entry_price * quantity)) * 100 if entry_price > 0 else 0
                        total_eval_pnl += net_pnl_val
                        
                        # ✅ Trailing Stop 상태: 고점 대비 현재 하락폭
                        drop_from_high = ((current_price - highest_price) / highest_price) * 100
                        
                        color = "green" if net_pnl_val >= 0 else "red"
                        lines.append(f"[bold]{symbol:<5}[/bold]: [{color}]{net_pnl_rate:>+6.2f}%[/{color}] [dim]({net_pnl_val:+,.0f}원)[/dim]")
                        
                        # 수익 구간일 때 고점 대비 하락 현황 시각화
                        if net_pnl_rate > 1.0:
                            lines.append(f"  └ [dim]Peak: {highest_price:,.0f} | Drop: [bold red]{drop_from_high:.2f}%[/bold red][/dim]")
                    
                summary_color = "green" if total_eval_pnl >= 0 else "red"
                lines.insert(1, f"Total Net PnL: [bold {summary_color}]{total_eval_pnl:+,.0f} KRW[/bold {summary_color}] [dim](수수료 반영)[/dim]\n" + "─" * 35)
            else:
                lines.append("[yellow]No active positions[/yellow]")
        except Exception as e:
            lines.append(f"[red]Error: {str(e)}[/red]")
        
        return Panel("\n".join(lines), title="📦 Positions", border_style="green")
        
    def get_recent_trades_panel(self):
        """✅ 최근 거래 내역 패널 - 캐시 적용"""
        try:
            # ✅ 캐시 체크
            now = datetime.now()
            elapsed = (now - self.last_trades_update).total_seconds()
            
            # 30초마다만 업데이트
            if elapsed >= self.trades_cache_interval or not self.recent_trades_cache:
                self.recent_trades_cache = self.trade_history.get_recent_trades(limit=5)
                self.last_trades_update = now
            
            trades = self.recent_trades_cache
            
            if not trades:
                return Panel(
                    "[dim]거래 내역 없음[/dim]",
                    title="📜 Recent Trades",
                    border_style="blue"
                )
            
            table = Table(show_header=True, header_style="bold blue", box=None, padding=(0, 1))
            table.add_column("Time", width=8)
            table.add_column("Coin", width=6)
            table.add_column("PnL", justify="right", width=10)
            table.add_column("%", justify="right", width=7)
            
            for trade in trades:
                try:
                    timestamp = trade['timestamp']
                    if isinstance(timestamp, str):
                        time_obj = datetime.fromisoformat(timestamp)
                    else:
                        time_obj = timestamp
                    
                    time_str = time_obj.strftime('%H:%M')
                    
                    pnl = trade.get('pnl', 0)
                    pnl_rate = trade.get('pnl_rate', 0)
                    
                    pnl_color = "green" if pnl > 0 else "red"
                    
                    table.add_row(
                        time_str,
                        trade['symbol'],
                        f"[{pnl_color}]{pnl:+,.0f}[/{pnl_color}]",
                        f"[{pnl_color}]{pnl_rate:+.1%}[/{pnl_color}]"
                    )
                except Exception as e:
                    continue
            
            return Panel(table, title="📜 Recent Trades", border_style="blue")
            
        except Exception as e:
            return Panel(
                f"[red]Error loading trades[/red]\n[dim]{str(e)[:30]}[/dim]",
                title="📜 Recent Trades",
                border_style="red"
            )
    
    def calculate_period_stats(self, days):
        """✅ JSON에서 통계 로드"""
        return self.trade_history.get_period_stats(days)
    
    def get_stats_panel(self, days, title):
        """✅ 통계 패널 - 캐시 적용"""
        # ✅ 캐시 체크
        now = datetime.now()
        elapsed = (now - self.last_stats_update).total_seconds()
        
        cache_key = '24h' if days == 1 else f'{days}d'
        
        # 5분마다만 업데이트
        if elapsed >= self.stats_cache_interval or self.stats_cache[cache_key] is None:
            self.stats_cache[cache_key] = self.calculate_period_stats(days)
            self.last_stats_update = now
        
        stats = self.stats_cache[cache_key]
        
        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        table.add_column("Item", style="cyan", width=12)
        table.add_column("Value", justify="right")
        
        # 순수익
        pnl_color = "green" if stats['net_pnl'] > 0 else "red"
        table.add_row("Net PnL", f"[{pnl_color}]{stats['net_pnl']:+,.0f}[/{pnl_color}]")
        table.add_row("Fees", f"[dim]-{stats['total_fee']:,.0f}[/dim]")
        
        # 거래 통계
        table.add_row("", "")
        table.add_row("Trades", f"{stats['trade_count']}")
        
        if stats['trade_count'] > 0:
            win_color = "green" if stats['win_rate'] >= 50 else "red"
            table.add_row("Win Rate", f"[{win_color}]{stats['win_rate']:.1f}%[/{win_color}]")
            
            # Profit Factor
            pf_color = "green" if stats['profit_factor'] >= 1.5 else "yellow" if stats['profit_factor'] >= 1.0 else "red"
            table.add_row("P.Factor", f"[{pf_color}]{stats['profit_factor']:.2f}[/{pf_color}]")
            
            # 평균
            if stats['avg_win'] > 0:
                table.add_row("Avg Win", f"[green]+{stats['avg_win']:,.0f}[/green]")
            if stats['avg_loss'] > 0:
                table.add_row("Avg Loss", f"[red]-{stats['avg_loss']:,.0f}[/red]")
        
        return Panel(
            table,
            title=title,
            border_style="cyan"
        )
    
    def get_footer(self):
        """푸터"""
        now = datetime.now()
        recent_calls = [t for t in self.api_calls if (now - t).total_seconds() < 60]
        calls_per_minute = len(recent_calls)
        
        if calls_per_minute > 500:
            api_status = "[red]CRITICAL[/red]"
        elif calls_per_minute > 300:
            api_status = "[yellow]WARNING[/yellow]"
        else:
            api_status = "[green]NORMAL[/green]"
        
        footer_text = (
            f"API: {api_status} ({calls_per_minute}/600/min) | "
            f"Cache: {len(self.cache.cache)} prices | "
            f"Max Pos: {RISK_CONFIG.get('max_positions', 3)} | "
            f"Stop Loss: {RISK_CONFIG.get('stop_loss', 0.012)*100:.1f}% | "
            f"[dim]Press Ctrl+C to exit[/dim]"
        )
        
        return Panel(footer_text, border_style="dim")
    
    def update(self):
        """✅ 업데이트 - Recent Trades 추가"""
        try:
            # 상단
            self.layout["header"].update(self.get_header())
            
            # 메인 콘텐츠
            self.layout["prices"].update(self.get_price_table())
            self.layout["positions"].update(self.get_positions_panel())
            self.layout["recent_trades"].update(self.get_recent_trades_panel())  # ✅ 추가
            
            self.layout["top_movers"].update(self.get_top_movers_panel())
            self.layout["dynamic_coins"].update(self.get_dynamic_coins_panel())
            self.layout["mtf_analysis"].update(self.get_mtf_analysis_panel())
            self.layout["ml_prediction"].update(self.get_ml_prediction_panel())
            
            # 하단 통계
            self.layout["stats_24h"].update(self.get_stats_panel(1, "📊 24 Hours"))
            self.layout["stats_7d"].update(self.get_stats_panel(7, "📊 7 Days"))
            self.layout["stats_30d"].update(self.get_stats_panel(30, "📊 30 Days"))
            
            # 푸터
            self.layout["footer"].update(self.get_footer())
            
        except Exception as e:
            console.print(f"[red]Update error: {e}[/red]")
        
        return self.layout

def main():
    dashboard = TradingDashboard()
    
    console.clear()
    console.print("[bold cyan]🚀 Upbit Advanced Trading Dashboard[/bold cyan]")
    console.print("[yellow]⚡ Features: MTF + ML + Recent Trades + Multi-Period Stats[/yellow]")
    console.print("[dim]Loading... First update may take 10-15 seconds.[/dim]")
    console.print("Press Ctrl+C to exit\n")
    
    try:
        with Live(dashboard.update(), refresh_per_second=1.0, console=console) as live:
            while True:
                time.sleep(1)
                live.update(dashboard.update())
    except KeyboardInterrupt:
        console.print("\n[bold red]Dashboard stopped[/bold red]")

if __name__ == "__main__":
    main()