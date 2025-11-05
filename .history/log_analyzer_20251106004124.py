"""
Trade History Analyzer
trade_history.json 파일을 분석하여 최적의 설정값을 제안합니다.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict
from typing import Dict, List
import pyupbit


class TradeHistoryAnalyzer:
    def __init__(self, history_file: str = "trade_history.json"):
        self.history_file = history_file
        self.trades_df = None
        
    def load_data(self):
        """JSON 파일 로드"""
        print("📄 거래 기록 로드 중...")
        
        with open(self.history_file, 'r', encoding='utf-8') as f:
            trades = json.load(f)
        
        if not trades:
            print("⚠️  거래 기록이 없습니다.")
            return False
        
        # DataFrame 생성
        self.trades_df = pd.DataFrame(trades)
        self.trades_df['timestamp'] = pd.to_datetime(self.trades_df['timestamp'])
        self.trades_df['date'] = self.trades_df['timestamp'].dt.date
        
        print(f"✅ 총 {len(self.trades_df)}개 거래 로드 완료")
        return True
    
    def basic_statistics(self):
        """기본 통계 분석"""
        print("\n" + "="*60)
        print("📊 기본 통계")
        print("="*60)
        
        df = self.trades_df
        total_trades = len(df)
        
        # 승/패 구분
        winning = df[df['pnl'] > 0]
        losing = df[df['pnl'] <= 0]
        
        win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0
        
        # 손익
        total_pnl = df['pnl'].sum()
        total_fee = df['fee'].sum()
        net_pnl = total_pnl - total_fee
        
        # 평균
        avg_profit = winning['pnl_rate'].mean() * 100 if len(winning) > 0 else 0
        avg_loss = losing['pnl_rate'].mean() * 100 if len(losing) > 0 else 0
        
        # 최대/최소
        max_profit = df['pnl_rate'].max() * 100
        max_loss = df['pnl_rate'].min() * 100
        
        print(f"\n📈 거래 성과:")
        print(f"   총 거래: {total_trades}회")
        print(f"   승리: {len(winning)}회 ({win_rate:.1f}%)")
        print(f"   패배: {len(losing)}회 ({100-win_rate:.1f}%)")
        print(f"   \n   총 손익: {total_pnl:,.0f}원")
        print(f"   총 수수료: {total_fee:,.0f}원")
        print(f"   순 손익: {net_pnl:,.0f}원")
        print(f"   \n   평균 수익: {avg_profit:.2f}%")
        print(f"   평균 손실: {avg_loss:.2f}%")
        print(f"   손익비: 1:{abs(avg_profit/avg_loss):.2f}" if avg_loss != 0 else "   손익비: N/A")
        print(f"   \n   최대 수익: {max_profit:.2f}%")
        print(f"   최대 손실: {max_loss:.2f}%")
        print(f"   평균 보유시간: {df['hold_time_hours'].mean():.1f}시간")
        
    def analyze_by_coin(self):
        """코인별 분석"""
        print("\n" + "="*60)
        print("💰 코인별 성과")
        print("="*60)
        
        coin_stats = []
        
        for symbol in self.trades_df['symbol'].unique():
            coin_df = self.trades_df[self.trades_df['symbol'] == symbol]
            
            total = len(coin_df)
            wins = len(coin_df[coin_df['pnl'] > 0])
            win_rate = wins / total * 100 if total > 0 else 0
            
            total_pnl = coin_df['pnl'].sum()
            avg_pnl_rate = coin_df['pnl_rate'].mean() * 100
            
            coin_stats.append({
                'symbol': symbol,
                'trades': total,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl_rate': avg_pnl_rate
            })
        
        coin_df = pd.DataFrame(coin_stats).sort_values('total_pnl', ascending=False)
        
        print("\n{:<8} {:>6} {:>10} {:>12} {:>12}".format(
            "코인", "거래수", "승률(%)", "총손익(원)", "평균(%)"
        ))
        print("-" * 60)
        
        for _, row in coin_df.iterrows():
            print("{:<8} {:>6} {:>10.1f} {:>12,.0f} {:>12.2f}".format(
                row['symbol'],
                row['trades'],
                row['win_rate'],
                row['total_pnl'],
                row['avg_pnl_rate']
            ))
    
    def analyze_by_hold_time(self):
        """보유 시간별 분석"""
        print("\n" + "="*60)
        print("⏰ 보유 시간별 성과")
        print("="*60)
        
        df = self.trades_df.copy()
        
        # 보유 시간 구간 분류
        bins = [0, 1, 3, 6, 12, 24, 48, float('inf')]
        labels = ['<1h', '1-3h', '3-6h', '6-12h', '12-24h', '24-48h', '48h+']
        df['hold_time_range'] = pd.cut(df['hold_time_hours'], bins=bins, labels=labels)
        
        time_stats = df.groupby('hold_time_range').agg({
            'pnl': ['count', lambda x: (x > 0).sum(), 'sum'],
            'pnl_rate': 'mean'
        })
        
        time_stats.columns = ['거래수', '승리', '총손익', '평균수익률']
        time_stats['승률(%)'] = (time_stats['승리'] / time_stats['거래수'] * 100).round(1)
        time_stats['평균수익률'] = (time_stats['평균수익률'] * 100).round(2)
        
        print(time_stats.to_string())
        
    def analyze_profit_loss_distribution(self):
        """손익 분포 분석"""
        print("\n" + "="*60)
        print("📉 손익 분포 분석")
        print("="*60)
        
        df = self.trades_df.copy()
        df['pnl_pct'] = df['pnl_rate'] * 100
        
        # 손익 구간별 분류
        bins = [-100, -5, -3, -2, -1, 0, 1, 2, 3, 5, 100]
        labels = ['<-5%', '-5~-3%', '-3~-2%', '-2~-1%', '-1~0%', 
                  '0~1%', '1~2%', '2~3%', '3~5%', '>5%']
        df['pnl_range'] = pd.cut(df['pnl_pct'], bins=bins, labels=labels)
        
        dist = df['pnl_range'].value_counts().sort_index()
        
        print("\n손익 구간별 거래 수:")
        for idx, count in dist.items():
            pct = count / len(df) * 100
            bar = '█' * int(pct / 2)
            print(f"{idx:>8}: {count:>3}회 ({pct:>5.1f}%) {bar}")
    
    def find_optimal_stop_loss(self):
        """최적 손절 포인트 찾기"""
        print("\n" + "="*60)
        print("🎯 최적 손절 포인트 분석")
        print("="*60)
        
        df = self.trades_df.copy()
        
        # 다양한 손절 포인트 시뮬레이션
        stop_loss_points = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]
        
        results = []
        
        for sl in stop_loss_points:
            # 손절 적용 시뮬레이션
            simulated_pnl = df['pnl_rate'].apply(
                lambda x: max(x, -sl)  # 손절 포인트 이하로 떨어지지 않음
            )
            
            total_pnl = simulated_pnl.sum()
            wins = (simulated_pnl > 0).sum()
            win_rate = wins / len(df) * 100
            avg_pnl = simulated_pnl.mean() * 100
            
            results.append({
                'stop_loss': sl * 100,
                'total_pnl': total_pnl * 100,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl
            })
        
        results_df = pd.DataFrame(results)
        
        print("\n손절(%) | 총수익률(%) | 승률(%) | 평균수익률(%)")
        print("-" * 60)
        for _, row in results_df.iterrows():
            print(f"{row['stop_loss']:>6.1f} | {row['total_pnl']:>11.2f} | {row['win_rate']:>7.1f} | {row['avg_pnl']:>13.2f}")
        
        # 최적 손절 포인트
        best_sl = results_df.loc[results_df['total_pnl'].idxmax()]
        print(f"\n✅ 최적 손절: {best_sl['stop_loss']:.1f}%")
        print(f"   (총수익률: {best_sl['total_pnl']:.2f}%, 승률: {best_sl['win_rate']:.1f}%)")
        
        return best_sl['stop_loss'] / 100
    
    def find_optimal_take_profit(self):
        """최적 익절 포인트 찾기"""
        print("\n" + "="*60)
        print("🎯 최적 익절 포인트 분석")
        print("="*60)
        
        df = self.trades_df.copy()
        
        # 다양한 익절 포인트 시뮬레이션
        take_profit_points = [0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05]
        
        results = []
        
        for tp in take_profit_points:
            # 익절 적용 시뮬레이션
            simulated_pnl = df['pnl_rate'].apply(
                lambda x: min(x, tp) if x > 0 else x  # 수익은 익절 포인트까지만
            )
            
            total_pnl = simulated_pnl.sum()
            wins = (simulated_pnl > 0).sum()
            win_rate = wins / len(df) * 100
            avg_pnl = simulated_pnl.mean() * 100
            
            results.append({
                'take_profit': tp * 100,
                'total_pnl': total_pnl * 100,
                'win_rate': win_rate,
                'avg_pnl': avg_pnl
            })
        
        results_df = pd.DataFrame(results)
        
        print("\n익절(%) | 총수익률(%) | 승률(%) | 평균수익률(%)")
        print("-" * 60)
        for _, row in results_df.iterrows():
            print(f"{row['take_profit']:>6.1f} | {row['total_pnl']:>11.2f} | {row['win_rate']:>7.1f} | {row['avg_pnl']:>13.2f}")
        
        # 최적 익절 포인트
        best_tp = results_df.loc[results_df['total_pnl'].idxmax()]
        print(f"\n✅ 최적 익절: {best_tp['take_profit']:.1f}%")
        print(f"   (총수익률: {best_tp['total_pnl']:.2f}%, 승률: {best_tp['win_rate']:.1f}%)")
        
        return best_tp['take_profit'] / 100
    
    def optimize_combined_params(self):
        """손절/익절 조합 최적화"""
        print("\n" + "="*60)
        print("🔍 손절/익절 조합 최적화")
        print("="*60)
        
        df = self.trades_df.copy()
        
        stop_losses = [0.01, 0.015, 0.02, 0.025, 0.03]
        take_profits = [0.015, 0.02, 0.025, 0.03, 0.035, 0.04]
        
        best_result = None
        best_score = float('-inf')
        all_results = []
        
        print("\n조합 테스트 중...")
        
        for sl in stop_losses:
            for tp in take_profits:
                # 손익비 체크 (최소 1:1.5)
                if tp < sl * 1.5:
                    continue
                
                # 시뮬레이션
                simulated_pnl = df['pnl_rate'].apply(
                    lambda x: min(max(x, -sl), tp)
                )
                
                total_pnl = simulated_pnl.sum()
                wins = (simulated_pnl > 0).sum()
                losses = (simulated_pnl <= 0).sum()
                win_rate = wins / len(df) * 100 if len(df) > 0 else 0
                avg_pnl = simulated_pnl.mean() * 100
                
                # 점수 계산: 승률 40% + 평균수익 40% + 총수익 20%
                score = win_rate * 0.4 + avg_pnl * 0.4 + total_pnl * 100 * 0.2
                
                result = {
                    'stop_loss': sl * 100,
                    'take_profit': tp * 100,
                    'ratio': tp / sl,
                    'total_pnl': total_pnl * 100,
                    'win_rate': win_rate,
                    'avg_pnl': avg_pnl,
                    'wins': wins,
                    'losses': losses,
                    'score': score
                }
                
                all_results.append(result)
                
                if score > best_score:
                    best_score = score
                    best_result = result
        
        # 상위 5개 결과
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        print("\n" + "="*60)
        print("🏆 최적 조합 TOP 5")
        print("="*60)
        
        for i, result in enumerate(all_results[:5], 1):
            print(f"\n[{i}위] 점수: {result['score']:.2f}")
            print(f"   손절: {result['stop_loss']:.1f}%")
            print(f"   익절: {result['take_profit']:.1f}%")
            print(f"   손익비: 1:{result['ratio']:.1f}")
            print(f"   총 수익률: {result['total_pnl']:.2f}%")
            print(f"   승률: {result['win_rate']:.1f}%")
            print(f"   평균 수익률: {result['avg_pnl']:.2f}%")
            print(f"   승/패: {result['wins']}/{result['losses']}")
        
        return all_results[:5]
    
    def analyze_market_conditions(self):
        """시장 상황별 분석 (업비트 시세 기반)"""
        print("\n" + "="*60)
        print("🌍 시장 상황별 성과 분석")
        print("="*60)
        
        # 각 거래 시점의 비트코인 추세 확인
        print("\n⏳ 거래 시점의 시장 데이터 수집 중...")
        
        market_conditions = []
        
        for idx, trade in self.trades_df.iterrows():
            timestamp = trade['timestamp']
            
            # 해당 시점의 BTC 데이터 (대략적인 시장 상황 파악)
            try:
                # 거래 시점 기준 최근 24시간 데이터
                btc_data = pyupbit.get_ohlcv("KRW-BTC", interval="minute60", count=24, 
                                             to=timestamp.strftime('%Y-%m-%d %H:%M:%S'))
                
                if btc_data is not None and len(btc_data) > 0:
                    # 추세 판단
                    price_change = (btc_data['close'].iloc[-1] - btc_data['close'].iloc[0]) / btc_data['close'].iloc[0]
                    
                    if price_change > 0.02:
                        condition = 'bullish'
                    elif price_change < -0.02:
                        condition = 'bearish'
                    else:
                        condition = 'neutral'
                    
                    market_conditions.append(condition)
                else:
                    market_conditions.append('unknown')
            except:
                market_conditions.append('unknown')
        
        self.trades_df['market_condition'] = market_conditions
        
        # 시장 상황별 통계
        market_stats = self.trades_df.groupby('market_condition').agg({
            'pnl': ['count', lambda x: (x > 0).sum(), 'sum'],
            'pnl_rate': 'mean'
        })
        
        market_stats.columns = ['거래수', '승리', '총손익', '평균수익률']
        market_stats['승률(%)'] = (market_stats['승리'] / market_stats['거래수'] * 100).round(1)
        market_stats['평균수익률(%)'] = (market_stats['평균수익률'] * 100).round(2)
        
        print("\n시장 상황별 성과:")
        print(market_stats.to_string())
        
    def generate_config(self, optimal_results: List[Dict]):
        """최적 설정 파일 생성"""
        best = optimal_results[0]
        
        # 시장 상황별 조정값 제안
        # 약세장에서는 더 보수적으로 (진입 기준 높임)
        # 강세장에서는 공격적으로 (진입 기준 낮춤)
        
        config_template = f'''"""
자동 생성된 최적 설정값
생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
분석 기간: {self.trades_df['timestamp'].min().strftime('%Y-%m-%d')} ~ {self.trades_df['timestamp'].max().strftime('%Y-%m-%d')}
총 거래 수: {len(self.trades_df)}회
"""

# =============================================================================
# 진입/청산 설정
# =============================================================================

# 진입 점수 기준 (추천: 7.0 ~ 8.0)
ENTRY_SCORE_THRESHOLD = 7.5

# 손절/익절 설정
STOP_LOSS = {best['stop_loss']/100:.3f}  # {best['stop_loss']:.1f}%
MIN_PROFIT_TARGET = {best['take_profit']/100:.3f}  # {best['take_profit']:.1f}%

# 손익비
PROFIT_TARGET_RATIO = {best['ratio']:.1f}  # 1:{best['ratio']:.1f}

# =============================================================================
# 시장 상황별 조정값
# =============================================================================

MARKET_ADJUSTMENTS = {{
    'bullish': -1.5,    # 강세장: 진입 기준 완화
    'neutral': 0.0,     # 중립: 기본값 사용
    'bearish': +2.0     # 약세장: 진입 기준 강화
}}

# =============================================================================
# 리스크 관리
# =============================================================================

# 추적 손절 설정
TRAILING_STOP = {{
    'activation_profit': 0.02,  # 2% 수익 시 추적 손절 활성화
    'trailing_percent': 0.01    # 최고점 대비 1% 하락 시 청산
}}

# 물타기 설정 (비활성화 권장)
PYRAMIDING_CONFIG = {{
    'enabled': False,  # 현재 성과가 좋지 않으므로 비활성화
    'max_pyramids': 2,
    'min_profit_for_pyramid': 0.03
}}

# =============================================================================
# 분석 결과 요약
# =============================================================================

# 백테스트 결과 (시뮬레이션):
# - 예상 총 수익률: {best['total_pnl']:.2f}%
# - 예상 승률: {best['win_rate']:.1f}%
# - 예상 평균 수익률: {best['avg_pnl']:.2f}%
# - 예상 승/패: {best['wins']}/{best['losses']}

# =============================================================================
# 추가 권장사항
# =============================================================================

# 1. 진입 조건 강화
#    - 현재 4.5점 → 7.5점으로 상향
#    - RSI 과매수/과매도 구간에서만 진입
#
# 2. 거래 빈도 제한
#    - 일 최대 10회 이내로 제한
#    - 코인당 동시 포지션 1개로 제한
#
# 3. 수수료 고려
#    - 업비트 수수료 0.05% * 2 = 0.1%
#    - 최소 익절 목표는 0.3% 이상 권장
#
# 4. 리스크 관리
#    - 전체 자산의 30% 이상 한 코인에 투자 금지
#    - 일 손실 한도: 5%
#    - 연속 3회 손실 시 거래 중지 및 전략 재검토
'''
        
        output_path = '/home/claude/optimized_config.py'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(config_template)
        
        print(f"\n✅ 최적 설정 파일 생성: {output_path}")
        return output_path


def main():
    print("="*60)
    print("🤖 Trade History Analyzer")
    print("="*60)
    
    # JSON 파일 경로
    history_file = "trade_history.json"
    
    analyzer = TradeHistoryAnalyzer(history_file)
    
    # 1. 데이터 로드
    if not analyzer.load_data():
        return
    
    # 2. 기본 통계
    analyzer.basic_statistics()
    
    # 3. 코인별 분석
    analyzer.analyze_by_coin()
    
    # 4. 보유 시간별 분석
    analyzer.analyze_by_hold_time()
    
    # 5. 손익 분포
    analyzer.analyze_profit_loss_distribution()
    
    # 6. 최적 손절 포인트
    optimal_sl = analyzer.find_optimal_stop_loss()
    
    # 7. 최적 익절 포인트
    optimal_tp = analyzer.find_optimal_take_profit()
    
    # 8. 조합 최적화
    top_results = analyzer.optimize_combined_params()
    
    # 9. 시장 상황별 분석 (선택)
    proceed = input("\n\n시장 상황별 분석을 진행할까요? (시간이 걸릴 수 있습니다) (y/n): ").strip().lower()
    if proceed == 'y':
        analyzer.analyze_market_conditions()
    
    # 10. 설정 파일 생성
    generate = input("\n최적 설정으로 config 파일을 생성할까요? (y/n): ").strip().lower()
    if generate == 'y':
        config_path = analyzer.generate_config(top_results)
        print(f"\n📁 생성된 파일을 확인하세요: {config_path}")
    
    print("\n" + "="*60)
    print("✅ 분석 완료!")
    print("="*60)
    print("\n💡 다음 단계:")
    print("   1. optimized_config.py 파일 확인")
    print("   2. config.py에 추천 설정값 적용")
    print("   3. 실전 투입 전 페이퍼 트레이딩으로 재테스트")
    print("="*60)


if __name__ == "__main__":
    main()