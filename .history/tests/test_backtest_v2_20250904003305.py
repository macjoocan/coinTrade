"""
매매 신호 디버깅 스크립트
왜 거래 신호가 없는지 분석
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from upbit_trader import *
import pandas as pd
import matplotlib.pyplot as plt

def analyze_signals_debug():
    """신호 생성 과정 상세 분석"""
    print("=" * 60)
    print("매매 신호 디버깅")
    print("=" * 60)
    
    # 설정 초기화
    class TestConfig:
        def __init__(self):
            self.access_key = ""
            self.secret_key = ""
            self.trading_params = {
                'initial_capital': 1000000,
                'max_position_size': 0.2,
                'commission': 0.0005
            }
            self.risk_params = {
                'stop_loss_pct': 0.05,
                'take_profit_pct': 0.1,
                'max_daily_loss': 0.02,
                'risk_per_trade': 0.02
            }
    
    config = TestConfig()
    trader = UpbitTrader(config)
    risk_manager = RiskManager(config)
    strategy = AdvancedTradingStrategy(trader, risk_manager)
    
    # 데이터 수집
    print("\n1. 데이터 수집 중...")
    df = trader.get_historical_data("KRW-BTC", days=100)
    
    if df.empty:
        print("❌ 데이터 수집 실패")
        return
    
    print(f"✓ 데이터 수집: {len(df)}일")
    
    # 지표 계산
    print("\n2. 기술적 지표 계산...")
    df = strategy.calculate_indicators(df)
    
    # 신호 생성 과정 디버깅
    print("\n3. 신호 생성 분석...")
    print("-" * 60)
    
    buy_signals_count = 0
    sell_signals_count = 0
    max_buy_score = 0
    max_sell_score = 0
    
    # 최근 20일 데이터만 상세 분석
    for i in range(max(50, len(df)-20), len(df)):
        row = df.iloc[i]
        date = row['date']
        
        # 매수 점수 계산
        buy_score = 0
        buy_conditions = []
        
        # 트렌드 조건
        if row['sma_20'] > row['sma_50']:
            buy_score += 2
            buy_conditions.append("SMA20>SMA50(+2)")
        if row['close'] > row['sma_20']:
            buy_score += 1
            buy_conditions.append("Close>SMA20(+1)")
        
        # RSI
        if 30 < row['rsi'] < 70:
            buy_score += 2
            buy_conditions.append(f"RSI={row['rsi']:.1f}(+2)")
        
        # MACD
        if row['macd'] > row['macd_signal']:
            buy_score += 2
            buy_conditions.append("MACD>Signal(+2)")
        
        # 볼린저밴드
        bb_position = (row['close'] - row['bb_lower']) / (row['bb_upper'] - row['bb_lower'])
        if 0.2 < bb_position < 0.8:
            buy_score += 1
            buy_conditions.append(f"BB={bb_position:.2f}(+1)")
        
        # 스토캐스틱
        if row['stoch_k'] < 80 and row['stoch_k'] > row['stoch_d']:
            buy_score += 2
            buy_conditions.append("Stoch OK(+2)")
        
        # 매도 점수 계산
        sell_score = 0
        sell_conditions = []
        
        if row['sma_20'] < row['sma_50']:
            sell_score += 2
            sell_conditions.append("SMA20<SMA50(+2)")
        if row['close'] < row['sma_20']:
            sell_score += 1
            sell_conditions.append("Close<SMA20(+1)")
        if row['rsi'] > 70:
            sell_score += 2
            sell_conditions.append(f"RSI={row['rsi']:.1f}(+2)")
        if row['macd'] < row['macd_signal']:
            sell_score += 2
            sell_conditions.append("MACD<Signal(+2)")
        if bb_position > 0.9:
            sell_score += 1
            sell_conditions.append(f"BB={bb_position:.2f}(+1)")
        if row['stoch_k'] > 80 and row['stoch_k'] < row['stoch_d']:
            sell_score += 2
            sell_conditions.append("Stoch OB(+2)")
        
        # 최대 점수 업데이트
        max_buy_score = max(max_buy_score, buy_score)
        max_sell_score = max(max_sell_score, sell_score)
        
        # 신호 판단
        signal = "HOLD"
        if buy_score >= 6:
            signal = "BUY"
            buy_signals_count += 1
        elif sell_score >= 6:
            signal = "SELL"
            sell_signals_count += 1
        
        # 상세 출력 (점수가 높은 경우만)
        if buy_score >= 4 or sell_score >= 4:
            print(f"\n날짜: {date.date()}")
            print(f"  가격: {row['close']:,.0f} KRW")
            print(f"  매수 점수: {buy_score}/10 - {', '.join(buy_conditions)}")
            print(f"  매도 점수: {sell_score}/10 - {', '.join(sell_conditions)}")
            print(f"  → 신호: {signal}")
    
    # 요약
    print("\n" + "=" * 60)
    print("4. 분석 요약")
    print("=" * 60)
    print(f"총 분석 기간: {len(df)}일")
    print(f"매수 신호: {buy_signals_count}회")
    print(f"매도 신호: {sell_signals_count}회")
    print(f"최대 매수 점수: {max_buy_score}/10")
    print(f"최대 매도 점수: {max_sell_score}/10")
    
    # 현재 시장 상태
    latest = df.iloc[-1]
    print(f"\n5. 현재 시장 상태")
    print("-" * 60)
    print(f"현재가: {latest['close']:,.0f} KRW")
    print(f"RSI: {latest['rsi']:.2f}")
    print(f"트렌드: {'상승' if latest['sma_20'] > latest['sma_50'] else '하락'}")
    
    bb_pos = (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower'])
    print(f"볼린저밴드 위치: {bb_pos:.1%}")
    
    if latest['rsi'] > 70:
        print("⚠️ RSI 과매수 구간")
    elif latest['rsi'] < 30:
        print("⚠️ RSI 과매도 구간")
    else:
        print("✓ RSI 중립 구간")
    
    # 시각화
    print("\n6. 지표 시각화...")
    fig, axes = plt.subplots(3, 1, figsize=(15, 10))
    
    # 가격 차트
    ax1 = axes[0]
    ax1.plot(df['date'], df['close'], label='Close', color='black', linewidth=1)
    ax1.plot(df['date'], df['sma_20'], label='SMA20', alpha=0.7)
    ax1.plot(df['date'], df['sma_50'], label='SMA50', alpha=0.7)
    ax1.fill_between(df['date'], df['bb_upper'], df['bb_lower'], alpha=0.1)
    ax1.set_title('BTC/KRW Price')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # RSI
    ax2 = axes[1]
    ax2.plot(df['date'], df['rsi'], color='purple')
    ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought')
    ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='Oversold')
    ax2.axhline(y=50, color='gray', linestyle='-', alpha=0.3)
    ax2.set_title('RSI')
    ax2.set_ylim(0, 100)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # MACD
    ax3 = axes[2]
    ax3.plot(df['date'], df['macd'], label='MACD', color='blue')
    ax3.plot(df['date'], df['macd_signal'], label='Signal', color='red')
    ax3.bar(df['date'], df['macd_histogram'], label='Histogram', alpha=0.3)
    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    ax3.set_title('MACD')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('signal_debug.png', dpi=100)
    plt.show()
    
    print("✓ 차트 저장: signal_debug.png")
    
    # 권장사항
    print("\n7. 권장사항")
    print("-" * 60)
    if buy_signals_count == 0 and sell_signals_count == 0:
        print("• 신호 조건이 너무 엄격합니다 (6점 → 5점으로 완화 고려)")
        print("• 더 긴 기간 데이터로 테스트해보세요 (200일)")
        print("• 다른 마켓도 테스트해보세요 (KRW-ETH, KRW-XRP)")
    elif buy_signals_count + sell_signals_count < 5:
        print("• 거래 신호가 적습니다")
        print("• 변동성이 큰 시간대(분봉)로 테스트 고려")
    else:
        print("• 신호 생성이 정상적입니다")
        print("• Paper Trading으로 진행 가능합니다")
    
    return df

if __name__ == "__main__":
    df = analyze_signals_debug()
    
    # 추가 테스트: 신호 조건 완화
    print("\n" + "=" * 60)
    print("8. 신호 조건 완화 테스트 (6점 → 5점)")
    print("=" * 60)
    
    if df is not None:
        # 5점 기준으로 다시 계산
        signals_5 = []
        for i in range(50, len(df)):
            row = df.iloc[i]
            
            # 간단한 점수 계산
            buy_score = 0
            if row['sma_20'] > row['sma_50']: buy_score += 2
            if row['close'] > row['sma_20']: buy_score += 1
            if 30 < row['rsi'] < 70: buy_score += 2
            if row['macd'] > row['macd_signal']: buy_score += 2
            
            sell_score = 0
            if row['sma_20'] < row['sma_50']: sell_score += 2
            if row['close'] < row['sma_20']: sell_score += 1
            if row['rsi'] > 70: sell_score += 2
            if row['macd'] < row['macd_signal']: sell_score += 2
            
            if buy_score >= 5:
                signals_5.append('buy')
            elif sell_score >= 5:
                signals_5.append('sell')
            else:
                signals_5.append('hold')
        
        buy_count_5 = signals_5.count('buy')
        sell_count_5 = signals_5.count('sell')
        
        print(f"5점 기준 매수 신호: {buy_count_5}회")
        print(f"5점 기준 매도 신호: {sell_count_5}회")
        
        if buy_count_5 + sell_count_5 > 0:
            print("→ 5점으로 낮추면 거래 신호가 발생합니다!")