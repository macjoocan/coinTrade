# volatility_monitor.py - 실시간 변동성 모니터링 및 동적 파라미터 조정

import logging
import pyupbit
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

class VolatilityMonitor:
    """
    실시간 변동성 모니터링
    - 시장 변동성 추적
    - 변동성에 따른 파라미터 자동 조정
    - 급격한 변동성 감지 및 알림
    """

    def __init__(self, config=None):
        self.config = config or {}

        # 변동성 기록 (심볼별)
        self.volatility_history = defaultdict(list)

        # 현재 변동성 수준
        self.current_volatility = {}

        # 변동성 등급
        self.volatility_grade = {}  # 'low', 'medium', 'high', 'extreme'

        # 마지막 업데이트 시간
        self.last_update = {}

        # 설정값
        self.update_interval = self.config.get('update_interval', 300)  # 5분마다 업데이트
        self.lookback_periods = self.config.get('lookback_periods', 24)  # 24시간

        # 변동성 임계값
        self.thresholds = {
            'low': 0.015,      # 1.5% 미만
            'medium': 0.03,    # 3% 미만
            'high': 0.05,      # 5% 미만
            'extreme': 0.05    # 5% 이상
        }

        logger.info("✅ VolatilityMonitor 초기화 완료")
        logger.info(f"   업데이트 간격: {self.update_interval}초")
        logger.info(f"   관찰 기간: {self.lookback_periods}시간")

    def calculate_volatility(self, symbol):
        """
        심볼의 변동성 계산 (ATR 기반)

        Args:
            symbol: 심볼 (예: BTC)

        Returns:
            volatility: 변동성 (float)
        """
        try:
            ticker = f"KRW-{symbol}"

            # OHLCV 데이터 조회
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=self.lookback_periods + 1)

            if df is None or len(df) < self.lookback_periods:
                logger.warning(f"{symbol}: 데이터 부족")
                return None

            # ATR (Average True Range) 계산
            high = df['high']
            low = df['low']
            close = df['close']

            # True Range 계산
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())

            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            atr = tr.rolling(window=14).mean().iloc[-1]

            # 현재가 대비 비율로 정규화
            current_price = close.iloc[-1]
            volatility = atr / current_price

            return volatility

        except Exception as e:
            logger.error(f"{symbol} 변동성 계산 실패: {e}")
            return None

    def update_volatility(self, symbols):
        """
        여러 심볼의 변동성 업데이트

        Args:
            symbols: 심볼 리스트 ['BTC', 'ETH', ...]
        """
        now = time.time()

        for symbol in symbols:
            # 업데이트 주기 체크
            last_time = self.last_update.get(symbol, 0)
            if now - last_time < self.update_interval:
                continue

            # 변동성 계산
            volatility = self.calculate_volatility(symbol)

            if volatility is not None:
                # 기록 저장
                self.current_volatility[symbol] = volatility
                self.volatility_history[symbol].append({
                    'timestamp': datetime.now(),
                    'volatility': volatility
                })

                # 최근 100개만 유지
                if len(self.volatility_history[symbol]) > 100:
                    self.volatility_history[symbol].pop(0)

                # 변동성 등급 판정
                grade = self._classify_volatility(volatility)
                old_grade = self.volatility_grade.get(symbol)
                self.volatility_grade[symbol] = grade

                # 등급 변경 시 알림
                if old_grade and old_grade != grade:
                    logger.warning(f"🌡️ {symbol} 변동성 등급 변경: {old_grade} → {grade}")
                    logger.warning(f"   현재 변동성: {volatility:.2%}")

                self.last_update[symbol] = now

    def _classify_volatility(self, volatility):
        """변동성 등급 분류"""
        if volatility < self.thresholds['low']:
            return 'low'
        elif volatility < self.thresholds['medium']:
            return 'medium'
        elif volatility < self.thresholds['high']:
            return 'high'
        else:
            return 'extreme'

    def get_volatility(self, symbol):
        """
        심볼의 현재 변동성 조회

        Returns:
            (volatility, grade)
        """
        vol = self.current_volatility.get(symbol, 0.02)  # 기본값 2%
        grade = self.volatility_grade.get(symbol, 'medium')
        return vol, grade

    def get_market_volatility(self, symbols):
        """
        전체 시장 변동성 계산 (평균)

        Args:
            symbols: 심볼 리스트

        Returns:
            (avg_volatility, grade)
        """
        volatilities = []

        for symbol in symbols:
            vol = self.current_volatility.get(symbol)
            if vol is not None:
                volatilities.append(vol)

        if not volatilities:
            return 0.02, 'medium'

        avg_vol = np.mean(volatilities)
        grade = self._classify_volatility(avg_vol)

        return avg_vol, grade

    def get_dynamic_stop_loss(self, symbol, base_stop_loss):
        """
        변동성 기반 동적 손절 계산

        Args:
            symbol: 심볼
            base_stop_loss: 기본 손절 (예: 0.01 = 1%)

        Returns:
            adjusted_stop_loss: 조정된 손절
        """
        vol, grade = self.get_volatility(symbol)

        if grade == 'low':
            # 저변동성: 손절 타이트하게
            multiplier = 0.8
        elif grade == 'medium':
            # 중변동성: 기본값 유지
            multiplier = 1.0
        elif grade == 'high':
            # 고변동성: 손절 여유 있게
            multiplier = 1.3
        else:  # extreme
            # 극단 변동성: 매우 여유 있게
            multiplier = 1.5

        adjusted = base_stop_loss * multiplier

        logger.info(f"{symbol} 손절 조정: {base_stop_loss:.2%} → {adjusted:.2%} (변동성: {grade})")

        return adjusted

    def get_dynamic_position_size(self, symbol, base_size):
        """
        변동성 기반 동적 포지션 크기 조정

        Args:
            symbol: 심볼
            base_size: 기본 포지션 크기

        Returns:
            adjusted_size: 조정된 포지션 크기
        """
        vol, grade = self.get_volatility(symbol)

        if grade == 'low':
            # 저변동성: 포지션 크기 증가
            multiplier = 1.2
        elif grade == 'medium':
            # 중변동성: 기본값 유지
            multiplier = 1.0
        elif grade == 'high':
            # 고변동성: 포지션 축소
            multiplier = 0.7
        else:  # extreme
            # 극단 변동성: 크게 축소
            multiplier = 0.5

        adjusted = base_size * multiplier

        return adjusted

    def should_pause_trading(self, symbols):
        """
        거래 일시 중단 여부 판단 (극단적 변동성)

        Args:
            symbols: 확인할 심볼 리스트

        Returns:
            (should_pause, reason)
        """
        extreme_count = 0
        high_count = 0

        for symbol in symbols:
            grade = self.volatility_grade.get(symbol)
            if grade == 'extreme':
                extreme_count += 1
            elif grade == 'high':
                high_count += 1

        total = len(symbols)

        # 50% 이상이 극단 변동성
        if extreme_count >= total * 0.5:
            return True, f"극단 변동성 코인 {extreme_count}/{total}개 - 거래 일시 중단"

        # 80% 이상이 고변동성
        if (extreme_count + high_count) >= total * 0.8:
            return True, f"고변동성 코인 {extreme_count + high_count}/{total}개 - 거래 일시 중단"

        return False, "정상"

    def detect_volatility_spike(self, symbol, lookback=5):
        """
        급격한 변동성 증가 감지

        Args:
            symbol: 심볼
            lookback: 과거 몇 개 데이터와 비교할지

        Returns:
            (is_spike, ratio)
        """
        history = self.volatility_history.get(symbol, [])

        if len(history) < lookback + 1:
            return False, 1.0

        recent = history[-lookback:]
        current = self.current_volatility.get(symbol)

        if not current or not recent:
            return False, 1.0

        avg_past = np.mean([h['volatility'] for h in recent])

        if avg_past == 0:
            return False, 1.0

        ratio = current / avg_past

        # 2배 이상 증가
        if ratio >= 2.0:
            logger.warning(f"⚠️ {symbol} 변동성 급증 감지!")
            logger.warning(f"   과거 평균: {avg_past:.2%} → 현재: {current:.2%}")
            logger.warning(f"   증가율: {ratio:.1f}배")
            return True, ratio

        return False, ratio

    def print_status(self, symbols):
        """변동성 현황 출력"""
        logger.info("")
        logger.info("="*60)
        logger.info("🌡️ 변동성 현황")
        logger.info("="*60)

        for symbol in symbols:
            vol, grade = self.get_volatility(symbol)

            grade_emoji = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🟠',
                'extreme': '🔴'
            }

            emoji = grade_emoji.get(grade, '⚪')

            logger.info(f"{emoji} {symbol}: {vol:.2%} ({grade.upper()})")

        # 시장 전체 변동성
        market_vol, market_grade = self.get_market_volatility(symbols)
        logger.info("")
        logger.info(f"📊 시장 평균: {market_vol:.2%} ({market_grade.upper()})")

        # 거래 중단 체크
        should_pause, reason = self.should_pause_trading(symbols)
        if should_pause:
            logger.warning(f"⚠️ {reason}")

        logger.info("="*60)
        logger.info("")

    def get_safe_coins(self, symbols, max_volatility=0.04):
        """
        안전한 변동성의 코인 필터링

        Args:
            symbols: 심볼 리스트
            max_volatility: 최대 허용 변동성 (기본 4%)

        Returns:
            safe_symbols: 안전한 심볼 리스트
        """
        safe = []

        for symbol in symbols:
            vol = self.current_volatility.get(symbol)
            if vol and vol <= max_volatility:
                safe.append(symbol)

        return safe
