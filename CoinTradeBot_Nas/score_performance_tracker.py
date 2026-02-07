# score_performance_tracker.py - 진입 점수별 성과 추적 시스템

import json
import logging
from datetime import datetime
from collections import defaultdict
import os

logger = logging.getLogger(__name__)

class ScorePerformanceTracker:
    """
    진입 점수별 성과 추적
    - 점수 구간별 승률, 평균 수익률 기록
    - 최적 진입 점수 추천
    - 데이터 기반 설정 개선
    """

    def __init__(self, file_path='score_performance.json'):
        self.file_path = file_path

        # 데이터 구조
        self.score_data = defaultdict(lambda: {
            'trades': [],           # 거래 목록
            'total_count': 0,       # 총 거래 수
            'wins': 0,              # 승리 횟수
            'losses': 0,            # 손실 횟수
            'total_pnl': 0.0,       # 총 손익
            'win_rate': 0.0,        # 승률
            'avg_pnl_rate': 0.0,    # 평균 수익률
            'avg_win': 0.0,         # 평균 수익
            'avg_loss': 0.0,        # 평균 손실
            'profit_factor': 0.0    # 손익비
        })

        # 점수 구간 설정 (0.5점 단위)
        self.score_ranges = [
            (3.0, 3.5), (3.5, 4.0), (4.0, 4.5), (4.5, 5.0),
            (5.0, 5.5), (5.5, 6.0), (6.0, 6.5), (6.5, 7.0),
            (7.0, 7.5), (7.5, 8.0), (8.0, 8.5), (8.5, 9.0),
            (9.0, 9.5), (9.5, 10.0)
        ]

        # 파일 로드
        self.load_data()

        logger.info("✅ ScorePerformanceTracker 초기화 완료")

    def get_score_range(self, score):
        """점수를 구간으로 변환 (예: 6.3 → "6.0-6.5")"""
        for low, high in self.score_ranges:
            if low <= score < high:
                return f"{low:.1f}-{high:.1f}"

        # 범위 밖
        if score < 3.0:
            return "3.0미만"
        else:
            return "10.0이상"

    def record_trade(self, entry_score, pnl, pnl_rate, symbol, entry_price, exit_price):
        """
        거래 기록

        Args:
            entry_score: 진입 점수 (예: 6.5)
            pnl: 손익 금액
            pnl_rate: 손익률 (예: 0.025 = 2.5%)
            symbol: 심볼
            entry_price: 진입가
            exit_price: 청산가
        """
        score_range = self.get_score_range(entry_score)

        trade_data = {
            'timestamp': datetime.now().isoformat(),
            'entry_score': entry_score,
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'pnl_rate': pnl_rate,
            'result': 'win' if pnl > 0 else 'loss'
        }

        # 거래 추가
        self.score_data[score_range]['trades'].append(trade_data)
        self.score_data[score_range]['total_count'] += 1
        self.score_data[score_range]['total_pnl'] += pnl

        if pnl > 0:
            self.score_data[score_range]['wins'] += 1
        else:
            self.score_data[score_range]['losses'] += 1

        # 통계 재계산
        self._recalculate_stats(score_range)

        # 주기적 저장 (10건마다)
        if self.score_data[score_range]['total_count'] % 10 == 0:
            self.save_data()

        logger.info(f"📊 점수별 기록: {score_range} → {trade_data['result']} ({pnl_rate:+.2%})")

    def _recalculate_stats(self, score_range):
        """특정 점수 구간의 통계 재계산"""
        data = self.score_data[score_range]

        if data['total_count'] == 0:
            return

        # 승률
        data['win_rate'] = data['wins'] / data['total_count']

        # 평균 수익률
        data['avg_pnl_rate'] = sum(t['pnl_rate'] for t in data['trades']) / data['total_count']

        # 평균 수익/손실
        wins = [t['pnl_rate'] for t in data['trades'] if t['pnl'] > 0]
        losses = [t['pnl_rate'] for t in data['trades'] if t['pnl'] <= 0]

        data['avg_win'] = sum(wins) / len(wins) if wins else 0
        data['avg_loss'] = sum(losses) / len(losses) if losses else 0

        # 손익비 (Profit Factor)
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0

        data['profit_factor'] = (total_wins / total_losses) if total_losses > 0 else 0

    def get_statistics(self):
        """전체 통계 조회"""
        stats = []

        for score_range in sorted(self.score_data.keys()):
            data = self.score_data[score_range]

            if data['total_count'] > 0:
                stats.append({
                    'score_range': score_range,
                    'trades': data['total_count'],
                    'win_rate': data['win_rate'],
                    'avg_pnl_rate': data['avg_pnl_rate'],
                    'avg_win': data['avg_win'],
                    'avg_loss': data['avg_loss'],
                    'profit_factor': data['profit_factor']
                })

        return stats

    def get_best_score_range(self, min_trades=10):
        """
        최적 점수 구간 추천

        Args:
            min_trades: 최소 거래 수 (신뢰도)

        Returns:
            (best_range, win_rate, avg_pnl_rate)
        """
        best_range = None
        best_score = -999

        for score_range, data in self.score_data.items():
            if data['total_count'] < min_trades:
                continue

            # 점수 = 승률 * 0.6 + 평균수익률 * 0.4
            combined_score = data['win_rate'] * 0.6 + data['avg_pnl_rate'] * 0.4

            if combined_score > best_score:
                best_score = combined_score
                best_range = (score_range, data['win_rate'], data['avg_pnl_rate'])

        return best_range

    def recommend_entry_threshold(self, min_trades=10, target_win_rate=0.50):
        """
        추천 진입 점수

        Args:
            min_trades: 최소 거래 수
            target_win_rate: 목표 승률

        Returns:
            recommended_score (float or None)
        """
        # 승률 >= 목표 승률인 구간 찾기
        candidates = []

        for score_range, data in self.score_data.items():
            if data['total_count'] < min_trades:
                continue

            if data['win_rate'] >= target_win_rate:
                # 점수 구간의 중간값
                if score_range == "3.0미만":
                    mid_score = 2.5
                elif score_range == "10.0이상":
                    mid_score = 10.5
                else:
                    low, high = map(float, score_range.split('-'))
                    mid_score = (low + high) / 2

                candidates.append((mid_score, data['win_rate'], data['avg_pnl_rate']))

        if not candidates:
            return None

        # 승률이 높으면서 점수가 낮은 것 선택 (빈도 확보)
        candidates.sort(key=lambda x: (-x[1], x[0]))  # 승률 내림차순, 점수 오름차순

        return candidates[0][0]

    def print_report(self, min_trades=5):
        """상세 리포트 출력"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 진입 점수별 성과 분석")
        logger.info("=" * 80)

        stats = self.get_statistics()

        if not stats:
            logger.info("⚠️ 데이터 없음 (거래 기록을 쌓아주세요)")
            logger.info("=" * 80)
            return

        # 헤더
        logger.info(f"{'점수 구간':^12} | {'거래수':^6} | {'승률':^7} | {'평균수익':^9} | {'평수익':^9} | {'평손실':^9} | {'손익비':^7}")
        logger.info("-" * 80)

        # 데이터 출력
        for stat in stats:
            if stat['trades'] < min_trades:
                continue  # 샘플 수 부족

            logger.info(
                f"{stat['score_range']:^12} | "
                f"{stat['trades']:>6} | "
                f"{stat['win_rate']:>6.1%} | "
                f"{stat['avg_pnl_rate']:>+8.2%} | "
                f"{stat['avg_win']:>+8.2%} | "
                f"{stat['avg_loss']:>+8.2%} | "
                f"{stat['profit_factor']:>6.2f}"
            )

        logger.info("=" * 80)

        # 최적 구간 추천
        best = self.get_best_score_range(min_trades)
        if best:
            score_range, win_rate, avg_pnl = best
            logger.info(f"🎯 최적 점수 구간: {score_range}")
            logger.info(f"   승률: {win_rate:.1%} | 평균 수익: {avg_pnl:+.2%}")

        # 추천 진입 점수
        recommended = self.recommend_entry_threshold(min_trades)
        if recommended:
            logger.info(f"💡 추천 진입 점수: {recommended:.1f}점 이상")

        logger.info("=" * 80)
        logger.info("")

    def save_data(self):
        """데이터 저장"""
        try:
            # defaultdict를 일반 dict로 변환
            save_data = {
                'last_updated': datetime.now().isoformat(),
                'score_data': dict(self.score_data)
            }

            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"✅ 점수별 성과 저장: {self.file_path}")

        except Exception as e:
            logger.error(f"점수별 성과 저장 실패: {e}")

    def load_data(self):
        """데이터 로드"""
        if not os.path.exists(self.file_path):
            logger.info(f"📝 새 파일 생성: {self.file_path}")
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)

            # 데이터 복원
            if 'score_data' in loaded:
                for score_range, data in loaded['score_data'].items():
                    self.score_data[score_range] = data

            logger.info(f"✅ 점수별 성과 로드: {len(self.score_data)}개 구간")

        except Exception as e:
            logger.error(f"점수별 성과 로드 실패: {e}")

    def get_score_range_detail(self, score_range):
        """특정 점수 구간의 상세 정보"""
        if score_range not in self.score_data:
            return None

        data = self.score_data[score_range]

        return {
            'score_range': score_range,
            'total_trades': data['total_count'],
            'wins': data['wins'],
            'losses': data['losses'],
            'win_rate': data['win_rate'],
            'avg_pnl_rate': data['avg_pnl_rate'],
            'avg_win': data['avg_win'],
            'avg_loss': data['avg_loss'],
            'profit_factor': data['profit_factor'],
            'recent_trades': data['trades'][-10:]  # 최근 10건
        }

    def export_csv(self, output_path='score_performance.csv'):
        """CSV로 내보내기"""
        import csv

        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 헤더
                writer.writerow([
                    '점수구간', '거래수', '승리', '손실', '승률',
                    '평균수익률', '평균수익', '평균손실', '손익비'
                ])

                # 데이터
                for score_range in sorted(self.score_data.keys()):
                    data = self.score_data[score_range]

                    if data['total_count'] == 0:
                        continue

                    writer.writerow([
                        score_range,
                        data['total_count'],
                        data['wins'],
                        data['losses'],
                        f"{data['win_rate']:.2%}",
                        f"{data['avg_pnl_rate']:+.2%}",
                        f"{data['avg_win']:+.2%}",
                        f"{data['avg_loss']:+.2%}",
                        f"{data['profit_factor']:.2f}"
                    ])

            logger.info(f"✅ CSV 내보내기 완료: {output_path}")
            return True

        except Exception as e:
            logger.error(f"CSV 내보내기 실패: {e}")
            return False
