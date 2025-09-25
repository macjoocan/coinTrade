# quick_movers.py - 빠른 상승/하락 TOP 5 조회

import pyupbit
from rich.console import Console
from rich.table import Table
from datetime import datetime

console = Console()

def get_quick_movers():
    """빠른 버전 - 주요 코인만 체크"""
    
    # 주요 코인 리스트
    major_coins = [
        'BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX', 
        'DOT', 'MATIC', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM',
        'TRX', 'SHIB', 'NEAR', 'BCH', 'APT', 'ARB', 'OP',
        'HBAR', 'ICP', 'FIL', 'IMX', 'SAND', 'MANA', 'AXS',
        'THETA', 'AAVE', 'EOS', 'ALGO', 'FLOW', 'GRT', 'SNX'
    ]
    
    market_data = []
    
    console.print("[yellow]Fetching market data...[/yellow]")
    
    for symbol in major_coins:
        ticker = f"KRW-{symbol}"
        try:
            current_price = pyupbit.get_current_price(ticker)
            
            if current_price:
                # 24시간 변동률
                df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
                
                if df is not None and len(df) >= 2:
                    yesterday_close = df['close'].iloc[-2]
                    change_rate = ((current_price - yesterday_close) / yesterday_close) * 100
                    
                    market_data.append({
                        'symbol': symbol,
                        'price': current_price,
                        'change': change_rate
                    })
        except:
            continue
    
    # 정렬
    market_data.sort(key=lambda x: x['change'], reverse=True)
    
    # 테이블 생성
    console.clear()
    console.print(f"\n[bold cyan]Market Movers - {datetime.now().strftime('%H:%M:%S')}[/bold cyan]\n")
    
    # 상승 TOP 5
    gainers_table = Table(title="🚀 Top Gainers", show_header=True, header_style="bold green")
    gainers_table.add_column("#", style="cyan", width=3)
    gainers_table.add_column("Symbol", style="white")
    gainers_table.add_column("Price", justify="right")
    gainers_table.add_column("24h Change", justify="right", style="green")
    
    for i, coin in enumerate(market_data[:5], 1):
        price_str = f"{coin['price']:,.0f}" if coin['price'] > 100 else f"{coin['price']:.2f}"
        gainers_table.add_row(
            str(i),
            coin['symbol'],
            price_str,
            f"↑ +{coin['change']:.2f}%"
        )
    
    # 하락 TOP 5
    losers_table = Table(title="📉 Top Losers", show_header=True, header_style="bold red")
    losers_table.add_column("#", style="cyan", width=3)
    losers_table.add_column("Symbol", style="white")
    losers_table.add_column("Price", justify="right")
    losers_table.add_column("24h Change", justify="right", style="red")
    
    for i, coin in enumerate(market_data[-5:][::-1], 1):
        price_str = f"{coin['price']:,.0f}" if coin['price'] > 100 else f"{coin['price']:.2f}"
        losers_table.add_row(
            str(i),
            coin['symbol'],
            price_str,
            f"↓ {coin['change']:.2f}%"
        )
    
    console.print(gainers_table)
    console.print()
    console.print(losers_table)

if __name__ == "__main__":
    try:
        while True:
            get_quick_movers()
            console.print("\n[dim]Refreshing in 30 seconds... (Ctrl+C to exit)[/dim]")
            time.sleep(30)
    except KeyboardInterrupt:
        console.print("\n[bold red]Stopped[/bold red]")