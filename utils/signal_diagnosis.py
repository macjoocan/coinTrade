# signal_diagnosis.py - 수정 버전

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
            
            # 지표 계산
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
            
            # ✅ 개선된 점수 추정 (improved_strategy.py와 동일)
            score = 0
            details = []
            
            # 추세 점수
            if sma_20 > sma_50 and current_price > sma_20:
                score += 2.5
                details.append("강한 상승 추세 (+2.5)")
            elif sma_20 > sma_50:
                score += 1.5
                details.append("상승 추세 (+1.5)")
            elif current_price > sma_20:
                score += 0.5
                details.append("단기 상승 (+0.5)")
            
            # ✅ RSI 점수 (개선된 로직)
            if rsi < 30:
                score += 1.0
                details.append(f"RSI 과매도 ({rsi:.1f}) (+1.0)")
            elif 30 <= rsi < 40:
                score += 3.0
                details.append(f"RSI 과매도 반등 ({rsi:.1f}) (+3.0)")
            elif 40 <= rsi < 50:
                score += 2.5
                details.append(f"RSI 건강한 수준 ({rsi:.1f}) (+2.5)")
            elif 50 <= rsi < 60:
                score += 2.0  # ✅ 1 → 2.0
                details.append(f"RSI 상승 지속 ({rsi:.1f}) (+2.0)")
            elif 60 <= rsi < 65:
                score += 1.5  # ✅ 신규
                details.append(f"RSI 강세 ({rsi:.1f}) (+1.5)")
            elif 65 <= rsi < 70:
                score += 1.0  # ✅ 신규
                details.append(f"RSI 과매수 주의 ({rsi:.1f}) (+1.0)")
            elif rsi >= 70:
                score += 0.0  # ✅ 차단
                details.append(f"RSI 과매수 위험 ({rsi:.1f}) (+0.0)")
            
            print(f"   ⭐ 추정 점수: {score:.1f}/10")
            
            # 상세 점수 내역
            for detail in details:
                print(f"      • {detail}")
            
            # ✅ 과매수 필터 체크
            if rsi >= 70:
                print(f"   ⛔ RSI 과매수 필터 작동 - 진입 금지")
            
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
    print("   1. 점수가 충분하지만 거래가 안 되면: MTF/ML 점수 확인 필요")
    print("   2. 실제 거래 신호 확인: python main_trading_bot.py → 테스트 모드")
    print("   3. RSI 70+ 코인은 과매수 필터로 자동 차단됨")
    print("="*80 + "\n")

if __name__ == "__main__":
    diagnose_signals()