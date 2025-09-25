# light_monitor.py - 최소 API 호출 버전

import pyupbit
import time
from datetime import datetime

def monitor_light():
    """초경량 모니터링"""
    
    # 관심 코인만
    watch_list = ['BTC', 'ETH', 'SOL']
    
    print("=" * 50)
    print("Light Monitor - Minimal API Calls")
    print("=" * 50)
    
    cache = {}
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
            
            for symbol in watch_list:
                ticker = f"KRW-{symbol}"
                
                # 15초에 한 번만 업데이트
                if symbol not in cache or time.time() - cache.get(f"{symbol}_time", 0) > 15:
                    price = pyupbit.get_current_price(ticker)
                    cache[symbol] = price
                    cache[f"{symbol}_time"] = time.time()
                else:
                    price = cache[symbol]
                
                if price:
                    print(f"  {symbol}: {price:,.0f} KRW")
            
            print("\n[API Calls: ~12/min, Limit: 600/min]")
            time.sleep(5)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    monitor_light()