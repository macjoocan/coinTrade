# emergency_actions.py
import pyupbit

def emergency_cleanup(upbit, positions):
    """긴급 포지션 정리"""
    
    print("🚨 긴급 포지션 정리 시작")
    
    # 손실 중인 포지션 청산
    for symbol in ['KAITO', 'ADA']:  # 손실 큰 것부터
        if symbol in positions:
            ticker = f"KRW-{symbol}"
            quantity = get_position_quantity(symbol)
            if quantity > 0:
                print(f"청산: {symbol}")
                upbit.sell_market_order(ticker, quantity)
    
    print("✅ 정리 완료")