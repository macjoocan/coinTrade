# fix_sideways_market.py - 횡보장 대응 수정 패치
"""
이 스크립트는 현재 시장 상황을 확인하고
improved_strategy.py의 수정 방법을 안내합니다.
"""

import pyupbit
from datetime import datetime

def check_market_condition():
    """현재 시장 상황 확인"""
    
    print("\n" + "="*80)
    print("🔍 시장 상황 진단")
    print("="*80)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    coins = ['BTC', 'ETH', 'SOL']
    signals = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    
    for coin in coins:
        ticker = f"KRW-{coin}"
        try:
            df = pyupbit.get_ohlcv(ticker, interval="day", count=3)
            if df is not None and len(df) >= 3:
                change = ((df['close'].iloc[-1] - df['close'].iloc[0]) 
                         / df['close'].iloc[0] * 100)
                
                if change > 3:
                    signals['bullish'] += 1
                    status = "🟢 강세"
                elif change < -3:
                    signals['bearish'] += 1
                    status = "🔴 약세"
                else:
                    signals['neutral'] += 1
                    status = "⚪ 횡보"
                
                print(f"{coin:5s}: 3일 변동 {change:+6.2f}% → {status}")
        except:
            print(f"{coin:5s}: 데이터 없음")
    
    # 시장 판단
    print()
    print("-"*80)
    if signals['bearish'] >= 2:
        market = 'bearish'
        emoji = '🐻'
        desc = '약세장'
    elif signals['bullish'] >= 2:
        market = 'bullish'
        emoji = '🐂'
        desc = '강세장'
    else:
        market = 'neutral'
        emoji = '➡️'
        desc = '횡보장'
    
    print(f"📊 시장 판단: {emoji} {desc.upper()} ({market})")
    print("-"*80)
    
    return market

def show_threshold_adjustment(market):
    """현재 시장에서의 threshold 조정 보기"""
    
    base = 5.5  # 현재 기본 threshold
    
    print("\n" + "="*80)
    print("🎯 진입 기준 조정")
    print("="*80)
    
    print(f"\n기본 기준: {base}점")
    print(f"현재 시장: {market}")
    print()
    
    # 현재 코드 동작
    print("【현재 코드】")
    if market == 'bearish':
        current = base + 1.0
    elif market == 'bullish':
        current = base - 0.5
    else:  # neutral
        current = base  # ⚠️ 문제!
    
    print(f"  조정된 기준: {current}점")
    print(f"  현재 점수: 3.5점")
    print(f"  결과: {'❌ 진입 불가' if 3.5 < current else '✅ 진입 가능'} ({current - 3.5:+.1f}점 차이)")
    
    # 수정 후 동작 - 옵션 1
    print("\n【수정 옵션 1: 횡보장 -0.8】")
    if market == 'bearish':
        new1 = base + 1.0
    elif market == 'bullish':
        new1 = base - 0.5
    else:  # neutral
        new1 = base - 0.8  # 완화
    
    print(f"  조정된 기준: {new1}점")
    print(f"  결과: {'❌ 진입 불가' if 3.5 < new1 else '✅ 진입 가능'} ({new1 - 3.5:+.1f}점 차이)")
    
    # 수정 후 동작 - 옵션 2
    print("\n【수정 옵션 2: 횡보장 -1.5】")
    if market == 'bearish':
        new2 = base + 0.5
    elif market == 'bullish':
        new2 = base - 1.0
    else:  # neutral
        new2 = base - 1.5  # 더 공격적
    
    print(f"  조정된 기준: {new2}점")
    print(f"  결과: {'❌ 진입 불가' if 3.5 < new2 else '✅ 진입 가능'} ({new2 - 3.5:+.1f}점 차이)")
    
    # 수정 후 동작 - 옵션 3
    print("\n【수정 옵션 3: Base 3.5 + 횡보장 그대로】")
    base3 = 3.5
    if market == 'bearish':
        new3 = base3 + 1.0
    elif market == 'bullish':
        new3 = base3 - 0.5
    else:  # neutral
        new3 = base3
    
    print(f"  조정된 기준: {new3}점")
    print(f"  결과: {'❌ 진입 불가' if 3.5 < new3 else '✅ 진입 가능'} ({new3 - 3.5:+.1f}점 차이)")
    
    print()
    print("="*80)

def show_fix_instructions(market):
    """수정 방법 안내"""
    
    print("\n" + "="*80)
    print("🔧 수정 방법")
    print("="*80)
    
    if market == 'neutral':
        print("\n⚠️  횡보장이 감지되었습니다!")
        print("   현재 코드는 횡보장에서 진입 기준을 완화하지 않습니다.\n")
    
    print("【추천 수정 - improved_strategy.py 약 146줄】")
    print("-"*80)
    print("""
# 기존 코드 (❌ 횡보장 미완화)
if market_condition == 'bearish':
    adjusted_threshold = base_threshold + 1.0
elif market_condition == 'bullish':
    adjusted_threshold = base_threshold - 0.5
else:  # neutral
    adjusted_threshold = base_threshold  # ← 문제!

# 수정 코드 (✅ 횡보장 완화)
if market_condition == 'bearish':
    adjusted_threshold = base_threshold + 0.5  # 1.0 → 0.5
elif market_condition == 'bullish':
    adjusted_threshold = base_threshold - 1.0  # -0.5 → -1.0
else:  # neutral (횡보장)
    adjusted_threshold = base_threshold - 1.5  # ← 수정!
""")
    print("-"*80)
    
    print("\n【또는 config.py에서 base 자체를 낮추기】")
    print("-"*80)
    print("""
ADVANCED_CONFIG = {
    'entry_score_threshold': 3.5,  # 5.5 → 3.5
    # ... 나머지 유지
}
""")
    print("-"*80)
    
    print("\n💡 추천:")
    if market == 'neutral':
        print("   현재 횡보장이므로 improved_strategy.py를 수정하는 것이 좋습니다.")
        print("   또는 config.py의 base threshold를 3.5로 낮추세요.")
    elif market == 'bullish':
        print("   강세장인데 거래가 안 된다면 base threshold를 낮추세요.")
    else:
        print("   약세장이므로 신중하게 진입 기준을 설정하세요.")
    
    print("\n="*80)

def main():
    print("\n" + "="*80)
    print("🩹 횡보장 대응 패치 진단")
    print("="*80)
    
    # 1. 시장 상황 확인
    market = check_market_condition()
    
    # 2. Threshold 조정 시뮬레이션
    show_threshold_adjustment(market)
    
    # 3. 수정 방법 안내
    show_fix_instructions(market)
    
    print("\n✅ 진단 완료!")
    print("   위의 수정 방법 중 하나를 적용한 후 봇을 재시작하세요.\n")

if __name__ == "__main__":
    main()