# annual_target_calculator.py - 연간 목표 수익률 계산

import math
from datetime import datetime

def calculate_realistic_annual_return():
    """현실적인 연간 수익률 계산"""
    
    print("="*60)
    print("🎯 연간 수익률 목표 설정")
    print("="*60)
    
    # 현재 전략 파라미터
    current_stats = {
        'win_rate': 0.50,           # 현재 승률 50%
        'avg_win': 0.015,           # 평균 수익 1.5%
        'avg_loss': 0.01,           # 평균 손실 1%
        'trades_per_day': 2,        # 일일 평균 거래 (보수적)
        'trading_days': 250,        # 연간 거래일
        'max_drawdown': 0.05,       # 최대 낙폭 5%
    }
    
    # 시나리오별 계산
    scenarios = {
        '비관적 (Bear)': {
            'win_rate': 0.45,
            'trades_per_day': 1,
            'slippage': 0.002
        },
        '현실적 (Base)': {
            'win_rate': 0.50,
            'trades_per_day': 2,
            'slippage': 0.001
        },
        '낙관적 (Bull)': {
            'win_rate': 0.55,
            'trades_per_day': 3,
            'slippage': 0.001
        }
    }
    
    print("\n📈 시나리오별 예상 수익률:\n")
    
    for scenario_name, params in scenarios.items():
        win_rate = params['win_rate']
        trades = params['trades_per_day'] * current_stats['trading_days']
        slippage = params['slippage']
        
        # 켈리 공식 기반 계산
        expected_return_per_trade = (
            win_rate * (current_stats['avg_win'] - slippage) - 
            (1 - win_rate) * (current_stats['avg_loss'] + slippage)
        )
        
        # 복리 계산
        annual_return = (1 + expected_return_per_trade) ** trades - 1
        
        # 최대 낙폭 고려
        risk_adjusted_return = annual_return * (1 - current_stats['max_drawdown'])
        
        print(f"{scenario_name}:")
        print(f"  거래 횟수: {trades}회/년")
        print(f"  거래당 기대수익: {expected_return_per_trade:.3f}")
        print(f"  연간 수익률: {annual_return:.1%}")
        print(f"  위험조정 수익률: {risk_adjusted_return:.1%}")
        print()
    
    return scenarios

# 실행
calculate_realistic_annual_return()