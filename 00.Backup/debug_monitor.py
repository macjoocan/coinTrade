# debug_monitor.py - 왜 거래가 안 되는지 확인

import pyupbit
import time
from datetime import datetime
from improved_strategy import ImprovedStrategy
from config import TRADING_PAIRS

def debug_signals():
    """신호 디버깅"""
    strategy = ImprovedStrategy()
    
    print("="*60)
    print("신호 디버깅 모드")
    print("="*60)
    
    while True:
        for symbol in TRADING_PAIRS:
            ticker = f"KRW-{symbol}"
            
            try:
                # 지표 계산 (간단 버전)
                df = pyupbit.get_ohlcv(ticker, interval="minute15", count=50)
                if df is None or len(df) < 50:
                    continue
                
                # RSI
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                
                # 이동평균
                sma_20 = df['close'].rolling(20).mean().iloc[-1]
                sma_50 = df['close'].rolling(50).mean().iloc[-1]
                current = df['close'].iloc[-1]
                
                # 볼륨
                volume_ratio = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
                
                # 점수 계산
                score = 0
                reasons = []
                
                if sma_20 > sma_50:
                    score += 1.5
                    reasons.append("추세↑")
                
                if 30 < rsi < 45:
                    score += 2
                    reasons.append(f"RSI:{rsi:.0f}")
                elif rsi < 30:
                    score += 3
                    reasons.append(f"RSI극:{rsi:.0f}")
                
                if volume_ratio > 1.2:
                    score += 1.5
                    reasons.append(f"Vol:{volume_ratio:.1f}x")
                
                # 결과 출력
                status = "❌"
                if score >= 5:
                    status = "✅ 매수!"
                elif score >= 4:
                    status = "🟡 관심"
                
                print(f"{datetime.now().strftime('%H:%M:%S')} {status} {symbol}: "
                      f"점수={score:.1f} {' '.join(reasons)} "
                      f"가격={current:,.0f}")
                
            except Exception as e:
                print(f"오류 {symbol}: {e}")
        
        print("-"*60)
        time.sleep(60)  # 1분 대기

if __name__ == "__main__":
    debug_signals()