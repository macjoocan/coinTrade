# trading_log_analyzer.py - trading.log 분석 및 설정 최적화 제안

import re
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import json

class TradingLogAnalyzer:
    """거래 로그 분석 및 최적 설정 제안"""
    
    def __init__(self, log_file='trading.log'):
        self.log_file = log_file
        self.trades = []
        self.market_conditions = {}
        
    def parse_log(self):
        """로그 파일 파싱"""
        print("\n" + "="*80)
        print("📊 Trading Log 분석 시작")
        print("="*80)
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_trade = {}
        
        for line in lines:
            # 매수 기록
            if '매수 완료' in line or '✅ 매수 완료' in line:
                match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = match.group(1)
                    
                    # 심볼 추출
                    symbol_match = re.search(r'매수 완료: ([A-Z]+)', line)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                    
                    # 가격 추출
                    price_match = re.search(r'@ ([\d,]+)', line)
                    if price_match:
                        price = float(price_match.group(1).replace(',', ''))
                    
                    current_trade = {
                        'symbol': symbol,
                        'entry_time': timestamp,
                        'entry_price': price,
                        'type': 'buy'
                    }
            
            # 매도 기록
            elif '매도 완료' in line or '🔴 매도 완료' in line:
                match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match:
                    timestamp = match.group(1)
                    
                    # 심볼 추출
                    symbol_match = re.search(r'매도 완료: ([A-Z]+)', line)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                    
                    # 가격 추출
                    price_match = re.search(r'@ ([\d,]+)', line)
                    if price_match:
                        exit_price = float(price_match.group(1).replace(',', ''))
                    
                    # PnL 추출
                    pnl_match = re.search(r'PnL ([+-]?[\d,]+)', line)
                    pnl_rate_match = re.search(r'\(([+-]?\d+\.\d+)%\)', line)
                    
                    if pnl_match:
                        pnl = float(pnl_match.group(1).replace(',', ''))
                    if pnl_rate_match:
                        pnl_rate = float(pnl_rate_match.group(1)) / 100
                    
                    # 매칭되는 매수 찾기
                    if current_trade.get('symbol') == symbol:
                        current_trade.update({
                            'exit_time': timestamp,
                            'exit_price': exit_price,
                            'pnl': pnl,
                            'pnl_rate': pnl_rate
                        })
                        
                        self.trades.append(current_trade.copy())
                        current_trade = {}
            
            # 진입 조건 기록
            elif '진입 조건 충족' in line or '✅ 진입 조건 충족' in line:
                score_match = re.search(r'점수: ([\d.]+)', line)
                if score_match and current_trade:
                    current_trade['entry_score'] = float(score_match.group(1))
        
        print(f"✅ 총 {len(self.trades)}개 거래 파싱 완료")
        return self.trades
    
    def analyze_trades(self):
        """거래 분석"""
        if not self.trades:
            print("❌ 분석할 거래가 없습니다")
            return
        
        df = pd.DataFrame(self.trades)
        
        print("\n" + "="*80)
        print("📈 거래 통계")
        print("="*80)
        
        total = len(df)
        wins = len(df[df['pnl'] > 0])
        losses = len(df[df['pnl'] <= 0])
        win_rate = wins / total if total > 0 else 0
        
        print(f"총 거래: {total}회")
        print(f"승: {wins}회 | 패: {losses}회")
        print(f"승률: {win_rate:.1%}")
        
        if total > 0:
            print(f"\n평균 손익: {df['pnl'].mean():,.0f}원")
            print(f"평균 수익률: {df['pnl_rate'].mean():.2%}")
            print(f"최대 이익: {df['pnl'].max():,.0f}원 ({df['pnl_rate'].max():.2%})")
            print(f"최대 손실: {df['pnl'].min():,.0f}원 ({df['pnl_rate'].min():.2%})")
        
        # 손실 거래 분석
        losses_df = df[df['pnl'] < 0]
        if len(losses_df) > 0:
            print("\n" + "-"*80)
            print("💔 손실 거래 상세")
            print("-"*80)
            
            for _, trade in losses_df.iterrows():
                print(f"\n{trade['symbol']} | {trade['entry_time']}")
                print(f"  진입: {trade['entry_price']:,.0f} → 청산: {trade['exit_price']:,.0f}")
                print(f"  손실: {trade['pnl']:,.0f}원 ({trade['pnl_rate']:.2%})")
                if 'entry_score' in trade:
                    print(f"  진입점수: {trade.get('entry_score', 'N/A')}")
        
        return df
    
    def analyze_market_conditions(self, df):
        """거래 당시 시장 상황 분석"""
        print("\n" + "="*80)
        print("🌐 시장 상황 분석 (거래 시점 기준)")
        print("="*80)
        
        market_data = []
        
        for _, trade in df.iterrows():
            symbol = trade['symbol']
            entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S')
            
            try:
                # 진입 시점의 시장 데이터
                ticker = f"KRW-{symbol}"
                
                # 일봉 데이터
                end_date = entry_time
                start_date = end_date - timedelta(days=10)
                
                df_ohlcv = pyupbit.get_ohlcv(
                    ticker, 
                    interval="day",
                    to=end_date.strftime('%Y-%m-%d %H:%M:%S'),
                    count=10
                )
                
                if df_ohlcv is not None and len(df_ohlcv) >= 5:
                    # 추세 계산
                    sma_5 = df_ohlcv['close'].tail(5).mean()
                    current_price = df_ohlcv['close'].iloc[-1]
                    
                    # 변동성
                    volatility = df_ohlcv['close'].pct_change().std()
                    
                    # 5일 수익률
                    returns_5d = (current_price - df_ohlcv['close'].iloc[-5]) / df_ohlcv['close'].iloc[-5]
                    
                    # RSI 간이 계산
                    delta = df_ohlcv['close'].diff()
                    gain = (delta.where(delta > 0, 0)).mean()
                    loss = (-delta.where(delta < 0, 0)).mean()
                    rs = gain / loss if loss > 0 else 1
                    rsi = 100 - (100 / (1 + rs))
                    
                    market_data.append({
                        'symbol': symbol,
                        'entry_time': trade['entry_time'],
                        'trend': 'up' if current_price > sma_5 else 'down',
                        'volatility': volatility,
                        'returns_5d': returns_5d,
                        'rsi': rsi,
                        'pnl_rate': trade['pnl_rate']
                    })
                    
                    print(f"\n{symbol} ({trade['entry_time']}):")
                    print(f"  추세: {'📈 상승' if current_price > sma_5 else '📉 하락'}")
                    print(f"  5일 수익률: {returns_5d:+.2%}")
                    print(f"  변동성: {volatility:.3f}")
                    print(f"  RSI: {rsi:.1f}")
                    print(f"  결과: {trade['pnl_rate']:+.2%}")
            
            except Exception as e:
                print(f"  ⚠️ {symbol} 데이터 없음: {e}")
                continue
        
        self.market_conditions = pd.DataFrame(market_data)
        return self.market_conditions
    
    def suggest_optimal_settings(self, trades_df, market_df):
        """최적 설정 제안"""
        print("\n" + "="*80)
        print("💡 최적 설정 제안")
        print("="*80)
        
        # 1. 진입 점수 분석
        losses = trades_df[trades_df['pnl'] < 0]
        wins = trades_df[trades_df['pnl'] > 0]
        
        print("\n【1️⃣ 진입 점수 분석】")
        print("-"*80)
        
        if 'entry_score' in losses.columns and len(losses) > 0:
            avg_loss_score = losses['entry_score'].mean()
            avg_win_score = wins['entry_score'].mean() if len(wins) > 0 else 0
            
            print(f"손실 거래 평균 점수: {avg_loss_score:.2f}")
            print(f"수익 거래 평균 점수: {avg_win_score:.2f}")
            
            # 제안 점수
            if avg_win_score > avg_loss_score:
                suggested_threshold = (avg_win_score + avg_loss_score) / 2 + 0.5
            else:
                suggested_threshold = 6.5
            
            print(f"\n✅ 제안 진입 점수: {suggested_threshold:.1f} (현재: 5.5)")
        else:
            suggested_threshold = 6.0
            print(f"✅ 제안 진입 점수: {suggested_threshold:.1f}")
        
        # 2. 손절 분석
        print("\n【2️⃣ 손절 설정 분석】")
        print("-"*80)
        
        if len(losses) > 0:
            avg_loss = losses['pnl_rate'].mean()
            max_loss = losses['pnl_rate'].min()
            
            print(f"평균 손실: {avg_loss:.2%}")
            print(f"최대 손실: {max_loss:.2%}")
            
            # 손절 제안: 평균 손실의 80%
            suggested_stop_loss = abs(avg_loss) * 0.8
            suggested_stop_loss = max(0.008, min(suggested_stop_loss, 0.015))
            
            print(f"\n✅ 제안 손절: {suggested_stop_loss:.1%} (현재: 1.2%)")
        else:
            suggested_stop_loss = 0.012
        
        # 3. 익절 분석
        print("\n【3️⃣ 익절 설정 분석】")
        print("-"*80)
        
        if len(wins) > 0:
            avg_win = wins['pnl_rate'].mean()
            max_win = wins['pnl_rate'].max()
            
            print(f"평균 수익: {avg_win:.2%}")
            print(f"최대 수익: {max_win:.2%}")
            
            # 익절 제안
            suggested_take_profit = avg_win * 0.9
            suggested_take_profit = max(0.015, min(suggested_take_profit, 0.04))
            
            print(f"\n✅ 제안 익절: {suggested_take_profit:.1%} (현재: 1.0%)")
        else:
            suggested_take_profit = 0.015
        
        # 4. 시장 상황별 분석
        print("\n【4️⃣ 시장 상황별 설정】")
        print("-"*80)
        
        if len(market_df) > 0:
            # 상승장 vs 하락장
            uptrend = market_df[market_df['trend'] == 'up']
            downtrend = market_df[market_df['trend'] == 'down']
            
            if len(uptrend) > 0:
                uptrend_winrate = len(uptrend[uptrend['pnl_rate'] > 0]) / len(uptrend)
                print(f"상승장 승률: {uptrend_winrate:.1%}")
            
            if len(downtrend) > 0:
                downtrend_winrate = len(downtrend[downtrend['pnl_rate'] > 0]) / len(downtrend)
                print(f"하락장 승률: {downtrend_winrate:.1%}")
            
            # 변동성 분석
            high_vol = market_df[market_df['volatility'] > 0.03]
            low_vol = market_df[market_df['volatility'] <= 0.03]
            
            if len(high_vol) > 0:
                high_vol_winrate = len(high_vol[high_vol['pnl_rate'] > 0]) / len(high_vol)
                print(f"\n고변동성 승률: {high_vol_winrate:.1%}")
            
            if len(low_vol) > 0:
                low_vol_winrate = len(low_vol[low_vol['pnl_rate'] > 0]) / len(low_vol)
                print(f"저변동성 승률: {low_vol_winrate:.1%}")
        
        # 5. 종합 제안
        print("\n" + "="*80)
        print("🎯 최종 제안 설정값")
        print("="*80)
        
        suggestions = {
            'ADVANCED_CONFIG': {
                'entry_score_threshold': round(suggested_threshold, 1),
                'comment': '진입 기준 상향 - 더 확실한 신호만'
            },
            'RISK_CONFIG': {
                'stop_loss': round(suggested_stop_loss, 4),
                'min_profit_target': round(suggested_take_profit, 4),
                'comment': '손절/익절 비율 최적화'
            },
            'STRATEGY_CONFIG': {
                'min_hold_time': 3600,  # 1시간
                'comment': '너무 빠른 청산 방지'
            }
        }
        
        print("\nconfig.py 수정 사항:")
        print("-"*80)
        print(f"""
ADVANCED_CONFIG = {{
    'entry_score_threshold': {suggestions['ADVANCED_CONFIG']['entry_score_threshold']},  # ⬆️ 상향 (기존: 5.5)
    # ... 기타 설정 유지
}}

RISK_CONFIG = {{
    'stop_loss': {suggestions['RISK_CONFIG']['stop_loss']},  # 조정 (기존: 0.012)
    'daily_loss_limit': 0.02,
    'max_positions': 5,
}}

STRATEGY_CONFIG = {{
    'min_profit_target': {suggestions['RISK_CONFIG']['min_profit_target']},  # 조정 (기존: 0.01)
    'max_trades_per_day': 30,
    'min_hold_time': {suggestions['STRATEGY_CONFIG']['min_hold_time']},  # 1시간
}}
""")
        
        # 6. 추가 권장사항
        print("\n" + "="*80)
        print("📋 추가 권장사항")
        print("="*80)
        
        print("""
1. 진입 조건 강화
   - MTF 최소 점수: 6.5 (현재: 6.0)
   - ML 최소 확률: 0.70 (현재: 0.65)
   
2. 부분 매도 활성화
   - +1.5%에서 30% 매도
   - +2.5%에서 추가 30% 매도
   - +4.0%에서 나머지 매도

3. 보유 시간 연장
   - 최소 1시간 보유 (충분한 추세 전개 대기)

4. 시장 상황 필터 강화
   - 하락장에서는 진입 점수 +1.0 추가
   - 고변동성(>3%)에서는 포지션 크기 50% 축소

5. 동적 코인 선택 기준 강화
   - 최소 변동률: 3% (현재: 2%)
   - 최소 점수: 5 (현재: 4)
""")
        
        # JSON 저장
        with open('suggested_config.json', 'w', encoding='utf-8') as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        
        print("\n✅ 제안 설정이 'suggested_config.json'에 저장되었습니다")
        
        return suggestions

def main():
    """메인 실행"""
    analyzer = TradingLogAnalyzer('trading.log')
    
    # 1. 로그 파싱
    trades = analyzer.parse_log()
    
    if not trades:
        print("\n❌ 파싱된 거래가 없습니다. trading.log 파일을 확인하세요.")
        return
    
    # 2. 거래 분석
    trades_df = analyzer.analyze_trades()
    
    # 3. 시장 상황 분석
    market_df = analyzer.analyze_market_conditions(trades_df)
    
    # 4. 최적 설정 제안
    suggestions = analyzer.suggest_optimal_settings(trades_df, market_df)
    
    print("\n" + "="*80)
    print("✅ 분석 완료!")
    print("="*80)
    print("\n다음 단계:")
    print("1. 위의 제안 설정을 config.py에 적용")
    print("2. suggested_config.json 파일 확인")
    print("3. 봇 재시작 후 성능 모니터링")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()