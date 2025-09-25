# position_health_check.py - 현재 포지션 건전성 체크

import pyupbit
from datetime import datetime
from risk_manager import RiskManager

def emergency_check():
    """긴급 포지션 체크"""
    
    print("="*60)
    print(f"긴급 포지션 점검: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)
    
    # 현재 보유 중인 포지션 확인
    positions = ['BTC', 'DOGE']  # 실제 보유 중인 것
    
    for symbol in positions:
        ticker = f"KRW-{symbol}"
        current_price = pyupbit.get_current_price(ticker)
        
        print(f"\n{symbol}:")
        print(f"  현재가: {current_price:,.0f}")
        
        # 예상 손익 (실제 진입가 필요)
        if symbol == 'BTC':
            entry = 160900000  # 예상
            pnl = ((current_price - entry) / entry) * 100
        elif symbol == 'DOGE':
            entry = 346  # 예상
            pnl = ((current_price - entry) / entry) * 100
        
        print(f"  예상 손익: {pnl:+.2f}%")
        
        # 권장 액션
        if pnl < -1.0:
            print(f"  🔴 즉시 손절 권장!")
        elif pnl < -0.5:
            print(f"  🟡 손절 준비")
        elif pnl > 1.0:
            print(f"  🟢 익절 고려")
        else:
            print(f"  ⚪ 관찰 유지")
    
    print("\n" + "="*60)
    print("💡 권장사항:")
    print("1. DOGE는 변동성이 크므로 타이트한 손절 설정")
    print("2. 신규 진입 중단 (연속 손실 2회)")
    print("3. 기존 포지션 정리 후 재시작 고려")
    print("="*60)

if __name__ == "__main__":
    emergency_check()