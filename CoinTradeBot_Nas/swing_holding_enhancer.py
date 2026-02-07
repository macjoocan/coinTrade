# swing_holding_enhancer.py - 스윙 홀딩 강화 시스템

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SwingHoldingEnhancer:
    """
    스윙 홀딩 강화 시스템

    목적:
    - 조기 익절 방지 (현재 58.8%가 0~1.5% 소액 수익에서 매도)
    - 최소 보유 시간 강제 (현재 2.2h → 목표 12~24h)
    - 데이터 기반: 12h+ 보유 시 승률 81.8% vs 12h 미만 61.0%

    핵심 원칙:
    1. 손절은 즉시 허용 (-1.5%)
    2. 소액 수익 + 짧은 보유 → 거부
    3. 큰 수익 (3%+) → 즉시 허용
    4. 추세 지속 시 홀딩 연장
    """

    def __init__(self, config=None):
        # 기본 설정
        self.min_swing_hold_hours = 12  # 최소 12시간 보유
        self.ideal_swing_hold_hours = 24  # 이상적 24시간

        # 수익률 기준
        self.min_profit_for_early_exit = 0.025  # 2.5% (조기 청산 허용 기준)
        self.good_profit_threshold = 0.030  # 3.0% (즉시 청산 허용)
        self.excellent_profit_threshold = 0.050  # 5.0% (무조건 청산)

        # 손절 기준
        self.stop_loss_threshold = -0.015  # -1.5%

        # 설정 덮어쓰기
        if config:
            self.min_swing_hold_hours = config.get('min_swing_hold_hours', 12)
            self.ideal_swing_hold_hours = config.get('ideal_swing_hold_hours', 24)
            self.min_profit_for_early_exit = config.get('min_profit_for_early_exit', 0.025)
            self.good_profit_threshold = config.get('good_profit_threshold', 0.030)

        logger.info("✅ SwingHoldingEnhancer 초기화")
        logger.info(f"   최소 보유: {self.min_swing_hold_hours}시간")
        logger.info(f"   조기 익절 기준: {self.min_profit_for_early_exit:.1%}")

    def should_allow_exit(self, symbol, entry_time, current_pnl_rate, exit_reason='normal'):
        """
        스윙 관점에서 청산 허용 여부

        Args:
            symbol: 코인 심볼
            entry_time: 진입 시간 (datetime)
            current_pnl_rate: 현재 손익률 (0.025 = 2.5%)
            exit_reason: 청산 이유 ('stop_loss', 'take_profit', 'trailing_stop', 'normal')

        Returns:
            (allow, reason)
            - allow: True/False
            - reason: 허용/거부 사유
        """
        # 보유 시간 계산
        if isinstance(entry_time, str):
            entry_dt = datetime.fromisoformat(entry_time)
        else:
            entry_dt = entry_time

        hold_hours = (datetime.now() - entry_dt).total_seconds() / 3600

        # ========================================
        # 1. 손절은 즉시 허용
        # ========================================
        if current_pnl_rate <= self.stop_loss_threshold or exit_reason == 'stop_loss':
            logger.info(f"{symbol}: 손절 허용 (손실: {current_pnl_rate:.2%}, 보유: {hold_hours:.1f}h)")
            return True, "손절"

        # ========================================
        # 2. 탁월한 수익 (5%+) → 즉시 허용
        # ========================================
        if current_pnl_rate >= self.excellent_profit_threshold:
            logger.info(f"{symbol}: 탁월한 수익 달성 ({current_pnl_rate:.2%}) - 즉시 익절")
            return True, f"탁월한 수익 ({current_pnl_rate:.2%})"

        # ========================================
        # 3. 최소 보유 시간 미달 체크
        # ========================================
        if hold_hours < self.min_swing_hold_hours:
            # 최소 보유 시간 미달이지만 큰 수익이면 허용
            if current_pnl_rate >= self.min_profit_for_early_exit:
                logger.info(f"{symbol}: 조기 익절 허용 (수익: {current_pnl_rate:.2%}, 보유: {hold_hours:.1f}h)")
                return True, f"조기 목표 수익 달성 ({current_pnl_rate:.2%})"
            else:
                # 소액 수익 → 거부!
                remaining_hours = self.min_swing_hold_hours - hold_hours
                logger.info(f"{symbol}: 스윙 홀딩 강제 (현재: {hold_hours:.1f}h, 남은시간: {remaining_hours:.1f}h, 수익: {current_pnl_rate:.2%})")
                return False, f"스윙 최소 보유 미달 ({hold_hours:.1f}h/{self.min_swing_hold_hours}h)"

        # ========================================
        # 4. 최소 보유 시간 달성 이후
        # ========================================

        # 4-1. 좋은 수익 (3%+) → 허용
        if current_pnl_rate >= self.good_profit_threshold:
            logger.info(f"{symbol}: 좋은 수익 + 충분한 보유 ({current_pnl_rate:.2%}, {hold_hours:.1f}h)")
            return True, f"목표 수익 달성 ({current_pnl_rate:.2%})"

        # 4-2. 중간 수익 (2~3%) → 이상적 보유 시간 체크
        if current_pnl_rate >= 0.020:
            if hold_hours >= self.ideal_swing_hold_hours:
                logger.info(f"{symbol}: 이상적 보유 달성 + 중간 수익 ({current_pnl_rate:.2%}, {hold_hours:.1f}h)")
                return True, f"충분한 보유 + 적정 수익 ({current_pnl_rate:.2%})"
            else:
                # 아직 이상적 시간 미달 → 홀딩
                logger.info(f"{symbol}: 중간 수익이지만 더 홀딩 ({current_pnl_rate:.2%}, {hold_hours:.1f}h/{self.ideal_swing_hold_hours}h)")
                return False, f"추가 홀딩 권장 (목표: {self.ideal_swing_hold_hours}h)"

        # 4-3. 소액 수익 (0~2%) → 홀딩
        if current_pnl_rate > 0:
            logger.info(f"{symbol}: 소액 수익 홀딩 ({current_pnl_rate:.2%}, {hold_hours:.1f}h)")
            return False, f"소액 수익 - 추가 상승 대기"

        # 4-4. 손실 상태 (0% ~ -1.5%) → 홀딩
        logger.info(f"{symbol}: 손실 홀딩 ({current_pnl_rate:.2%}, {hold_hours:.1f}h)")
        return False, f"손실 상태 - 반등 대기"

    def get_recommended_hold_time(self, current_pnl_rate):
        """
        현재 수익률에 따른 권장 보유 시간

        Returns:
            recommended_hours
        """
        if current_pnl_rate >= 0.030:  # 3% 이상
            return self.min_swing_hold_hours  # 최소만 충족하면 OK
        elif current_pnl_rate >= 0.020:  # 2~3%
            return (self.min_swing_hold_hours + self.ideal_swing_hold_hours) / 2  # 중간
        else:  # 2% 미만
            return self.ideal_swing_hold_hours  # 이상적 시간까지 기다림

    def get_exit_strategy_summary(self, symbol, entry_time, current_pnl_rate):
        """
        현재 상태 요약

        Returns:
            summary dict
        """
        if isinstance(entry_time, str):
            entry_dt = datetime.fromisoformat(entry_time)
        else:
            entry_dt = entry_time

        hold_hours = (datetime.now() - entry_dt).total_seconds() / 3600

        allow, reason = self.should_allow_exit(symbol, entry_time, current_pnl_rate)

        recommended = self.get_recommended_hold_time(current_pnl_rate)
        remaining = max(0, recommended - hold_hours)

        return {
            'symbol': symbol,
            'hold_hours': hold_hours,
            'current_pnl_rate': current_pnl_rate,
            'allow_exit': allow,
            'reason': reason,
            'recommended_hold_hours': recommended,
            'remaining_hours': remaining,
            'progress': min(100, (hold_hours / recommended) * 100)
        }

    def print_status(self, symbol, entry_time, current_pnl_rate):
        """상태 출력"""
        summary = self.get_exit_strategy_summary(symbol, entry_time, current_pnl_rate)

        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"📊 {symbol} 스윙 홀딩 상태")
        logger.info(f"{'='*60}")
        logger.info(f"보유 시간: {summary['hold_hours']:.1f}h / {summary['recommended_hold_hours']:.1f}h ({summary['progress']:.0f}%)")
        logger.info(f"현재 수익: {summary['current_pnl_rate']:+.2%}")
        logger.info(f"청산 가능: {'✅ YES' if summary['allow_exit'] else '❌ NO'}")
        logger.info(f"사유: {summary['reason']}")

        if not summary['allow_exit'] and summary['remaining_hours'] > 0:
            logger.info(f"남은 시간: {summary['remaining_hours']:.1f}시간")

        logger.info(f"{'='*60}")
        logger.info(f"")
