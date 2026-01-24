# adaptive_score_manager.py - 주기적 히스토리 분석 및 점수 자동 조정

import json
import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import time

logger = logging.getLogger(__name__)


class AdaptiveScoreManager:
    """
    주기적으로 거래 히스토리를 분석하여 진입 점수를 자동 조정하는 시스템

    기능:
    - n시간마다 히스토리 분석
    - 승률/수익률 기반 점수 자동 조정
    - 시장 상황에 따른 동적 조정
    - 조정 이력 추적
    """

    def __init__(self,
                 trade_history_file='trade_history.json',
                 score_history_file='score_adjustment_history.json',
                 analysis_interval_hours=4):
        """
        Args:
            trade_history_file: 거래 히스토리 파일 경로
            score_history_file: 점수 조정 이력 파일 경로
            analysis_interval_hours: 분석 주기 (시간)
        """
        self.trade_history_file = trade_history_file
        self.score_history_file = score_history_file
        self.analysis_interval = analysis_interval_hours * 3600  # 초 단위

        # 점수 조정 설정
        self.config = {
            'min_trades_for_analysis': 10,      # 분석에 필요한 최소 거래 수
            'lookback_days': 7,                  # 분석할 기간 (일)
            'target_win_rate': 0.50,             # 목표 승률
            'min_win_rate': 0.40,                # 최소 허용 승률
            'max_adjustment': 0.5,               # 최대 조정폭
            'adjustment_step': 0.1,              # 조정 단위
            'score_min': 4.0,                    # 최소 진입 점수
            'score_max': 8.0,                    # 최대 진입 점수
            'consecutive_loss_threshold': 3,    # 연속 손실 임계값
            'hot_streak_threshold': 3,          # 연속 수익 임계값
        }

        # 현재 상태
        self.current_score_threshold = 5.5      # 현재 진입 점수 (config에서 로드됨)
        self.last_analysis_time = None
        self.adjustment_history = []

        # 스레드 관련
        self._running = False
        self._thread = None

        # 초기화
        self._load_history()

        logger.info(f"✅ AdaptiveScoreManager 초기화")
        logger.info(f"   분석 주기: {analysis_interval_hours}시간")
        logger.info(f"   현재 점수: {self.current_score_threshold}")

    def _load_history(self):
        """조정 이력 로드"""
        if os.path.exists(self.score_history_file):
            try:
                with open(self.score_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.adjustment_history = data.get('history', [])
                    self.last_analysis_time = data.get('last_analysis_time')
                    if data.get('current_score'):
                        self.current_score_threshold = data['current_score']
                    logger.info(f"   조정 이력 로드: {len(self.adjustment_history)}건")
            except Exception as e:
                logger.error(f"조정 이력 로드 실패: {e}")

    def _save_history(self):
        """조정 이력 저장"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'last_analysis_time': self.last_analysis_time,
                'current_score': self.current_score_threshold,
                'history': self.adjustment_history[-100:]  # 최근 100건만 유지
            }
            with open(self.score_history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"조정 이력 저장 실패: {e}")

    def load_trade_history(self, days=None):
        """거래 히스토리 로드"""
        if days is None:
            days = self.config['lookback_days']

        if not os.path.exists(self.trade_history_file):
            return []

        try:
            with open(self.trade_history_file, 'r', encoding='utf-8') as f:
                all_trades = json.load(f)

            # 기간 필터링
            cutoff = datetime.now() - timedelta(days=days)
            recent_trades = []

            for trade in all_trades:
                try:
                    trade_time = datetime.fromisoformat(trade['timestamp'])
                    if trade_time >= cutoff:
                        recent_trades.append(trade)
                except:
                    continue

            return recent_trades

        except Exception as e:
            logger.error(f"거래 히스토리 로드 실패: {e}")
            return []

    def analyze_performance(self, trades=None):
        """
        거래 성과 분석

        Returns:
            dict: 분석 결과
        """
        if trades is None:
            trades = self.load_trade_history()

        if len(trades) < self.config['min_trades_for_analysis']:
            return {
                'valid': False,
                'reason': f"거래 수 부족 ({len(trades)}/{self.config['min_trades_for_analysis']})"
            }

        # 기본 통계
        total_trades = len(trades)
        wins = [t for t in trades if t.get('pnl', 0) > 0]
        losses = [t for t in trades if t.get('pnl', 0) <= 0]

        win_rate = len(wins) / total_trades if total_trades > 0 else 0

        # 평균 수익/손실
        avg_win = sum(t.get('pnl_rate', 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get('pnl_rate', 0) for t in losses) / len(losses) if losses else 0

        # 총 수익률
        total_pnl_rate = sum(t.get('pnl_rate', 0) for t in trades)
        avg_pnl_rate = total_pnl_rate / total_trades if total_trades > 0 else 0

        # 연속 손익 분석
        consecutive_losses = self._count_consecutive(trades, 'loss')
        consecutive_wins = self._count_consecutive(trades, 'win')

        # 최근 추세 (최근 5거래)
        recent_trades = trades[-5:] if len(trades) >= 5 else trades
        recent_wins = len([t for t in recent_trades if t.get('pnl', 0) > 0])
        recent_trend = 'hot' if recent_wins >= 4 else 'cold' if recent_wins <= 1 else 'neutral'

        # 시간대별 분석
        hourly_performance = self._analyze_by_hour(trades)

        return {
            'valid': True,
            'total_trades': total_trades,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_pnl_rate': avg_pnl_rate,
            'total_pnl_rate': total_pnl_rate,
            'consecutive_losses': consecutive_losses,
            'consecutive_wins': consecutive_wins,
            'recent_trend': recent_trend,
            'hourly_performance': hourly_performance,
            'analysis_time': datetime.now().isoformat()
        }

    def _count_consecutive(self, trades, result_type):
        """연속 승/패 횟수 계산 (최근부터)"""
        count = 0
        for trade in reversed(trades):
            if result_type == 'win' and trade.get('pnl', 0) > 0:
                count += 1
            elif result_type == 'loss' and trade.get('pnl', 0) <= 0:
                count += 1
            else:
                break
        return count

    def _analyze_by_hour(self, trades):
        """시간대별 성과 분석"""
        hourly = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0})

        for trade in trades:
            try:
                trade_time = datetime.fromisoformat(trade['timestamp'])
                hour = trade_time.hour

                if trade.get('pnl', 0) > 0:
                    hourly[hour]['wins'] += 1
                else:
                    hourly[hour]['losses'] += 1

                hourly[hour]['total_pnl'] += trade.get('pnl_rate', 0)
            except:
                continue

        return dict(hourly)

    def calculate_adjustment(self, analysis):
        """
        점수 조정값 계산

        Returns:
            tuple: (adjustment, reason)
        """
        if not analysis.get('valid'):
            return 0, analysis.get('reason', '분석 불가')

        adjustment = 0
        reasons = []

        win_rate = analysis['win_rate']
        consecutive_losses = analysis['consecutive_losses']
        consecutive_wins = analysis['consecutive_wins']
        recent_trend = analysis['recent_trend']
        avg_pnl_rate = analysis['avg_pnl_rate']

        # 1. 승률 기반 조정
        if win_rate < self.config['min_win_rate']:
            # 승률 너무 낮음 → 점수 올리기 (더 엄격하게)
            adjustment += self.config['adjustment_step'] * 2
            reasons.append(f"승률 낮음({win_rate:.1%})")
        elif win_rate < self.config['target_win_rate']:
            adjustment += self.config['adjustment_step']
            reasons.append(f"승률 미달({win_rate:.1%})")
        elif win_rate > 0.65:
            # 승률 높음 → 점수 낮추기 (더 많은 기회)
            adjustment -= self.config['adjustment_step']
            reasons.append(f"승률 우수({win_rate:.1%})")

        # 2. 연속 손실 대응
        if consecutive_losses >= self.config['consecutive_loss_threshold']:
            adjustment += self.config['adjustment_step']
            reasons.append(f"연속손실 {consecutive_losses}회")

        # 3. 연속 수익 대응 (핫 스트릭)
        if consecutive_wins >= self.config['hot_streak_threshold']:
            adjustment -= self.config['adjustment_step'] * 0.5
            reasons.append(f"연속수익 {consecutive_wins}회")

        # 4. 평균 수익률 기반
        if avg_pnl_rate < -0.01:  # 평균 -1% 이하
            adjustment += self.config['adjustment_step']
            reasons.append(f"평균수익 부진({avg_pnl_rate:.2%})")
        elif avg_pnl_rate > 0.02:  # 평균 +2% 이상
            adjustment -= self.config['adjustment_step'] * 0.5
            reasons.append(f"평균수익 양호({avg_pnl_rate:.2%})")

        # 5. 최근 추세 반영
        if recent_trend == 'cold':
            adjustment += self.config['adjustment_step'] * 0.5
            reasons.append("최근 부진")
        elif recent_trend == 'hot':
            adjustment -= self.config['adjustment_step'] * 0.5
            reasons.append("최근 호조")

        # 조정폭 제한
        adjustment = max(-self.config['max_adjustment'],
                        min(self.config['max_adjustment'], adjustment))

        # 소수점 정리
        adjustment = round(adjustment, 1)

        reason = ', '.join(reasons) if reasons else '변경 없음'

        return adjustment, reason

    def apply_adjustment(self, adjustment, reason, analysis):
        """
        점수 조정 적용

        Returns:
            tuple: (new_score, applied)
        """
        if adjustment == 0:
            logger.info(f"📊 점수 유지: {self.current_score_threshold} (변경 불필요)")
            return self.current_score_threshold, False

        old_score = self.current_score_threshold
        new_score = old_score + adjustment

        # 범위 제한
        new_score = max(self.config['score_min'],
                       min(self.config['score_max'], new_score))
        new_score = round(new_score, 1)

        if new_score == old_score:
            logger.info(f"📊 점수 유지: {old_score} (범위 제한)")
            return old_score, False

        # 적용
        self.current_score_threshold = new_score

        # 이력 기록
        record = {
            'timestamp': datetime.now().isoformat(),
            'old_score': old_score,
            'new_score': new_score,
            'adjustment': adjustment,
            'reason': reason,
            'analysis': {
                'win_rate': analysis.get('win_rate'),
                'total_trades': analysis.get('total_trades'),
                'avg_pnl_rate': analysis.get('avg_pnl_rate'),
                'consecutive_losses': analysis.get('consecutive_losses')
            }
        }
        self.adjustment_history.append(record)

        # 저장
        self._save_history()

        logger.info("=" * 60)
        logger.info("🔄 진입 점수 자동 조정")
        logger.info("=" * 60)
        logger.info(f"   이전: {old_score}")
        logger.info(f"   현재: {new_score} ({adjustment:+.1f})")
        logger.info(f"   사유: {reason}")
        logger.info(f"   기반: {analysis.get('total_trades')}건 분석, 승률 {analysis.get('win_rate', 0):.1%}")
        logger.info("=" * 60)

        return new_score, True

    def run_analysis(self, apply_changes=True):
        """
        분석 실행 및 조정 적용

        Args:
            apply_changes: True면 조정 적용, False면 분석만

        Returns:
            dict: 분석 결과 및 조정 정보
        """
        logger.info("")
        logger.info("🔍 히스토리 기반 점수 분석 시작...")

        # 분석
        analysis = self.analyze_performance()

        if not analysis.get('valid'):
            logger.info(f"⚠️ {analysis.get('reason')}")
            return {'applied': False, 'reason': analysis.get('reason')}

        # 조정값 계산
        adjustment, reason = self.calculate_adjustment(analysis)

        result = {
            'analysis': analysis,
            'adjustment': adjustment,
            'reason': reason,
            'current_score': self.current_score_threshold,
            'applied': False
        }

        # 적용
        if apply_changes and adjustment != 0:
            new_score, applied = self.apply_adjustment(adjustment, reason, analysis)
            result['new_score'] = new_score
            result['applied'] = applied
        else:
            logger.info(f"📊 현재 점수: {self.current_score_threshold}")
            logger.info(f"   분석 결과: 승률 {analysis['win_rate']:.1%}, "
                       f"평균수익 {analysis['avg_pnl_rate']:+.2%}")
            if adjustment != 0:
                logger.info(f"   권장 조정: {adjustment:+.1f} ({reason})")

        self.last_analysis_time = datetime.now().isoformat()
        self._save_history()

        return result

    def start_background_monitor(self, config_updater=None):
        """
        백그라운드 모니터링 시작

        Args:
            config_updater: 설정 업데이트 콜백 함수 (new_score를 받음)
        """
        if self._running:
            logger.warning("이미 모니터링 중입니다")
            return

        self._running = True
        self._config_updater = config_updater

        def monitor_loop():
            while self._running:
                try:
                    # 분석 실행
                    result = self.run_analysis(apply_changes=True)

                    # 설정 업데이트 콜백 호출
                    if result.get('applied') and self._config_updater:
                        self._config_updater(result['new_score'])

                except Exception as e:
                    logger.error(f"분석 오류: {e}")

                # 다음 분석까지 대기
                time.sleep(self.analysis_interval)

        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()

        logger.info(f"🔄 백그라운드 점수 모니터링 시작 (주기: {self.analysis_interval // 3600}시간)")

    def stop_background_monitor(self):
        """백그라운드 모니터링 중지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("⏹️ 백그라운드 점수 모니터링 중지")

    def get_current_score(self):
        """현재 진입 점수 반환"""
        return self.current_score_threshold

    def set_current_score(self, score):
        """현재 진입 점수 설정 (외부에서 동기화용)"""
        self.current_score_threshold = score

    def get_adjustment_summary(self, days=7):
        """최근 조정 요약"""
        cutoff = datetime.now() - timedelta(days=days)
        recent = []

        for record in self.adjustment_history:
            try:
                rec_time = datetime.fromisoformat(record['timestamp'])
                if rec_time >= cutoff:
                    recent.append(record)
            except:
                continue

        if not recent:
            return None

        total_adjustment = sum(r['adjustment'] for r in recent)

        return {
            'period_days': days,
            'adjustments_count': len(recent),
            'total_adjustment': total_adjustment,
            'current_score': self.current_score_threshold,
            'recent_adjustments': recent[-5:]  # 최근 5건
        }

    def print_status(self):
        """현재 상태 출력"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 AdaptiveScoreManager 상태")
        logger.info("=" * 60)
        logger.info(f"   현재 진입 점수: {self.current_score_threshold}")
        logger.info(f"   분석 주기: {self.analysis_interval // 3600}시간")
        logger.info(f"   마지막 분석: {self.last_analysis_time or '없음'}")
        logger.info(f"   조정 이력: {len(self.adjustment_history)}건")

        # 최근 조정
        if self.adjustment_history:
            last = self.adjustment_history[-1]
            logger.info(f"   마지막 조정: {last['old_score']} → {last['new_score']} ({last['reason']})")

        logger.info("=" * 60)


# 편의 함수
def create_adaptive_manager(analysis_interval_hours=4):
    """AdaptiveScoreManager 인스턴스 생성"""
    return AdaptiveScoreManager(analysis_interval_hours=analysis_interval_hours)


if __name__ == "__main__":
    # 테스트
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    manager = AdaptiveScoreManager(analysis_interval_hours=4)
    manager.print_status()

    # 분석 실행 (적용 안 함)
    result = manager.run_analysis(apply_changes=False)
    print(f"\n분석 결과: {result}")
