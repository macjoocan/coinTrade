# emergency_check.py - 긴급 점검 스크립트

import pyupbit
from datetime import datetime

def check_positions():
    """현재 포지션 긴급 점검"""
    
    positions = {
        'BTC': {'entry': 160900000, 'current': None},  # 예상 진입가
        'DOGE': {'entry': 346, 'current': None}
    }
    
    print("="*50)
    print(f"긴급 점검: {datetime.now().strftime('%H:%M:%S')}")
    print("="*50)
    
    for symbol, pos in positions.items():
        ticker = f"KRW-{symbol}"
        current = pyupbit.get_current_price(ticker)
        
        if current:
            positions[symbol]['current'] = current
            pnl = ((current - pos['entry']) / pos['entry']) * 100
            
            print(f"\n{symbol}:")
            print(f"  진입가: {pos['entry']:,.0f}")
            print(f"  현재가: {current:,.0f}")
            print(f"  손익률: {pnl:+.2f}%")
            
            # 권장 액션
            if pnl < -1.0:
                print(f"  ⚠️ 권장: 즉시 손절!")
            elif pnl > 0.8:
                print(f"  ✅ 권장: 익절 고려")
            else:
                print(f"  ⏳ 권장: 관찰 유지")
    
    print("\n" + "="*50)
    print("권장사항:")
    print("1. DOGE는 변동성이 커서 손절 고려")
    print("2. 새로운 진입은 자제")
    print("3. 진입 점수 기준을 6점으로 상향")
    print("="*50)

if __name__ == "__main__":
    check_positions()