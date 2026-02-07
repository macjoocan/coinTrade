# rapid_market_detector.py
# 실시간 시장 급변 감지 시스템

import pyupbit
import numpy as np
import pandas as pd  # 🆕 상단으로 이동
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


class RapidMarketDetector:
    """
    실시간 시장 급변 감지기
    - 1분/5분/15분봉 기반 빠른 분석
    - 급등락 감지
    - 모멘텀 전환 감지
    - 변동성 스파이크 감지
    """

    def __init__(self):
        # 캐시 설정 (초 단위)
        self._cache_duration = 30  # 30초 캐시 (빠른 대응)
        self._last_analysis_time = None
        self._cached_result = None

        # 시장 상태
        self.market_state = {
            'condition': 'neutral',      # bullish, bearish, neutral, crash, surge
            'volatility': 'normal',      # low, normal, high, extreme
            'momentum': 'neutral',       # strong_up, up, neutral, down, strong_down
            'trend_strength': 0,         # -10 ~ +10
            'rapid_change': False,       # 급변 여부
            'score_adjustment': 0,       # 진입 점수 조정값
        }

        # 변동성 기록 (최근 1시간)
        self.volatility_history = deque(maxlen=60)

        # 가격 변화 기록
        self.price_changes = {}

    def analyze(self, trading_pairs):
        """
        실시간 시장 분석 (메인 함수)
        Returns: market_state dict
        """
        now = datetime.now()

        # 캐시 확인
        if self._last_analysis_time:
            elapsed = (now - self._last_analysis_time).total_seconds()
            if elapsed < self._cache_duration and self._cached_result:
                return self._cached_result

        try:
            # 대장주 분석 (BTC, ETH 우선)
            major_coins = trading_pairs[:3] if len(trading_pairs) >= 3 else trading_pairs

            # 멀티 타임프레임 분석
            mtf_result = self._analyze_multi_timeframe(major_coins)

            # 급등락 감지
            rapid_change = self._detect_rapid_change(major_coins)

            # 변동성 분석
            volatility = self._analyze_volatility(major_coins)

            # 모멘텀 분석
            momentum = self._analyze_momentum(major_coins)

            # 종합 판단
            self._calculate_market_state(mtf_result, rapid_change, volatility, momentum)

            # 캐시 저장
            self._last_analysis_time = now
            self._cached_result = self.market_state.copy()

            # 상태 변화 로깅
            self._log_state_change()

            return self.market_state

        except Exception as e:
            logger.error(f"시장 분석 실패: {e}")
            return self.market_state

    def _analyze_multi_timeframe(self, coins):
        """1분/5분/15분봉 멀티 타임프레임 분석"""
        timeframes = {
            'minute1': {'weight': 0.2, 'count': 10},   # 최근 10분
            'minute5': {'weight': 0.3, 'count': 12},   # 최근 1시간
            'minute15': {'weight': 0.5, 'count': 8},   # 최근 2시간
        }

        total_score = 0
        valid_count = 0

        for coin in coins:
            ticker = f"KRW-{coin}"
            coin_score = 0

            for tf, config in timeframes.items():
                try:
                    df = pyupbit.get_ohlcv(ticker, interval=tf, count=config['count'])
                    if df is None or len(df) < config['count'] - 2:
                        continue

                    # 추세 점수 계산
                    price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]

                    # EMA 추세
                    ema_short = df['close'].ewm(span=3).mean().iloc[-1]
                    ema_long = df['close'].ewm(span=7).mean().iloc[-1]
                    ema_trend = (ema_short - ema_long) / ema_long

                    # 거래량 추세
                    vol_ratio = df['volume'].iloc[-3:].mean() / df['volume'].mean() if df['volume'].mean() > 0 else 1

                    # 점수 계산
                    tf_score = 0
                    tf_score += np.clip(price_change * 100, -3, 3)  # -3 ~ +3
                    tf_score += np.clip(ema_trend * 50, -2, 2)      # -2 ~ +2

                    if vol_ratio > 1.5 and price_change > 0:
                        tf_score += 1  # 상승 + 거래량 증가
                    elif vol_ratio > 1.5 and price_change < 0:
                        tf_score -= 1  # 하락 + 거래량 증가 (더 위험)

                    coin_score += tf_score * config['weight']

                except Exception as e:
                    logger.debug(f"{coin} {tf} 분석 실패: {e}")
                    continue

            total_score += coin_score
            valid_count += 1

        avg_score = total_score / valid_count if valid_count > 0 else 0
        return {'score': avg_score, 'valid_count': valid_count}

    def _detect_rapid_change(self, coins):
        """급등락 감지 (5분 내 ±2% 이상 변동)"""
        rapid_changes = []

        for coin in coins:
            ticker = f"KRW-{coin}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval='minute1', count=6)
                if df is None or len(df) < 5:
                    continue

                # 5분간 가격 변화
                price_5min = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]

                # 1분간 가격 변화 (초단기)
                price_1min = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2]

                change_info = {
                    'coin': coin,
                    'change_5min': price_5min,
                    'change_1min': price_1min,
                    'is_rapid': abs(price_5min) >= 0.02,  # 2% 이상
                    'is_surge': price_5min >= 0.02,
                    'is_crash': price_5min <= -0.02,
                }

                rapid_changes.append(change_info)
                self.price_changes[coin] = change_info

            except Exception as e:
                logger.debug(f"{coin} 급변 감지 실패: {e}")
                continue

        # 급변 여부 종합
        has_rapid = any(c['is_rapid'] for c in rapid_changes)
        surge_count = sum(1 for c in rapid_changes if c['is_surge'])
        crash_count = sum(1 for c in rapid_changes if c['is_crash'])

        return {
            'has_rapid_change': has_rapid,
            'surge_count': surge_count,
            'crash_count': crash_count,
            'details': rapid_changes
        }

    def _analyze_volatility(self, coins):
        """변동성 분석"""
        volatilities = []

        for coin in coins:
            ticker = f"KRW-{coin}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval='minute5', count=24)  # 2시간
                if df is None or len(df) < 12:
                    continue

                # ATR 기반 변동성
                high_low = df['high'] - df['low']
                atr = high_low.mean()
                current_range = high_low.iloc[-1]

                # 변동성 비율
                vol_ratio = current_range / atr if atr > 0 else 1

                # 가격 대비 변동성
                price_volatility = atr / df['close'].mean() if df['close'].mean() > 0 else 0

                volatilities.append({
                    'coin': coin,
                    'vol_ratio': vol_ratio,
                    'price_volatility': price_volatility,
                })

            except Exception as e:
                logger.debug(f"{coin} 변동성 분석 실패: {e}")
                continue

        # 평균 변동성
        if volatilities:
            avg_vol_ratio = np.mean([v['vol_ratio'] for v in volatilities])
            avg_price_vol = np.mean([v['price_volatility'] for v in volatilities])
        else:
            avg_vol_ratio = 1
            avg_price_vol = 0.01

        # 변동성 레벨 판단
        if avg_vol_ratio >= 2.5 or avg_price_vol >= 0.03:
            level = 'extreme'
        elif avg_vol_ratio >= 1.8 or avg_price_vol >= 0.02:
            level = 'high'
        elif avg_vol_ratio >= 0.7:
            level = 'normal'
        else:
            level = 'low'

        # 변동성 기록
        self.volatility_history.append({
            'time': datetime.now(),
            'ratio': avg_vol_ratio,
            'level': level
        })

        return {
            'level': level,
            'ratio': avg_vol_ratio,
            'price_volatility': avg_price_vol,
            'is_spike': avg_vol_ratio >= 2.0
        }

    def _analyze_momentum(self, coins):
        """모멘텀 분석 (추세 강도 및 방향)"""
        momentum_scores = []

        for coin in coins:
            ticker = f"KRW-{coin}"
            try:
                df = pyupbit.get_ohlcv(ticker, interval='minute5', count=20)
                if df is None or len(df) < 15:
                    continue

                # RSI 계산 (수정됨)
                delta = df['close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

                # 안전한 RSI 계산
                last_loss = loss.iloc[-1] if len(loss) > 0 else 0
                if last_loss != 0 and not pd.isna(last_loss):
                    rs = gain.iloc[-1] / last_loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = 50  # 기본값

                # MACD 기반 모멘텀
                ema12 = df['close'].ewm(span=12).mean()
                ema26 = df['close'].ewm(span=26).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9).mean()
                macd_hist = macd.iloc[-1] - signal.iloc[-1]

                # 가격 모멘텀
                price_mom = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5]

                # 종합 모멘텀 점수
                score = 0
                score += (rsi - 50) / 25  # -2 ~ +2
                score += np.clip(macd_hist / df['close'].iloc[-1] * 1000, -2, 2)
                score += np.clip(price_mom * 50, -3, 3)

                momentum_scores.append(score)

            except Exception as e:
                logger.debug(f"{coin} 모멘텀 분석 실패: {e}")
                continue

        if not momentum_scores:
            return {'direction': 'neutral', 'strength': 0}

        avg_score = np.mean(momentum_scores)

        # 모멘텀 방향 판단
        if avg_score >= 3:
            direction = 'strong_up'
        elif avg_score >= 1:
            direction = 'up'
        elif avg_score <= -3:
            direction = 'strong_down'
        elif avg_score <= -1:
            direction = 'down'
        else:
            direction = 'neutral'

        return {
            'direction': direction,
            'strength': avg_score,
            'raw_scores': momentum_scores
        }

    def _calculate_market_state(self, mtf_result, rapid_change, volatility, momentum):
        """종합 시장 상태 계산"""

        # 1. 시장 상황 결정
        mtf_score = mtf_result['score']

        if rapid_change['crash_count'] >= 2:
            condition = 'crash'  # 급락장
        elif rapid_change['surge_count'] >= 2:
            condition = 'surge'  # 급등장
        elif mtf_score >= 3:
            condition = 'strong_bullish'
        elif mtf_score >= 1.5:
            condition = 'bullish'
        elif mtf_score <= -3:
            condition = 'strong_bearish'
        elif mtf_score <= -1.5:
            condition = 'bearish'
        else:
            condition = 'neutral'

        # 2. 진입 점수 조정값 계산 (핵심!)
        score_adj = 0

        # 시장 상황별 조정
        condition_adjustments = {
            'crash': 4.0,           # 급락장: 거의 진입 차단
            'strong_bearish': 3.0,  # 강한 하락장
            'bearish': 2.0,         # 하락장
            'neutral': 0.5,         # 중립
            'bullish': -0.5,        # 상승장: 진입 완화
            'strong_bullish': -1.0, # 강한 상승장
            'surge': 0.0,           # 급등장: 주의 (추격매수 방지)
        }
        score_adj += condition_adjustments.get(condition, 0)

        # 변동성에 따른 추가 조정
        volatility_adjustments = {
            'extreme': 2.0,  # 극심한 변동성
            'high': 1.0,     # 높은 변동성
            'normal': 0,
            'low': -0.3,     # 낮은 변동성: 약간 완화
        }
        score_adj += volatility_adjustments.get(volatility['level'], 0)

        # 모멘텀에 따른 미세 조정
        if momentum['direction'] == 'strong_down':
            score_adj += 0.5
        elif momentum['direction'] == 'strong_up':
            score_adj -= 0.3

        # 급변 시 추가 조정
        if rapid_change['has_rapid_change']:
            score_adj += 1.0  # 급변 시 보수적

        # 3. 상태 업데이트
        self.market_state = {
            'condition': condition,
            'volatility': volatility['level'],
            'momentum': momentum['direction'],
            'trend_strength': mtf_score,
            'rapid_change': rapid_change['has_rapid_change'],
            'score_adjustment': round(score_adj, 1),
            'details': {
                'mtf_score': mtf_score,
                'volatility_ratio': volatility['ratio'],
                'momentum_strength': momentum['strength'],
                'crash_count': rapid_change['crash_count'],
                'surge_count': rapid_change['surge_count'],
            }
        }

    def _log_state_change(self):
        """상태 변화 로깅"""
        state = self.market_state

        # 조건별 이모지
        condition_emoji = {
            'crash': '🔴💥',
            'strong_bearish': '🔴',
            'bearish': '🟠',
            'neutral': '⚪',
            'bullish': '🟢',
            'strong_bullish': '🟢🚀',
            'surge': '🟡⚡',
        }

        emoji = condition_emoji.get(state['condition'], '⚪')

        logger.info(f"")
        logger.info(f"{'='*50}")
        logger.info(f"{emoji} 실시간 시장 분석")
        logger.info(f"{'='*50}")
        logger.info(f"  상황: {state['condition'].upper()}")
        logger.info(f"  변동성: {state['volatility']}")
        logger.info(f"  모멘텀: {state['momentum']}")
        logger.info(f"  추세강도: {state['trend_strength']:+.1f}")
        logger.info(f"  급변감지: {'⚠️ YES' if state['rapid_change'] else 'NO'}")
        logger.info(f"  📊 점수조정: {state['score_adjustment']:+.1f}")
        logger.info(f"{'='*50}")

    def get_market_state(self, trading_pairs):
        """🆕 대시보드용 시장 상태 반환 (analyze 래퍼)"""
        self.analyze(trading_pairs)

        return {
            'state': self.market_state.get('condition', 'neutral'),
            'score_adjustment': self.market_state.get('score_adjustment', 0),
            'position_multiplier': self.get_position_size_multiplier(),
            'rapid_change': self.market_state.get('details', {}).get('mtf_score', 0) * 0.01,
            'volatility': self.market_state.get('details', {}).get('volatility_ratio', 0) * 0.01,
            'momentum': self.market_state.get('momentum', 'neutral'),
            'trend_strength': self.market_state.get('trend_strength', 0),
        }

    def get_score_adjustment(self):
        """현재 점수 조정값 반환"""
        return self.market_state.get('score_adjustment', 0)

    def is_safe_to_enter(self):
        """진입 안전 여부 판단"""
        condition = self.market_state.get('condition', 'neutral')
        volatility = self.market_state.get('volatility', 'normal')

        # 진입 위험 상황
        dangerous = ['crash', 'strong_bearish']
        extreme_volatility = ['extreme']

        if condition in dangerous:
            return False, f"시장 상황 위험 ({condition})"
        if volatility in extreme_volatility:
            return False, f"변동성 극심 ({volatility})"

        return True, "진입 가능"

    def get_position_size_multiplier(self):
        """포지션 크기 배율 반환"""
        condition = self.market_state.get('condition', 'neutral')
        volatility = self.market_state.get('volatility', 'normal')

        # 기본 배율
        base = 1.0

        # 시장 상황별 배율
        condition_multipliers = {
            'crash': 0.3,
            'strong_bearish': 0.5,
            'bearish': 0.7,
            'neutral': 1.0,
            'bullish': 1.1,
            'strong_bullish': 1.2,
            'surge': 0.8,  # 급등 추격매수 방지
        }
        base *= condition_multipliers.get(condition, 1.0)

        # 변동성에 따른 조정
        if volatility == 'extreme':
            base *= 0.5
        elif volatility == 'high':
            base *= 0.7

        return round(base, 2)

    def should_close_positions(self):
        """긴급 청산 권고 여부"""
        condition = self.market_state.get('condition', 'neutral')
        rapid = self.market_state.get('rapid_change', False)

        if condition == 'crash' and rapid:
            return True, "급락장 감지 - 청산 권고"

        return False, ""

    def get_adaptive_stop_loss(self, base_stop_loss):
        """변동성 기반 동적 손절 조정"""
        volatility = self.market_state.get('volatility', 'normal')

        adjustments = {
            'low': 0.8,      # 변동성 낮으면 손절 타이트하게
            'normal': 1.0,
            'high': 1.3,     # 변동성 높으면 손절 여유있게
            'extreme': 1.5,
        }

        multiplier = adjustments.get(volatility, 1.0)
        return round(base_stop_loss * multiplier, 4)


# 싱글톤 인스턴스
_detector_instance = None

def get_rapid_detector():
    """싱글톤 인스턴스 반환"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = RapidMarketDetector()
    return _detector_instance
