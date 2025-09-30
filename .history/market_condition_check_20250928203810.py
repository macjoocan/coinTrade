# market_condition_check.py - 현재 시장 상황 분석

import pyupbit
from datetime import datetime

def analyze_current_market():
    """현재 시장 상황 분석"""
    
    coins = ['BTC', 'ETH', 'SOL', 'AVAX', 'MATIC']
    
    print("="*60)
    print(f"시장 상황 분석 - {datetime.now().strftime('%H:%M')}")
    print("="*60)
    
    market_signals = {
        'bullish': 0,
        'bearish': 0,
        'neutral': 0
    }
    
    for coin in coins:
        ticker = f"KRW-{coin}"
        
        try:
            # 일봉 데이터
            df = pyupbit.get_ohlcv(ticker, interval="day", count=7)
            
            # 1주일 추세
            week_change = ((df['close'].iloc[-1] - df['close'].iloc[0]) 
                          / df['close'].iloc[0] * 100)
            
            # 변동성
            volatility = df['close'].pct_change().std() * 100
            
            # RSI (간단 계산)
            df_hour = pyupbit.get_ohlcv(ticker, interval="minute60", count=24)
            delta = df_hour['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            print(f"\n{coin}:")
            print(f"  주간 변화: {week_change:+.1f}%")
            print(f"  변동성: {volatility:.1f}%")
            print(f"  RSI: {rsi:.1f}")
            
            # 신호 판단
            if week_change > 5 and rsi < 70:
                market_signals['bullish'] += 1
                signal = "📈 상승"
            elif week_change < -5 or rsi > 70:
                market_signals['bearish'] += 1
                signal = "📉 하락"
            else:
                market_signals['neutral'] += 1
                signal = "➡️ 횡보"
            
            print(f"  신호: {signal}")
            
        except Exception as e:
            print(f"{coin}: 분석 실패 - {e}")
    
    # 종합 판단
    print("\n" + "="*60)
    print("📌 시장 종합 판단:")
    print(f"  상승 신호: {market_signals['bullish']}/5")
    print(f"  하락 신호: {market_signals['bearish']}/5")
    print(f"  횡보 신호: {market_signals['neutral']}/5")
    
    if market_signals['neutral'] >= 3:
        print("\n💡 판단: 횡보장 - 관망 권장")
        return 'sideways'
    elif market_signals['bullish'] >= 3:
        print("\n💡 판단: 상승장 - 적극 진입")
        return 'bullish'
    else:
        print("\n💡 판단: 혼조세 - 신중한 접근")
        return 'mixed'

# 실행
market_condition = analyze_current_market()