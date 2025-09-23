# monitor.py - 실시간 모니터링 도구

import time
import pyupbit
from datetime import datetime
from config import TRADING_PAIRS

def monitor_prices():
    """실시간 가격 모니터링"""
    print("실시간 가격 모니터링 시작")
    print("="*60)
    
    while True:
        try:
            print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            
            for symbol in TRADING_PAIRS:
                ticker = f"KRW-{symbol}"
                price = pyupbit.get_current_price(ticker)
                
                if price:
                    # 24시간 변동률
                    ticker_info = pyupbit.get_ticker(ticker)[0]
                    change_rate = ticker_info['signed_change_rate'] * 100
                    
                    # 색상 코드
                    if change_rate > 0:
                        color = "🟢"
                    elif change_rate < 0:
                        color = "🔴"
                    else:
                        color = "⚪"
                    
                    print(f"{color} {symbol}: {price:,.0f} KRW ({change_rate:+.2f}%)")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n모니터링 종료")
            break
        except Exception as e:
            print(f"오류: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_prices()