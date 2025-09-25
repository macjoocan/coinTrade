# pump_dump_analyzer.py - 급등 후 하락 패턴 분석

import pyupbit
import pandas as pd
from datetime import datetime, timedelta

def analyze_pump_patterns():
    """급등 코인의 이후 패턴 분석"""
    
    print("="*60)
    print("급등 코인 패턴 분석 (최근 30일)")
    print("="*60)
    
    # 주요 코인들 분석
    symbols = ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK', 'WIF']  # 변동성 높은 코인들
    
    pump_stats = {
        'total_pumps': 0,
        'profitable_after_24h': 0,
        'loss_after_24h': 0,
        'avg_drawdown': []
    }
    
    for symbol in symbols:
        ticker = f"KRW-{symbol}"
        try:
            # 30일 데이터
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=720)
            
            if df is not None:
                # 시간당 변동률 계산
                df['change'] = df['close'].pct_change() * 100
                
                # 10% 이상 급등 시점 찾기
                pump_points = df[df['change'] > 10].index
                
                for pump_time in pump_points:
                    pump_idx = df.index.get_loc(pump_time)
                    
                    if pump_idx < len(df) - 24:  # 24시간 후 데이터 존재
                        pump_price = df.iloc[pump_idx]['close']
                        
                        # 24시간 후 가격
                        price_24h = df.iloc[pump_idx + 24]['close']
                        
                        # 24시간 내 최저가
                        min_price = df.iloc[pump_idx:pump_idx+24]['low'].min()
                        
                        # 통계
                        pump_stats['total_pumps'] += 1
                        
                        if price_24h > pump_price:
                            pump_stats['profitable_after_24h'] += 1
                        else:
                            pump_stats['loss_after_24h'] += 1
                        
                        drawdown = ((min_price - pump_price) / pump_price) * 100
                        pump_stats['avg_drawdown'].append(drawdown)
                        
        except:
            pass
    
    # 결과 출력
    if pump_stats['total_pumps'] > 0:
        win_rate = pump_stats['profitable_after_24h'] / pump_stats['total_pumps'] * 100
        avg_dd = sum(pump_stats['avg_drawdown']) / len(pump_stats['avg_drawdown'])
        
        print(f"\n📊 분석 결과:")
        print(f"총 급등 횟수: {pump_stats['total_pumps']}회")
        print(f"24시간 후 수익: {pump_stats['profitable_after_24h']}회 ({win_rate:.1f}%)")
        print(f"24시간 후 손실: {pump_stats['loss_after_24h']}회")
        print(f"평균 최대 낙폭: {avg_dd:.1f}%")
        
        print("\n⚠️ 위험 요소:")
        if win_rate < 40:
            print("  🔴 승률 40% 미만 - 매우 위험")
        if avg_dd < -10:
            print("  🔴 평균 10% 이상 하락 - 손절 어려움")
            
    return pump_stats

# 실제 사례 분석
def real_case_study():
    """실제 급등 사례 분석"""
    
    print("\n" + "="*60)
    print("실제 급등 코인 사례")
    print("="*60)
    
    cases = [
        {
            'coin': 'LUNA (2022.05)',
            'pump': '+100%',
            'result': '-99.9% (며칠 내 붕괴)',
            'lesson': 'FOMO는 파멸의 지름길'
        },
        {
            'coin': 'FTT (2022.11)',
            'pump': '+30%',
            'result': '-95% (거래소 파산)',
            'lesson': '급등 뒤엔 이유가 있다'
        },
        {
            'coin': 'DOGE (매 급등시)',
            'pump': '+20-50%',
            'result': '-30-60% (1-2일 내)',
            'lesson': '밈코인은 특히 위험'
        }
    ]
    
    for case in cases:
        print(f"\n{case['coin']}:")
        print(f"  급등: {case['pump']}")
        print(f"  결과: {case['result']}")
        print(f"  교훈: {case['lesson']}")

if __name__ == "__main__":
    analyze_pump_patterns()
    real_case_study()