# momentum_scanner_diagnosis.py - 모멘텀 스캐너가 작동하는지 확인

import pyupbit
import pandas as pd
from datetime import datetime
from momentum_scanner import MomentumScanner
from config import DYNAMIC_COIN_CONFIG, STABLE_PAIRS

def diagnose_momentum_scanner():
    """모멘텀 스캐너 상세 진단"""
    
    print("\n" + "="*80)
    print("🔥 모멘텀 스캐너 진단 시작")
    print("="*80)
    print(f"⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 설정 확인:")
    print(f"   - 활성화: {DYNAMIC_COIN_CONFIG['enabled']}")
    print(f"   - 갱신 주기: {DYNAMIC_COIN_CONFIG['refresh_interval']/3600:.0f}시간")
    print(f"   - 최대 선택: {DYNAMIC_COIN_CONFIG['max_dynamic_coins']}개")
    print(f"   - 최소 점수: {DYNAMIC_COIN_CONFIG['min_score']}")
    print("="*80)
    
    if not DYNAMIC_COIN_CONFIG['enabled']:
        print("❌ 모멘텀 스캐너가 비활성화되어 있습니다!")
        print("💡 config.py에서 DYNAMIC_COIN_CONFIG['enabled'] = True로 설정하세요.")
        return
    
    # 스캐너 초기화
    scanner = MomentumScanner()
    
    print("\n📊 현재 시장 상황 분석 중...")
    print("-"*80)
    
    # 주요 코인 체크
    major_coins = [
        'BTC', 'ETH', 'XRP', 'SOL', 'DOGE', 'ADA', 'AVAX', 'DOT', 
        'MATIC', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM', 'TRX', 'SHIB',
        'NEAR', 'BCH', 'APT', 'ARB', 'OP', 'SUI', 'SEI', 'HBAR'
    ]
    
    candidates = []
    
    for i, symbol in enumerate(major_coins):
        ticker = f"KRW-{symbol}"
        
        try:
            # 24시간 데이터
            df = pyupbit.get_ohlcv(ticker, interval="day", count=3)
            
            if df is None or len(df) < 2:
                continue
            
            # 변동률
            change_24h = ((df['close'].iloc[-1] - df['close'].iloc[-2]) / 
                         df['close'].iloc[-2] * 100)
            
            # 거래량
            volume_krw = df['close'].iloc[-1] * df['volume'].iloc[-1]
            
            # 변동성
            volatility = (df['high'].iloc[-1] - df['low'].iloc[-1]) / df['close'].iloc[-1]
            
            # 모멘텀 점수
            score = 0
            
            # 연속 상승
            if len(df) >= 3:
                if df['close'].iloc[-1] > df['close'].iloc[-2] > df['close'].iloc[-3]:
                    score += 2
            
            # 거래량 증가
            if df['volume'].iloc[-1] > df['volume'].iloc[-2] * 1.5:
                score += 2
            
            # 상승 강도
            if df['close'].iloc[-1] > df['open'].iloc[-1]:
                body_ratio = (df['close'].iloc[-1] - df['open'].iloc[-1]) / df['open'].iloc[-1]
                score += min(body_ratio * 100, 3)
            
            # 필터 체크
            volume_ok = volume_krw > scanner.min_volume
            volatility_ok = volatility < scanner.max_volatility
            change_ok = change_24h > 3
            score_ok = score > 5
            
            candidates.append({
                'symbol': symbol,
                'change_24h': change_24h,
                'volume': volume_krw,
                'volatility': volatility,
                'score': score,
                'volume_ok': volume_ok,
                'volatility_ok': volatility_ok,
                'change_ok': change_ok,
                'score_ok': score_ok,
                'pass_all': volume_ok and volatility_ok and change_ok and score_ok
            })
            
            # 진행률 표시 (5개마다)
            if (i + 1) % 5 == 0:
                print(f"   스캔 중... {i+1}/{len(major_coins)}")
        
        except Exception as e:
            continue
    
    # 결과 정렬
    candidates.sort(key=lambda x: (x['change_24h'] + x['score']), reverse=True)
    
    print("\n" + "="*80)
    print("📈 Top 10 코인 분석 결과")
    print("="*80)
    print(f"{'순위':<4} {'코인':<8} {'24h변동':<10} {'점수':<8} {'거래량':<15} {'필터':<10}")
    print("-"*80)
    
    for i, coin in enumerate(candidates[:10], 1):
        status = "✅ 통과" if coin['pass_all'] else "❌ 탈락"
        
        # 탈락 이유
        reasons = []
        if not coin['volume_ok']:
            reasons.append("거래량")
        if not coin['volatility_ok']:
            reasons.append("변동성")
        if not coin['change_ok']:
            reasons.append("변동률")
        if not coin['score_ok']:
            reasons.append("점수")
        
        reason_str = f" ({','.join(reasons)})" if reasons else ""
        
        print(f"{i:<4} {coin['symbol']:<8} "
              f"{coin['change_24h']:>8.2f}% "
              f"{coin['score']:>6.1f} "
              f"{coin['volume']/1e9:>10.0f}억 "
              f"{status}{reason_str}")
    
    # 합격 코인
    passed_coins = [c for c in candidates if c['pass_all']]
    
    print("\n" + "="*80)
    print(f"🎯 필터 통과 코인: {len(passed_coins)}개")
    print("="*80)
    
    if passed_coins:
        print("✅ 선택된 코인:")
        for coin in passed_coins[:DYNAMIC_COIN_CONFIG['max_dynamic_coins']]:
            print(f"   - {coin['symbol']}: "
                  f"변동 {coin['change_24h']:+.1f}%, "
                  f"점수 {coin['score']:.1f}")
    else:
        print("❌ 조건을 만족하는 코인이 없습니다!")
        print("\n💡 원인 분석:")
        
        # 가장 가까운 코인 분석
        if candidates:
            best = candidates[0]
            print(f"\n가장 유력한 후보: {best['symbol']}")
            print(f"   24h 변동: {best['change_24h']:.2f}% (기준: 3%)")
            print(f"   모멘텀 점수: {best['score']:.1f} (기준: 5)")
            print(f"   거래량: {best['volume']/1e9:.0f}억원 (기준: 500억)")
            print(f"   변동성: {best['volatility']:.3f} (기준: 0.05)")
            
            print("\n💡 해결책:")
            if not best['change_ok']:
                print("   1. 시장이 횡보장입니다 → 변동률 기준을 2%로 낮추세요")
            if not best['score_ok']:
                print("   2. 모멘텀이 약합니다 → 점수 기준을 4점으로 낮추세요")
            if not best['volume_ok']:
                print("   3. 거래량이 부족합니다 → 기준을 300억으로 낮추세요")
    
    print("\n" + "="*80)
    print("🔧 실제 스캐너 테스트")
    print("="*80)
    
    # 실제 스캐너 실행
    print("실제 스캐너 실행 중...")
    selected = scanner.scan_top_performers(top_n=DYNAMIC_COIN_CONFIG['max_dynamic_coins'])
    
    if selected:
        print(f"✅ 스캐너가 {len(selected)}개 코인을 찾았습니다:")
        for coin in selected:
            print(f"   - {coin}")
    else:
        print("❌ 스캐너가 코인을 찾지 못했습니다!")
    
    print("\n" + "="*80)
    print("📋 권장사항")
    print("="*80)
    
    if not passed_coins:
        print("""
현재 시장 상황(횡보장)에 맞게 기준을 완화하세요:

momentum_scanner.py 수정:
----------------------------------------
class MomentumScanner:
    def __init__(self):
        self.min_volume = 30_000_000_000  # 500억 → 300억
        self.max_volatility = 0.06         # 0.05 → 0.06
        
    def scan_top_performers(self, top_n=3):
        # ... 
        if coin['change_24h'] > 2 and coin['score'] > 4:  # 3→2, 5→4
            selected.append(coin['symbol'])
----------------------------------------

또는 config.py에서:
----------------------------------------
DYNAMIC_COIN_CONFIG = {
    'enabled': True,
    'max_dynamic_coins': 3,
    'refresh_interval': 3600 * 3,  # 6시간 → 3시간
    'min_score': 4,                # 6 → 4
}
----------------------------------------
""")
    else:
        print("""
✅ 모멘텀 스캐너가 정상 작동 중입니다!

확인사항:
1. 봇이 실행 중이라면 최대 6시간 대기해야 갱신됩니다
2. 즉시 갱신하려면 봇을 재시작하세요
3. 로그에서 "모멘텀 코인 스캔 시작..." 메시지를 확인하세요
""")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    diagnose_momentum_scanner()