"""
Entry Score Analyzer
trading.log에서 진입 점수를 추출하고 통계를 분석합니다.
"""

import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd


class EntryScoreAnalyzer:
    def __init__(self, log_file="trading.log", history_file="trade_history.json"):
        self.log_file = log_file
        self.history_file = history_file
        self.entry_scores = []
        self.trade_history = []
        
    def parse_log_for_scores(self):
        """로그 파일에서 진입 점수 추출"""
        print("📄 로그 파일에서 진입 점수 추출 중...")
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_analysis = {}
        
        for i, line in enumerate(lines):
            try:
                # 타임스탬프 추출
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if timestamp_match:
                    timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                
                # 코인 종합 분석 시작
                if "종합 분석" in line:
                    symbol_match = re.search(r'📊 ([A-Z]+) 종합 분석', line)
                    if symbol_match:
                        current_analysis = {
                            'timestamp': timestamp,
                            'symbol': symbol_match.group(1)
                        }
                
                # 최종 점수 추출
                if "최종 점수:" in line and current_analysis:
                    score_match = re.search(r'최종 점수:\s*([0-9.]+)/10', line)
                    if score_match:
                        current_analysis['score'] = float(score_match.group(1))
                
                # 진입 기준 추출
                if "진입 기준:" in line and current_analysis:
                    threshold_match = re.search(r'진입 기준:\s*([0-9.]+)\s*\(시장:\s*(\w+)\)', line)
                    if threshold_match:
                        current_analysis['threshold'] = float(threshold_match.group(1))
                        current_analysis['market'] = threshold_match.group(2)
                
                # 매수 체결 확인 (다음 몇 줄 내에)
                if "매수" in line and "체결" in line and current_analysis.get('score'):
                    # 현재 분석이 매수로 이어진 경우
                    buy_symbol_match = re.search(r'([A-Z]+)', line)
                    if buy_symbol_match and buy_symbol_match.group(1) == current_analysis.get('symbol'):
                        current_analysis['action'] = 'buy'
                        self.entry_scores.append(current_analysis.copy())
                        current_analysis = {}
                
                # 진입 조건 미충족
                if "진입 조건 미충족" in line and current_analysis.get('score'):
                    current_analysis['action'] = 'skip'
                    self.entry_scores.append(current_analysis.copy())
                    current_analysis = {}
                    
            except Exception as e:
                continue
        
        print(f"✅ 총 {len(self.entry_scores)}개 분석 로그 추출 완료")
        
        # 실제 매수만 필터링
        buy_scores = [x for x in self.entry_scores if x.get('action') == 'buy']
        print(f"   실제 매수: {len(buy_scores)}개")
        
        return self.entry_scores
    
    def load_trade_history(self):
        """거래 기록 로드"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                self.trade_history = json.load(f)
            print(f"✅ 거래 기록 {len(self.trade_history)}개 로드 완료")
            return True
        except Exception as e:
            print(f"⚠️  거래 기록 로드 실패: {e}")
            return False
    
    def match_scores_with_trades(self):
        """진입 점수와 거래 결과 매칭"""
        print("\n📊 진입 점수와 거래 결과 매칭 중...")
        
        buy_scores = [x for x in self.entry_scores if x.get('action') == 'buy']
        
        matched = []
        
        for trade in self.trade_history:
            trade_time = datetime.fromisoformat(trade['timestamp'])
            trade_symbol = trade['symbol']
            
            # 거래 시간 기준 ±5분 이내의 매수 점수 찾기
            for score_data in buy_scores:
                if score_data['symbol'] == trade_symbol:
                    time_diff = abs((trade_time - score_data['timestamp']).total_seconds())
                    
                    # 5분(300초) 이내
                    if time_diff < 300:
                        matched.append({
                            'timestamp': trade['timestamp'],
                            'symbol': trade_symbol,
                            'entry_score': score_data['score'],
                            'threshold': score_data['threshold'],
                            'market': score_data['market'],
                            'pnl': trade['pnl'],
                            'pnl_rate': trade['pnl_rate'],
                            'hold_time': trade['hold_time_hours']
                        })
                        break
        
        print(f"✅ {len(matched)}개 거래와 점수 매칭 완료")
        return matched
    
    def analyze_all_scores(self):
        """모든 점수 분석 (매수 여부 무관)"""
        print("\n" + "="*60)
        print("📊 전체 점수 분석 (매수 시도 여부 무관)")
        print("="*60)
        
        if not self.entry_scores:
            print("⚠️  분석할 데이터가 없습니다.")
            return
        
        df = pd.DataFrame(self.entry_scores)
        
        print(f"\n총 분석 횟수: {len(df)}회")
        
        # 매수 vs 스킵
        buy_count = len(df[df['action'] == 'buy'])
        skip_count = len(df[df['action'] == 'skip'])
        
        print(f"   매수 진입: {buy_count}회 ({buy_count/len(df)*100:.1f}%)")
        print(f"   진입 스킵: {skip_count}회 ({skip_count/len(df)*100:.1f}%)")
        
        # 전체 점수 통계
        print(f"\n📈 전체 점수 통계:")
        print(f"   평균: {df['score'].mean():.2f}점")
        print(f"   최소: {df['score'].min():.2f}점")
        print(f"   최대: {df['score'].max():.2f}점")
        print(f"   중앙값: {df['score'].median():.2f}점")
        print(f"   표준편차: {df['score'].std():.2f}")
        
        # 매수된 것들의 점수
        buy_df = df[df['action'] == 'buy']
        if len(buy_df) > 0:
            print(f"\n🎯 실제 매수 진입 점수:")
            print(f"   평균: {buy_df['score'].mean():.2f}점")
            print(f"   최소: {buy_df['score'].min():.2f}점")
            print(f"   최대: {buy_df['score'].max():.2f}점")
            print(f"   중앙값: {buy_df['score'].median():.2f}점")
        
        # 점수 구간별 분포
        print(f"\n📊 점수 구간별 분포:")
        bins = [0, 3, 4, 5, 6, 7, 8, 9, 10]
        df['score_range'] = pd.cut(df['score'], bins=bins)
        
        dist = df['score_range'].value_counts().sort_index()
        
        for idx, count in dist.items():
            pct = count / len(df) * 100
            bar = '█' * int(pct / 2)
            
            # 해당 구간의 매수 비율
            range_df = df[df['score_range'] == idx]
            buy_rate = len(range_df[range_df['action'] == 'buy']) / len(range_df) * 100 if len(range_df) > 0 else 0
            
            print(f"{str(idx):>12}: {count:>3}회 ({pct:>5.1f}%) {bar} | 매수율: {buy_rate:.0f}%")
        
        # 시장 상황별 점수
        if 'market' in df.columns:
            print(f"\n🌍 시장 상황별 점수:")
            market_stats = df.groupby('market')['score'].agg(['count', 'mean', 'min', 'max'])
            print(market_stats.to_string())
    
    def analyze_matched_scores(self, matched_data):
        """매칭된 점수와 거래 결과 분석"""
        print("\n" + "="*60)
        print("💰 진입 점수별 수익성 분석")
        print("="*60)
        
        if not matched_data:
            print("⚠️  매칭된 데이터가 없습니다.")
            return
        
        df = pd.DataFrame(matched_data)
        
        # 승/패 구분
        df['result'] = df['pnl_rate'].apply(lambda x: 'win' if x > 0 else 'loss')
        
        print(f"\n총 {len(df)}개 거래 분석")
        print(f"   승리: {len(df[df['result']=='win'])}회")
        print(f"   패배: {len(df[df['result']=='loss'])}회")
        print(f"   승률: {len(df[df['result']=='win'])/len(df)*100:.1f}%")
        
        # 진입 점수 통계
        print(f"\n📈 진입 점수 통계:")
        print(f"   평균: {df['entry_score'].mean():.2f}점")
        print(f"   최소: {df['entry_score'].min():.2f}점")
        print(f"   최대: {df['entry_score'].max():.2f}점")
        
        # 승리한 거래의 점수
        win_df = df[df['result'] == 'win']
        loss_df = df[df['result'] == 'loss']
        
        if len(win_df) > 0:
            print(f"\n✅ 수익 거래의 진입 점수:")
            print(f"   평균: {win_df['entry_score'].mean():.2f}점")
            print(f"   최소: {win_df['entry_score'].min():.2f}점")
            print(f"   최대: {win_df['entry_score'].max():.2f}점")
        
        if len(loss_df) > 0:
            print(f"\n❌ 손실 거래의 진입 점수:")
            print(f"   평균: {loss_df['entry_score'].mean():.2f}점")
            print(f"   최소: {loss_df['entry_score'].min():.2f}점")
            print(f"   최대: {loss_df['entry_score'].max():.2f}점")
        
        # 점수 구간별 승률
        print(f"\n📊 점수 구간별 승률:")
        bins = [0, 4, 5, 6, 7, 8, 10]
        labels = ['0-4', '4-5', '5-6', '6-7', '7-8', '8-10']
        df['score_range'] = pd.cut(df['entry_score'], bins=bins, labels=labels)
        
        score_analysis = df.groupby('score_range').agg({
            'result': ['count', lambda x: (x == 'win').sum()],
            'pnl_rate': 'mean'
        })
        
        score_analysis.columns = ['거래수', '승리', '평균수익률']
        score_analysis['승률(%)'] = (score_analysis['승리'] / score_analysis['거래수'] * 100).round(1)
        score_analysis['평균수익률(%)'] = (score_analysis['평균수익률'] * 100).round(2)
        
        print(score_analysis.to_string())
        
        # 최적 진입 점수 제안
        print(f"\n" + "="*60)
        print("💡 최적 진입 점수 제안")
        print("="*60)
        
        # 승률이 가장 높은 구간 찾기
        best_range = score_analysis['승률(%)'].idxmax()
        best_win_rate = score_analysis.loc[best_range, '승률(%)']
        
        print(f"\n✅ 승률이 가장 높은 구간: {best_range}점 (승률: {best_win_rate:.1f}%)")
        
        # 전체 거래의 중앙값
        median_score = df['entry_score'].median()
        print(f"📊 전체 거래의 중앙값: {median_score:.2f}점")
        
        # 상위 25% 점수
        q75_score = df['entry_score'].quantile(0.75)
        print(f"📈 상위 25% 점수: {q75_score:.2f}점")
        
        # 실질적 제안
        print(f"\n" + "-"*60)
        print("💡 권장 진입 점수:")
        print(f"   보수적: {q75_score:.1f}점 이상 (상위 25%)")
        print(f"   균형적: {median_score:.1f}점 이상 (중앙값)")
        print(f"   공격적: {df['entry_score'].quantile(0.25):.1f}점 이상 (하위 75%)")
        print("-"*60)
        
        return score_analysis
    
    def generate_recommendation(self, matched_data):
        """최종 권장사항 생성"""
        print("\n" + "="*60)
        print("📝 최종 권장 설정")
        print("="*60)
        
        if not matched_data:
            # 전체 점수만 기반으로 제안
            df = pd.DataFrame(self.entry_scores)
            buy_df = df[df['action'] == 'buy']
            
            if len(buy_df) > 0:
                avg_entry = buy_df['score'].mean()
                median_entry = buy_df['score'].median()
                
                print(f"\n과거 실제 진입 점수:")
                print(f"   평균: {avg_entry:.2f}점")
                print(f"   중앙값: {median_entry:.2f}점")
                
                print(f"\n💡 권장 진입 기준:")
                print(f"   현재 설정: 4.5점")
                print(f"   권장 설정: {median_entry:.1f}점")
            else:
                print("\n⚠️  매수 데이터가 없어 권장사항을 생성할 수 없습니다.")
        else:
            df = pd.DataFrame(matched_data)
            
            # 수익 거래의 평균 점수
            win_df = df[df['pnl_rate'] > 0]
            if len(win_df) > 0:
                win_avg = win_df['entry_score'].mean()
                win_median = win_df['entry_score'].median()
                
                print(f"\n✅ 수익 거래의 진입 점수:")
                print(f"   평균: {win_avg:.2f}점")
                print(f"   중앙값: {win_median:.2f}점")
                
                print(f"\n💡 권장 진입 기준:")
                print(f"   보수적: {win_median + 0.5:.1f}점 이상")
                print(f"   균형적: {win_median:.1f}점 이상")
                print(f"   공격적: {win_median - 0.5:.1f}점 이상")


def main():
    print("="*60)
    print("🎯 Entry Score Analyzer")
    print("="*60)
    
    analyzer = EntryScoreAnalyzer()
    
    # 1. 로그에서 점수 추출
    analyzer.parse_log_for_scores()
    
    # 2. 전체 점수 분석
    analyzer.analyze_all_scores()
    
    # 3. 거래 기록 로드
    if analyzer.load_trade_history():
        # 4. 점수와 거래 결과 매칭
        matched = analyzer.match_scores_with_trades()
        
        if matched:
            # 5. 매칭된 데이터 분석
            analyzer.analyze_matched_scores(matched)
            
            # 6. 최종 권장사항
            analyzer.generate_recommendation(matched)
        else:
            print("\n⚠️  점수와 거래 결과를 매칭할 수 없습니다.")
            analyzer.generate_recommendation(None)
    else:
        analyzer.generate_recommendation(None)
    
    print("\n" + "="*60)
    print("✅ 분석 완료!")
    print("="*60)


if __name__ == "__main__":
    main()