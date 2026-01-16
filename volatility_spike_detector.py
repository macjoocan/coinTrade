# volatility_spike_detector.py - 급변하는 시장 대응 시스템
import pyupbit
import numpy as np
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class VolatilitySpikeDetector:
    """변동성 급증 감지기 - 급변하는 코인 시장 대응"""

    def __init__(self):
        # 감지 기준
        self.spike_threshold = 0.03      # 3% 이상 급변 = 스파이크
        self.volume_surge_threshold = 3.0  # 거래량 3배 이상
        self.lookback_minutes = 15       # 최근 15분 관찰

        # 캐시 설정
        self.cache_duration = 60         # 1분 캐시 (빠른 대응)
        self._last_check = None
        self._spike_status = False
        self._spike_details = {}

        logger.info("⚡ 변동성 스파이크 감지기 초기화")
        logger.info(f"   감지 기준: ±{self.spike_threshold:.1%} 급변")
        logger.info(f"   거래량: {self.volume_surge_threshold:.1f}배 이상")
        logger.info(f"   관찰 시간: {self.lookback_minutes}분")

    def detect_spike(self, trading_pairs):
        """변동성 스파이크 감지 (메인 함수)"""

        now = datetime.now()

        # 캐시 체크
        if self._last_check:
            elapsed = (now - self._last_check).total_seconds()
            if elapsed < self.cache_duration:
                return self._spike_status

        spike_count = 0
        spike_details = []

        # 상위 5개 코인 검사 (더 많으면 API 제한 걸림)
        check_coins = trading_pairs[:5]

        for coin in check_coins:
            ticker = f"KRW-{coin}"

            try:
                # 1분봉 최근 15개 (15분)
                df = pyupbit.get_ohlcv(ticker, interval="minute1", count=self.lookback_minutes)

                if df is None or len(df) < 10:
                    continue

                # 1. 급등/급락 감지 (가장 중요)
                price_changes = df['close'].pct_change().abs()
                max_change = price_changes.max()
                max_change_idx = price_changes.idxmax()

                # 2. 거래량 폭발 감지
                recent_volume = df['volume'].iloc[-1]
                avg_volume = df['volume'].iloc[:-1].mean()
                volume_surge = recent_volume / avg_volume if avg_volume > 0 else 1

                # 3. 가격 변동폭 (고가-저가)
                high_low_range = (df['high'] - df['low']).mean()
                avg_price = df['close'].mean()
                volatility = high_low_range / avg_price if avg_price > 0 else 0

                # 스파이크 점수 계산
                score = 0
                reasons = []

                if max_change > self.spike_threshold:  # 3% 이상 급변
                    score += 1.0
                    reasons.append(f"급변 {max_change:.1%}")
                    logger.warning(f"⚡ {coin}: 급변 감지 ({max_change:.1%}) at {max_change_idx}")

                if volume_surge > self.volume_surge_threshold:  # 거래량 3배 이상
                    score += 0.7
                    reasons.append(f"거래량 {volume_surge:.1f}x")
                    logger.warning(f"📊 {coin}: 거래량 폭발 ({volume_surge:.1f}x)")

                if volatility > 0.025:  # 변동폭 2.5% 이상
                    score += 0.5
                    reasons.append(f"고변동 {volatility:.1%}")

                if score > 0:
                    spike_details.append({
                        'coin': coin,
                        'score': score,
                        'max_change': max_change,
                        'volume_surge': volume_surge,
                        'volatility': volatility,
                        'reasons': reasons
                    })

                spike_count += score

            except Exception as e:
                logger.error(f"{coin} 변동성 감지 실패: {e}")
                continue

        # 판정: 2개 이상 코인에서 스파이크 감지 (점수 2.0 이상)
        self._spike_status = (spike_count >= 2.0)
        self._spike_details = {
            'total_score': spike_count,
            'coins': spike_details,
            'timestamp': now
        }
        self._last_check = now

        if self._spike_status:
            logger.warning(f"\n{'='*60}")
            logger.warning(f"🌪️ 시장 변동성 급증 감지!")
            logger.warning(f"{'='*60}")
            logger.warning(f"총 스파이크 점수: {spike_count:.1f}/2.0")
            for detail in spike_details:
                logger.warning(f"  • {detail['coin']}: {', '.join(detail['reasons'])}")
            logger.warning(f"{'='*60}\n")
        else:
            logger.debug(f"변동성 정상 (점수: {spike_count:.1f}/2.0)")

        return self._spike_status

    def get_risk_adjustment(self):
        """변동성 스파이크 시 리스크 조정값 반환"""

        if not self._spike_status:
            return None

        # 스파이크 강도에 따른 조정
        spike_score = self._spike_details.get('total_score', 2.0)

        # 강도별 조정값
        if spike_score >= 4.0:  # 매우 심각
            adjustment = {
                'position_size_multiplier': 0.3,   # 포지션 30%로 축소
                'stop_loss_tightening': 0.003,     # 손절 -0.3%로 타이트
                'entry_score_increase': 3.0,       # 진입 점수 +3점 필요
                'force_exit_on_spike': True,       # 기존 포지션 강제 청산
                'severity': 'critical',
            }
        elif spike_score >= 3.0:  # 심각
            adjustment = {
                'position_size_multiplier': 0.4,
                'stop_loss_tightening': 0.004,
                'entry_score_increase': 2.5,
                'force_exit_on_spike': True,
                'severity': 'high',
            }
        else:  # 보통 (2.0 ~ 3.0)
            adjustment = {
                'position_size_multiplier': 0.5,
                'stop_loss_tightening': 0.005,
                'entry_score_increase': 2.0,
                'force_exit_on_spike': False,
                'severity': 'medium',
            }

        adjustment['spike_score'] = spike_score
        adjustment['affected_coins'] = [c['coin'] for c in self._spike_details.get('coins', [])]

        return adjustment

    def is_coin_affected(self, symbol):
        """특정 코인이 스파이크 영향을 받는지 확인"""

        if not self._spike_status:
            return False

        affected_coins = [c['coin'] for c in self._spike_details.get('coins', [])]
        return symbol in affected_coins

    def get_spike_details(self):
        """스파이크 상세 정보 반환 (디버깅용)"""
        return self._spike_details

    def reset_cache(self):
        """캐시 강제 리셋 (수동 재평가용)"""
        self._last_check = None
        logger.info("⚡ 변동성 캐시 리셋")
