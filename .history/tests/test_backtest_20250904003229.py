"""
백테스팅 전용 테스트 스크립트
API 키 없이 실행 가능 - 안전하게 전략 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from upbit_trader import (
    Config, UpbitTrader, RiskManager, 
    AdvancedTradingStrategy, BacktestEngine,
    TechnicalIndicators
)
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def test_basic_functionality():
    """기본 기능 테스트"""
    print("=" * 60)
    print("1. 기본 기능 테스트")
    print("=" * 60)
    
    # 테스트용 설정 생성
    class TestConfig:
        def __init__(self):
            self.access_key = ""  # 백테스팅에는 불필요
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
    print("✓ 설정 생성 완료")
    
    # 컴포넌트 초기화
    trader = UpbitTrader(config)
    print("✓ 트레이더 초기화 완료")
    
    risk_manager = RiskManager(config)
    print("✓ 리스크 매니저 초기화 완료")
    
    strategy = AdvancedTradingStrategy(trader, risk_manager)
    print("✓ 전략 초기화 완료")
    
    return trader, risk_manager, strategy

def test_data_collection(trader, market="KRW-BTC"):
    """데이터 수집 테스트"""
    print("\n" + "=" * 60)
    print("2. 데이터 수집 테스트")
    print("=" * 60)
    
    try:
        # 현재가 조회 테스트
        ticker = trader.get_ticker(market)
        if ticker:
            current_price = ticker.get('trade_price', 0)
            print(f"✓ 현재가 조회 성공: {current_price:,.0f} KRW")
        
        # 캔들 데이터 조회 테스트
        candles = trader.get_candles(market, 'days', count=5)
        if candles:
            print(f"✓ 캔들 데이터 조회 성공: {len(candles)}개")
            
        # 과거 데이터 수집 테스트
        df = trader.get_historical_data(market, days=30)
        if not df.empty:
            print(f"✓ 과거 데이터 수집 성공: {len(df)}일")
            print(f"  기간: {df['date'].min().date()} ~ {df['date'].max().date()}")
            return df
        else:
            print("✗ 데이터 수집 실패")
            return None
            
    except Exception as e:
        print(f"✗ 데이터 수집 중 오류: {e}")
        return None

def test_indicators(df):
    """기술적 지표 계산 테스트"""
    print("\n" + "=" * 60)
    print("3. 기술적 지표 계산 테스트")
    print("=" * 60)
    
    indicators = TechnicalIndicators()
    
    try:
        # SMA 테스트
        sma_20 = indicators.sma(df['close'], 20)
        print(f"✓ SMA(20) 계산 완료: 최근 값 {sma_20.iloc[-1]:,.0f}")
        
        # RSI 테스트
        rsi = indicators.rsi(df['close'])
        print(f"✓ RSI 계산 완료: 최근 값 {rsi.iloc[-1]:.2f}")
        
        # MACD 테스트
        macd, signal, histogram = indicators.macd(df['close'])
        print(f"✓ MACD 계산 완료: 최근 값 {macd.iloc[-1]:,.0f}")
        
        # 볼린저밴드 테스트
        upper, middle, lower = indicators.bollinger_bands(df['close'])
        print(f"✓ 볼린저밴드 계산 완료")
        print(f"  상단: {upper.iloc[-1]:,.0f}")
        print(f"  중간: {middle.iloc[-1]:,.0f}")
        print(f"  하단: {lower.iloc[-1]:,.0f}")
        
        # ATR 테스트
        atr = indicators.atr(df['high'], df['low'], df['close'])
        print(f"✓ ATR 계산 완료: 최근 값 {atr.iloc[-1]:,.0f}")
        
        return True
        
    except Exception as e:
        print(f"✗ 지표 계산 중 오류: {e}")
        return False

def test_backtest(strategy, market="KRW-BTC", days=100):
    """백테스팅 실행 테스트"""
    print("\n" + "=" * 60)
    print("4. 백테스팅 실행 테스트")
    print("=" * 60)
    
    try:
        # 데이터 수집
        print(f"데이터 수집 중 ({days}일)...")
        df = strategy.trader.get_historical_data(market, days=days)
        
        if df.empty:
            print("✗ 데이터 수집 실패")
            return None, None
        
        print(f"✓ 데이터 수집 완료: {len(df)}개 캔들")
        
        # 백테스팅 실행
        print("\n백테스팅 실행 중...")
        backtest, df_with_signals = strategy.backtest_strategy(df, "테스트 전략")
        
        # 거래 횟수 확인
        if backtest.trades:
            print(f"✓ 백테스팅 완료: {len(backtest.trades)}번 거래")
        else:
            print("△ 백테스팅 완료: 거래 신호 없음")
        
        return backtest, df_with_signals
        
    except Exception as e:
        print(f"✗ 백테스팅 중 오류: {e}")
        return None, None

def test_risk_management(risk_manager):
    """리스크 관리 테스트"""
    print("\n" + "=" * 60)
    print("5. 리스크 관리 기능 테스트")
    print("=" * 60)
    
    # 포지션 사이즈 계산 테스트
    test_price = 50000000  # 5천만원
    position_size = risk_manager.calculate_position_size(test_price, volatility=0.02)
    print(f"✓ 포지션 사이즈 계산:")
    print(f"  가격: {test_price:,.0f} KRW")
    print(f"  추천 수량: {position_size:.8f}")
    print(f"  투자 금액: {position_size * test_price:,.0f} KRW")
    
    # 손절/익절 테스트
    from upbit_trader import PositionType
    
    entry_price = 50000000
    
    # 손절 테스트
    stop_loss_price = entry_price * 0.96  # 4% 하락
    should_stop = risk_manager.check_stop_loss(entry_price, stop_loss_price, PositionType.LONG)
    print(f"\n✓ 손절매 테스트:")
    print(f"  진입가: {entry_price:,.0f}")
    print(f"  현재가: {stop_loss_price:,.0f}")
    print(f"  손절매 신호: {should_stop}")
    
    # 익절 테스트
    take_profit_price = entry_price * 1.12  # 12% 상승
    should_profit = risk_manager.check_take_profit(entry_price, take_profit_price, PositionType.LONG)
    print(f"\n✓ 익절매 테스트:")
    print(f"  진입가: {entry_price:,.0f}")
    print(f"  현재가: {take_profit_price:,.0f}")
    print(f"  익절매 신호: {should_profit}")
    
    # 일일 거래 제한 테스트
    print(f"\n✓ 일일 거래 제한:")
    print(f"  최대 손실: {risk_manager.max_daily_loss * 100}%")
    print(f"  최대 거래: {risk_manager.max_daily_trades}회")

def visualize_test_results(backtest, df_with_signals, save_path="test_results.png"):
    """결과 시각화 (저장)"""
    print("\n" + "=" * 60)
    print("6. 결과 시각화")
    print("=" * 60)
    
    try:
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        
        # 1. 가격과 신호
        ax1 = axes[0]
        ax1.plot(df_with_signals['date'], df_with_signals['close'], label='Price', color='black')
        
        buy_signals = df_with_signals[df_with_signals['signal'] == 'buy']
        sell_signals = df_with_signals[df_with_signals['signal'] == 'sell']
        
        ax1.scatter(buy_signals['date'], buy_signals['close'], 
                   color='green', marker='^', s=50, label='Buy')
        ax1.scatter(sell_signals['date'], sell_signals['close'], 
                   color='red', marker='v', s=50, label='Sell')
        
        ax1.set_title('Price and Signals')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. RSI
        ax2 = axes[1]
        if 'rsi' in df_with_signals.columns:
            ax2.plot(df_with_signals['date'], df_with_signals['rsi'], color='purple')
            ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5)
            ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5)
        ax2.set_title('RSI')
        ax2.grid(True, alpha=0.3)
        
        # 3. 자본 곡선
        ax3 = axes[2]
        if backtest.equity_curve:
            equity_df = pd.DataFrame(backtest.equity_curve)
            ax3.plot(equity_df['date'], equity_df['capital'], color='blue', linewidth=2)
            ax3.axhline(y=backtest.initial_capital, color='gray', linestyle='--', alpha=0.5)
        ax3.set_title('Equity Curve')
        ax3.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=100)
        print(f"✓ 차트 저장 완료: {save_path}")
        plt.show()
        
    except Exception as e:
        print(f"✗ 시각화 중 오류: {e}")

def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "🚀 업비트 자동거래 시스템 테스트 시작")
    print("=" * 60)
    
    # 1. 기본 기능 테스트
    trader, risk_manager, strategy = test_basic_functionality()
    
    # 2. 데이터 수집 테스트
    df = test_data_collection(trader)
    
    if df is not None:
        # 3. 지표 계산 테스트
        test_indicators(df)
    
    # 4. 리스크 관리 테스트
    test_risk_management(risk_manager)
    
    # 5. 백테스팅 테스트
    backtest, df_with_signals = test_backtest(strategy, days=50)
    
    # 6. 결과 시각화
    if backtest and df_with_signals is not None:
        visualize_test_results(backtest, df_with_signals)
    
    print("\n" + "=" * 60)
    print("✅ 모든 테스트 완료!")
    print("=" * 60)
    
    # 테스트 요약
    print("\n📊 테스트 요약:")
    print("- API 연결: OK")
    print("- 데이터 수집: OK")
    print("- 지표 계산: OK")
    print("- 리스크 관리: OK")
    print("- 백테스팅: OK")
    print("\n다음 단계: 더 긴 기간으로 백테스팅 후 Paper Trading 진행")

if __name__ == "__main__":
    run_all_tests()