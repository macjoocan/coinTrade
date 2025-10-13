# signal_diagnosis.py - 왜 거래가 안 되는지 진단

import pyupbit
from improved_strategy import ImprovedStrategy
from config import TRADING_PAIRS, ADVANCED_CONFIG
from datetime import datetime

def diagnose_signals():
    """현재 모든 코인의 신호 상태 진단"""
    
    strategy = ImprovedStrategy()
    
    print("\n" + "="*80)
    print("🔍 업비트 트레이딩 시스템 진단")
    print("="*80)
    print(f"⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 진입 기준: {ADVANCED_CONFIG['entry_score_threshold']:.1f}점")
    print("="*80)
    
    # ML 상태 확인
    if hasattr(strategy, 'ml_generator') and strategy.ml_generator:
        ml_status = "✅ 학습됨" if strategy.ml_generator.is_trained else "❌ 미학습"
        print(f"\n🤖 ML 모델 상태: {ml_status}")
    else:
        print(f"\n🤖 ML 모델 상태: ❌ 비활성화")
    
    # MTF 상태 확인
    if hasattr(strategy, 'mtf_analyzer') and strategy.mtf_analyzer:
        print(f"📈 MTF 분석: ✅ 활성화")
    else:
        print(f"📈 MTF 분석: ❌ 비활성화")
    
    print("\n" + "-"*80)
    print("코인별 신호 분석:")
    print("-"*80)
    
    for symbol in TRADING_PAIRS:
        ticker = f"KRW-{symbol}"
        
        try:
            print(f"\n🪙 {symbol}")
            print("   " + "-"*40)
            
            # 기술적 지표 계산
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=100)
            if df is None:
                print(f"   ❌ 데이터 없음")
                continue
            
            # 간단한 지표만 계산
            current_price = df['close'].iloc[-1]
            sma_20 = df['close'].rolling(20).mean().iloc[-1]
            sma_50 = df['close'].rolling(50).mean().iloc[-1]
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            
            print(f"   💰 현재가: {current_price:,.0f} KRW")
            print(f"   📊 SMA20: {sma_20:,.0f} / SMA50: {sma_50:,.0f}")
            print(f"   📈 RSI: {rsi:.1f}")
            
            # 추세 판단
            if sma_20 > sma_50 and current_price > sma_20:
                trend = "🟢 강한 상승"
            elif sma_20 > sma_50:
                trend = "🟡 상승"
            elif sma_20 < sma_50:
                trend = "🔴 하락"
            else:
                trend = "⚪ 횡보"
            print(f"   🎯 추세: {trend}")
            
            # 간단한 점수 추정
            score = 0
            if sma_20 > sma_50 and current_price > sma_20:
                score += 2.5
            elif sma_20 > sma_50:
                score += 1.5
            
            if 30 < rsi < 40:
                score += 3
            elif 40 < rsi < 50:
                score += 2
            elif 50 < rsi < 60:
                score += 1
            
            print(f"   ⭐ 추정 점수: {score:.1f}/10")
            
            # 진입 가능 여부
            threshold = ADVANCED_CONFIG['entry_score_threshold']
            if score >= threshold:
                print(f"   ✅ 진입 조건 충족! (기준: {threshold:.1f})")
            else:
                gap = threshold - score
                print(f"   ❌ 진입 조건 미달 ({gap:.1f}점 부족)")
            
        except Exception as e:
            print(f"   ⚠️ 분석 실패: {str(e)[:50]}")
    
    print("\n" + "="*80)
    print("\n💡 권장사항:")
    print("   1. ML 모델이 미학습 상태라면: 봇을 한 번 실행하여 자동 학습")
    print("   2. 점수가 계속 부족하면: config.py에서 entry_score_threshold 낮추기")
    print("   3. 횡보장이라면: 동적 코인 스캐너 활성화 확인")
    print("="*80 + "\n")

if __name__ == "__main__":
    diagnose_signals()