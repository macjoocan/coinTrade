# auto_optimizer.py - 봇 시작 시 자동 설정 최적화

import logging
from score_performance_tracker import ScorePerformanceTracker
from config import STRATEGY_PRESETS, ACTIVE_PRESET, apply_preset

logger = logging.getLogger(__name__)

class AutoOptimizer:
    """
    봇 시작 시 자동 최적화
    - 과거 데이터 분석
    - 최적 진입 점수 추천
    - 자동 설정 조정 (선택적)
    """

    def __init__(self, score_tracker):
        self.score_tracker = score_tracker
        self.min_trades_for_optimization = 30  # 최소 30회 거래 필요
        self.target_win_rate = 0.50  # 목표 승률 50%
        self.min_daily_trades = 2    # 최소 하루 2회 거래

        logger.info("🤖 AutoOptimizer 초기화")

    def analyze_and_recommend(self):
        """
        데이터 분석 및 추천

        Returns:
            (should_optimize, recommendations)
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 자동 최적화 분석 시작")
        logger.info("=" * 80)

        # 1. 데이터 충분성 체크
        stats = self.score_tracker.get_statistics()
        total_trades = sum(s['trades'] for s in stats)

        if total_trades < self.min_trades_for_optimization:
            logger.info(f"⚠️ 데이터 부족: {total_trades}/{self.min_trades_for_optimization}회")
            logger.info(f"   → {self.min_trades_for_optimization - total_trades}회 더 거래 필요")
            logger.info(f"   → 기본 설정 유지")
            logger.info("=" * 80)
            logger.info("")
            return False, None

        logger.info(f"✅ 충분한 데이터: {total_trades}회 거래 분석")

        # 2. 현재 설정 확인
        current_preset = ACTIVE_PRESET
        current_threshold = STRATEGY_PRESETS[current_preset]['entry_score_threshold']

        logger.info(f"\n📊 현재 설정:")
        logger.info(f"   프리셋: {current_preset}")
        logger.info(f"   진입 점수: {current_threshold:.1f}점")

        # 3. 전체 성과 분석
        overall_stats = self._calculate_overall_stats(stats)

        logger.info(f"\n📈 전체 성과:")
        logger.info(f"   총 거래: {overall_stats['total_trades']}회")
        logger.info(f"   승률: {overall_stats['win_rate']:.1%}")
        logger.info(f"   평균 수익: {overall_stats['avg_pnl']:+.2%}")

        # 4. 최적 점수 구간 찾기
        best_range_info = self.score_tracker.get_best_score_range(min_trades=10)

        if not best_range_info:
            logger.info(f"\n⚠️ 최적 구간 없음 (각 구간별 거래 10회 미만)")
            logger.info(f"   → 기본 설정 유지")
            logger.info("=" * 80)
            logger.info("")
            return False, None

        best_range, best_win_rate, best_avg_pnl = best_range_info

        logger.info(f"\n🎯 최적 구간: {best_range}")
        logger.info(f"   승률: {best_win_rate:.1%}")
        logger.info(f"   평균 수익: {best_avg_pnl:+.2%}")

        # 5. 추천 진입 점수 계산
        recommended_score = self.score_tracker.recommend_entry_threshold(
            min_trades=10,
            target_win_rate=self.target_win_rate
        )

        if not recommended_score:
            logger.info(f"\n⚠️ 목표 승률 {self.target_win_rate:.0%} 달성 구간 없음")
            logger.info(f"   → 기본 설정 유지")
            logger.info("=" * 80)
            logger.info("")
            return False, None

        logger.info(f"\n💡 추천 진입 점수: {recommended_score:.1f}점")

        # 6. 변경 필요성 판단
        difference = abs(recommended_score - current_threshold)

        if difference < 0.3:  # 0.3점 미만 차이면 변경 불필요
            logger.info(f"\n✅ 현재 설정이 최적 (차이: {difference:.1f}점)")
            logger.info(f"   → 변경 불필요")
            logger.info("=" * 80)
            logger.info("")
            return False, None

        # 7. 추천 사항 생성
        recommendations = {
            'current_threshold': current_threshold,
            'recommended_threshold': recommended_score,
            'difference': recommended_score - current_threshold,
            'best_range': best_range,
            'best_win_rate': best_win_rate,
            'best_avg_pnl': best_avg_pnl,
            'overall_win_rate': overall_stats['win_rate'],
            'total_trades': total_trades
        }

        logger.info(f"\n🔧 변경 권장")
        logger.info(f"   현재: {current_threshold:.1f}점")
        logger.info(f"   추천: {recommended_score:.1f}점")
        logger.info(f"   변화: {recommendations['difference']:+.1f}점")

        # 8. 예상 효과
        self._show_expected_impact(recommendations, stats)

        logger.info("=" * 80)
        logger.info("")

        return True, recommendations

    def _calculate_overall_stats(self, stats):
        """전체 통계 계산"""
        if not stats:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_pnl': 0
            }

        total_trades = sum(s['trades'] for s in stats)
        total_wins = sum(s['trades'] * s['win_rate'] for s in stats)
        win_rate = total_wins / total_trades if total_trades > 0 else 0

        weighted_pnl = sum(s['trades'] * s['avg_pnl_rate'] for s in stats)
        avg_pnl = weighted_pnl / total_trades if total_trades > 0 else 0

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl
        }

    def _show_expected_impact(self, recommendations, stats):
        """예상 효과 표시"""
        logger.info(f"\n📊 예상 효과:")

        current_threshold = recommendations['current_threshold']
        recommended_threshold = recommendations['recommended_threshold']

        # 현재 설정의 성과
        current_stats = self._get_stats_around_threshold(stats, current_threshold)
        recommended_stats = self._get_stats_around_threshold(stats, recommended_threshold)

        if current_stats:
            logger.info(f"   현재 설정 ({current_threshold:.1f}점):")
            logger.info(f"      승률: {current_stats['win_rate']:.1%}")
            logger.info(f"      거래: ~{current_stats['trades']:.0f}회/주")

        if recommended_stats:
            logger.info(f"   추천 설정 ({recommended_threshold:.1f}점):")
            logger.info(f"      승률: {recommended_stats['win_rate']:.1%}")
            logger.info(f"      거래: ~{recommended_stats['trades']:.0f}회/주")

            if current_stats:
                win_rate_change = recommended_stats['win_rate'] - current_stats['win_rate']
                trade_change = recommended_stats['trades'] - current_stats['trades']

                logger.info(f"   변화:")
                logger.info(f"      승률: {win_rate_change:+.1%}p")
                logger.info(f"      거래: {trade_change:+.0f}회/주")

    def _get_stats_around_threshold(self, stats, threshold):
        """특정 점수 근처의 통계"""
        # threshold ± 0.5 범위의 구간들 평균
        relevant_stats = []

        for stat in stats:
            score_range = stat['score_range']

            if score_range in ['3.0미만', '10.0이상']:
                continue

            # 구간의 중간값 계산
            try:
                low, high = map(float, score_range.split('-'))
                mid = (low + high) / 2

                if abs(mid - threshold) <= 0.5:
                    relevant_stats.append(stat)
            except:
                continue

        if not relevant_stats:
            return None

        total_trades = sum(s['trades'] for s in relevant_stats)
        if total_trades == 0:
            return None

        weighted_win_rate = sum(s['trades'] * s['win_rate'] for s in relevant_stats)
        avg_win_rate = weighted_win_rate / total_trades

        return {
            'win_rate': avg_win_rate,
            'trades': total_trades / 4  # 주당 거래 (4주 기준)
        }

    def auto_apply(self, recommendations, auto_confirm=False):
        """
        자동 적용

        Args:
            recommendations: 추천 사항
            auto_confirm: 자동 승인 (True면 사용자 확인 없이 적용)

        Returns:
            applied (bool)
        """
        if not recommendations:
            return False

        recommended_threshold = recommendations['recommended_threshold']
        current_preset = ACTIVE_PRESET

        logger.info("")
        logger.info("=" * 80)
        logger.info("🔧 설정 자동 조정")
        logger.info("=" * 80)

        if not auto_confirm:
            logger.info(f"\n⚠️ 자동 적용 비활성화")
            logger.info(f"   수동으로 config.py를 수정하세요:")
            logger.info(f"   ")
            logger.info(f"   STRATEGY_PRESETS['{current_preset}']['entry_score_threshold'] = {recommended_threshold:.1f}")
            logger.info("")
            logger.info("=" * 80)
            return False

        # config.py 자동 수정 (런타임)
        STRATEGY_PRESETS[current_preset]['entry_score_threshold'] = recommended_threshold

        # 프리셋 재적용
        apply_preset(current_preset)

        logger.info(f"✅ 설정 자동 적용 완료")
        logger.info(f"   진입 점수: {recommendations['current_threshold']:.1f} → {recommended_threshold:.1f}점")
        logger.info("")
        logger.info("⚠️ 주의: 이 변경은 런타임에만 적용됩니다.")
        logger.info("   영구 적용하려면 config.py 파일을 직접 수정하세요.")
        logger.info("")
        logger.info("=" * 80)

        return True

def optimize_on_startup(score_tracker, auto_apply=False):
    """
    봇 시작 시 자동 최적화 실행

    Args:
        score_tracker: ScorePerformanceTracker 인스턴스
        auto_apply: True면 자동 적용, False면 추천만

    Returns:
        (optimized, recommendations)
    """
    optimizer = AutoOptimizer(score_tracker)

    # 분석 및 추천
    should_optimize, recommendations = optimizer.analyze_and_recommend()

    if not should_optimize:
        return False, None

    # 자동 적용 (선택적)
    if auto_apply:
        applied = optimizer.auto_apply(recommendations, auto_confirm=True)
        return applied, recommendations
    else:
        # 추천만 (수동 적용)
        optimizer.auto_apply(recommendations, auto_confirm=False)
        return False, recommendations
