# binance_dashboard.py - Binance Futures Trading Dashboard
# Real-time positions, P&L, and market data visualization

import os
import sys
import time
import json
import ccxt
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
import logging

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

console = Console()

# 설정 파일 경로 결정
def get_settings_path():
    """실행 환경에 따른 설정 파일 경로"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'binance_settings.json')
    return os.path.join(os.path.dirname(__file__), 'binance_settings.json')

def get_positions_path():
    """포지션 파일 경로"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'binance_positions.json')
    return os.path.join(os.path.dirname(__file__), 'binance_positions.json')

def get_history_path():
    """거래 히스토리 파일 경로"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'binance_history.json')
    return os.path.join(os.path.dirname(__file__), 'binance_history.json')


class BinanceDataCache:
    """바이낸스 시장 데이터 캐싱"""
    def __init__(self, exchange):
        self.exchange = exchange
        self.cache = {}
        self.last_update = {}
        self.update_interval = 2  # 2초
        self.change_cache = {}
        self.change_update_interval = 60  # 1분

    def get_price(self, symbol):
        """현재가 조회"""
        now = datetime.now()

        if symbol in self.cache:
            elapsed = (now - self.last_update.get(symbol, datetime.min)).total_seconds()
            if elapsed < self.update_interval:
                return self.cache[symbol]

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            self.cache[symbol] = price
            self.last_update[symbol] = now
            return price
        except Exception as e:
            logger.debug(f"Price fetch failed for {symbol}: {e}")
            return self.cache.get(symbol, 0)

    def get_price_with_change(self, symbol):
        """현재가 + 24시간 변동률"""
        now = datetime.now()
        price = self.get_price(symbol)

        change_key = f"{symbol}_change"
        if change_key in self.change_cache:
            elapsed = (now - self.last_update.get(change_key, datetime.min)).total_seconds()
            if elapsed < self.change_update_interval:
                return price, self.change_cache[change_key]

        try:
            ticker = self.exchange.fetch_ticker(symbol)
            change_pct = ticker.get('percentage', 0) or 0
            self.change_cache[change_key] = change_pct
            self.last_update[change_key] = now
            return price, change_pct
        except Exception as e:
            logger.debug(f"Change fetch failed for {symbol}: {e}")
            return price, self.change_cache.get(change_key, 0)


class BinanceDashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self.exchange = None
        self.cache = None
        self.settings = {}
        self.symbols = []
        self.mode = "unknown"

        # 캐시
        self.positions_cache = {}
        self.last_pos_update = datetime.now() - timedelta(seconds=10)
        self.pos_update_interval = 1  # 1초

        self.history_cache = []
        self.last_history_update = datetime.now() - timedelta(minutes=5)
        self.history_update_interval = 10  # 10초

        self.balance_cache = 0
        self.last_balance_update = datetime.now() - timedelta(seconds=30)
        self.balance_update_interval = 5  # 5초

        # 초기화
        self._load_settings()
        self._init_exchange()
        self.setup_layout()

    def _load_settings(self):
        """설정 파일 로드"""
        try:
            settings_path = get_settings_path()
            with open(settings_path, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)

            self.mode = self.settings.get('mode', 'simulation')
            self.symbols = self.settings.get('trading', {}).get('symbols', [])
            logger.info(f"Settings loaded: mode={self.mode}, symbols={self.symbols}")
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self.settings = {}
            self.symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT']

    def _init_exchange(self):
        """거래소 API 초기화"""
        try:
            api_config = self.settings.get('api', {})
            api_key = api_config.get('key', '')
            api_secret = api_config.get('secret', '')

            self.exchange = ccxt.binance({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'adjustForTimeDifference': True,
                    'recvWindow': 60000
                }
            })

            self.cache = BinanceDataCache(self.exchange)
            logger.info("Exchange initialized")
        except Exception as e:
            logger.error(f"Exchange init failed: {e}")
            self.exchange = None

    def setup_layout(self):
        """레이아웃 구성"""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="stats", size=10),
            Layout(name="footer", size=3)
        )

        # 메인: 좌/우
        self.layout["main"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )

        # 좌측: 가격 + 포지션
        self.layout["left"].split(
            Layout(name="prices", ratio=1),
            Layout(name="positions", ratio=1)
        )

        # 우측: 최근 거래 + 계좌 정보
        self.layout["right"].split(
            Layout(name="recent_trades", ratio=1),
            Layout(name="account", ratio=1)
        )

        # 하단 통계
        self.layout["stats"].split_row(
            Layout(name="stats_today"),
            Layout(name="stats_7d"),
            Layout(name="stats_30d")
        )

    def get_header(self):
        """헤더"""
        mode_color = "green" if self.mode == "live" else "yellow"
        mode_text = "LIVE" if self.mode == "live" else "SIMULATION"

        return Panel(
            f"[bold cyan]Binance Futures Dashboard[/bold cyan]\n"
            f"[yellow]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/yellow] | "
            f"Mode: [{mode_color}]{mode_text}[/{mode_color}] | "
            f"Symbols: {', '.join([s.replace('/USDT', '') for s in self.symbols[:4]])}",
            style="bold on dark_blue"
        )

    def get_price_table(self):
        """가격 테이블"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=10)
        table.add_column("Price", justify="right", width=12)
        table.add_column("24h", justify="right", width=10)

        for symbol in self.symbols[:8]:
            try:
                if self.cache:
                    price, change = self.cache.get_price_with_change(symbol)

                    if price:
                        # 변동률 색상
                        if change > 0:
                            change_color, arrow, sign = "green", "↑", "+"
                        elif change < 0:
                            change_color, arrow, sign = "red", "↓", ""
                        else:
                            change_color, arrow, sign = "yellow", "→", ""

                        # 가격 포맷
                        if price > 1000:
                            price_str = f"{price:,.2f}"
                        elif price > 1:
                            price_str = f"{price:.4f}"
                        else:
                            price_str = f"{price:.6f}"

                        short_symbol = symbol.replace('/USDT', '')
                        table.add_row(
                            short_symbol,
                            price_str,
                            f"[{change_color}]{arrow}{sign}{change:.2f}%[/{change_color}]"
                        )
                    else:
                        table.add_row(symbol.replace('/USDT', ''), "N/A", "-")
                else:
                    table.add_row(symbol.replace('/USDT', ''), "No API", "-")
            except Exception as e:
                table.add_row(symbol.replace('/USDT', ''), "Error", "-")

        return Panel(table, title="Watchlist", border_style="cyan")

    def _load_positions(self):
        """포지션 파일 로드"""
        now = datetime.now()
        if (now - self.last_pos_update).total_seconds() < self.pos_update_interval:
            return self.positions_cache

        try:
            pos_path = get_positions_path()
            if os.path.exists(pos_path):
                with open(pos_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.positions_cache = data.get('positions', {})
            self.last_pos_update = now
        except Exception as e:
            logger.debug(f"Position load failed: {e}")

        return self.positions_cache

    def get_positions_panel(self):
        """포지션 패널"""
        lines = []
        positions = self._load_positions()

        if not positions:
            lines.append("[yellow]No active positions[/yellow]")
            return Panel("\n".join(lines), title="Positions", border_style="green")

        total_pnl = 0
        total_pnl_pct = 0

        lines.append(f"[bold green]Active: {len(positions)}[/bold green]\n")

        for symbol, pos in positions.items():
            try:
                entry_price = pos.get('entry_price', 0)
                quantity = pos.get('quantity', 0)
                side = pos.get('side', 'BUY')

                # 현재가 조회
                current_price = self.cache.get_price(symbol) if self.cache else 0

                if current_price and entry_price > 0:
                    # P&L 계산 (롱/숏 구분)
                    if side == 'BUY':
                        pnl_pct = ((current_price - entry_price) / entry_price) * 100
                        pnl_val = (current_price - entry_price) * quantity
                    else:
                        pnl_pct = ((entry_price - current_price) / entry_price) * 100
                        pnl_val = (entry_price - current_price) * quantity

                    total_pnl += pnl_val

                    color = "green" if pnl_val >= 0 else "red"
                    side_emoji = "🟢" if side == 'BUY' else "🔴"
                    short_symbol = symbol.replace('/USDT', '')

                    # Stop Loss / Take Profit
                    sl = pos.get('stop_loss', 0)
                    tp = pos.get('take_profit', 0)

                    lines.append(f"{side_emoji} [bold]{short_symbol}[/bold]: [{color}]{pnl_pct:+.2f}%[/{color}] ({pnl_val:+.2f} USDT)")
                    lines.append(f"   [dim]Entry: {entry_price:.4f} | Now: {current_price:.4f}[/dim]")
                    lines.append(f"   [dim]SL: {sl:.4f} | TP: {tp:.4f}[/dim]")
                else:
                    short_symbol = symbol.replace('/USDT', '')
                    lines.append(f"[bold]{short_symbol}[/bold]: [dim]Loading...[/dim]")
            except Exception as e:
                lines.append(f"[red]Error: {str(e)[:30]}[/red]")

        # 총 P&L
        total_color = "green" if total_pnl >= 0 else "red"
        lines.insert(1, f"Total PnL: [{total_color}]{total_pnl:+.2f} USDT[/{total_color}]\n" + "─" * 35)

        return Panel("\n".join(lines), title="Positions", border_style="green")

    def _load_history(self):
        """거래 히스토리 로드"""
        now = datetime.now()
        if (now - self.last_history_update).total_seconds() < self.history_update_interval:
            return self.history_cache

        try:
            hist_path = get_history_path()
            if os.path.exists(hist_path):
                with open(hist_path, 'r', encoding='utf-8') as f:
                    self.history_cache = json.load(f)
            self.last_history_update = now
        except Exception as e:
            logger.debug(f"History load failed: {e}")

        return self.history_cache

    def get_recent_trades_panel(self):
        """최근 거래 패널"""
        history = self._load_history()

        if not history:
            return Panel(
                "[dim]No trade history[/dim]",
                title="Recent Trades",
                border_style="blue"
            )

        table = Table(show_header=True, header_style="bold blue", box=None, padding=(0, 1))
        table.add_column("Time", width=12)
        table.add_column("Symbol", width=8)
        table.add_column("Side", width=6)
        table.add_column("PnL", justify="right", width=12)

        # 최근 5개
        recent = sorted(history, key=lambda x: x.get('exit_time', ''), reverse=True)[:5]

        for trade in recent:
            try:
                exit_time = trade.get('exit_time', '')
                if exit_time:
                    time_obj = datetime.fromisoformat(exit_time)
                    time_str = time_obj.strftime('%m-%d %H:%M')
                else:
                    time_str = "-"

                symbol = trade.get('symbol', '').replace('/USDT', '')
                side = trade.get('side', 'BUY')
                pnl = trade.get('pnl', 0)
                pnl_rate = trade.get('pnl_rate', 0)

                side_color = "green" if side == 'BUY' else "red"
                pnl_color = "green" if pnl > 0 else "red"

                table.add_row(
                    time_str,
                    symbol,
                    f"[{side_color}]{side}[/{side_color}]",
                    f"[{pnl_color}]{pnl:+.2f} ({pnl_rate:+.1%})[/{pnl_color}]"
                )
            except Exception as e:
                continue

        return Panel(table, title="Recent Trades", border_style="blue")

    def _get_balance(self):
        """잔고 조회"""
        now = datetime.now()
        if (now - self.last_balance_update).total_seconds() < self.balance_update_interval:
            return self.balance_cache

        try:
            if self.exchange and self.mode == 'live':
                balance = self.exchange.fetch_balance()
                self.balance_cache = balance['USDT']['free']
            else:
                self.balance_cache = self.settings.get('simulation', {}).get('initial_balance', 10000)
            self.last_balance_update = now
        except Exception as e:
            logger.debug(f"Balance fetch failed: {e}")

        return self.balance_cache

    def get_account_panel(self):
        """계좌 정보 패널"""
        lines = []

        try:
            balance = self._get_balance()
            positions = self._load_positions()

            # 잔고
            lines.append(f"[bold cyan]Available Balance[/bold cyan]")
            lines.append(f"[bold white]{balance:,.2f} USDT[/bold white]")
            lines.append("")

            # 설정 정보
            risk = self.settings.get('risk', {})
            leverage = risk.get('leverage', 3)
            stop_loss = risk.get('stop_loss', 0.02)
            take_profit = risk.get('take_profit', 0.04)
            max_positions = risk.get('max_positions', 4)

            lines.append(f"[bold yellow]Risk Settings[/bold yellow]")
            lines.append(f"Leverage: [cyan]{leverage}x[/cyan]")
            lines.append(f"Stop Loss: [red]{stop_loss*100:.1f}%[/red]")
            lines.append(f"Take Profit: [green]{take_profit*100:.1f}%[/green]")
            lines.append(f"Max Positions: {len(positions)}/{max_positions}")

            # Trailing Stop
            trailing = self.settings.get('trailing_stop', {})
            if trailing.get('enabled', False):
                lines.append("")
                lines.append(f"[bold magenta]Trailing Stop[/bold magenta]")
                lines.append(f"Activation: {trailing.get('activation', 0.02)*100:.1f}%")
                lines.append(f"Distance: {trailing.get('distance', 0.01)*100:.1f}%")

        except Exception as e:
            lines.append(f"[red]Error: {str(e)}[/red]")

        return Panel("\n".join(lines), title="Account Info", border_style="yellow")

    def _calculate_stats(self, days):
        """기간별 통계 계산"""
        history = self._load_history()

        if not history:
            return {
                'trade_count': 0,
                'win_count': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'profit_factor': 0
            }

        # 기간 필터
        cutoff = datetime.now() - timedelta(days=days)
        filtered = []

        for trade in history:
            try:
                exit_time = trade.get('exit_time', '')
                if exit_time:
                    trade_time = datetime.fromisoformat(exit_time)
                    if trade_time >= cutoff:
                        filtered.append(trade)
            except:
                continue

        if not filtered:
            return {
                'trade_count': 0,
                'win_count': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'profit_factor': 0
            }

        # 통계 계산
        wins = [t for t in filtered if t.get('pnl', 0) > 0]
        losses = [t for t in filtered if t.get('pnl', 0) < 0]

        total_pnl = sum(t.get('pnl', 0) for t in filtered)
        total_win = sum(t.get('pnl', 0) for t in wins)
        total_loss = abs(sum(t.get('pnl', 0) for t in losses))

        return {
            'trade_count': len(filtered),
            'win_count': len(wins),
            'win_rate': (len(wins) / len(filtered) * 100) if filtered else 0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(filtered) if filtered else 0,
            'profit_factor': (total_win / total_loss) if total_loss > 0 else 0
        }

    def get_stats_panel(self, days, title):
        """통계 패널"""
        stats = self._calculate_stats(days)

        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        table.add_column("Item", style="cyan", width=12)
        table.add_column("Value", justify="right")

        # P&L
        pnl_color = "green" if stats['total_pnl'] > 0 else "red"
        table.add_row("Total PnL", f"[{pnl_color}]{stats['total_pnl']:+.2f}[/{pnl_color}]")
        table.add_row("Avg PnL", f"{stats['avg_pnl']:+.2f}")

        table.add_row("", "")
        table.add_row("Trades", f"{stats['trade_count']}")

        if stats['trade_count'] > 0:
            win_color = "green" if stats['win_rate'] >= 50 else "red"
            table.add_row("Win Rate", f"[{win_color}]{stats['win_rate']:.1f}%[/{win_color}]")

            pf_color = "green" if stats['profit_factor'] >= 1.5 else "yellow" if stats['profit_factor'] >= 1.0 else "red"
            table.add_row("P.Factor", f"[{pf_color}]{stats['profit_factor']:.2f}[/{pf_color}]")

        return Panel(table, title=title, border_style="cyan")

    def get_footer(self):
        """푸터"""
        api_status = "[green]Connected[/green]" if self.exchange else "[red]Disconnected[/red]"

        footer_text = (
            f"API: {api_status} | "
            f"Cache: {len(self.cache.cache) if self.cache else 0} prices | "
            f"[dim]Press Ctrl+C to exit[/dim]"
        )

        return Panel(footer_text, border_style="dim")

    def update(self):
        """대시보드 업데이트"""
        try:
            self.layout["header"].update(self.get_header())

            self.layout["prices"].update(self.get_price_table())
            self.layout["positions"].update(self.get_positions_panel())
            self.layout["recent_trades"].update(self.get_recent_trades_panel())
            self.layout["account"].update(self.get_account_panel())

            self.layout["stats_today"].update(self.get_stats_panel(1, "Today"))
            self.layout["stats_7d"].update(self.get_stats_panel(7, "7 Days"))
            self.layout["stats_30d"].update(self.get_stats_panel(30, "30 Days"))

            self.layout["footer"].update(self.get_footer())

        except Exception as e:
            console.print(f"[red]Update error: {e}[/red]")

        return self.layout


def main():
    console.clear()
    console.print("[bold cyan]Binance Futures Dashboard[/bold cyan]")
    console.print("[yellow]Loading...[/yellow]")
    console.print("Press Ctrl+C to exit\n")

    try:
        dashboard = BinanceDashboard()

        with Live(dashboard.update(), refresh_per_second=0.5, console=console) as live:
            while True:
                time.sleep(2)
                live.update(dashboard.update())
    except KeyboardInterrupt:
        console.print("\n[bold red]Dashboard stopped[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")


if __name__ == "__main__":
    main()
