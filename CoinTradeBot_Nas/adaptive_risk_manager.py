# adaptive_risk_manager.py - ATR 기반 동적 손절/익절 + 마켓 레짐 감지
# v1.0.0 - 자동 파라미터 조절 시스템

import pyupbit
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)


class AdaptiveRiskManager:
    """
    ATR 기반 동적 손절/익절 관리자
    - ATR (Average True Range) 기반 손절/익절 자동 조절
    - 변동성 레벨에 따른 파라미터 동적 조정
    - 마켓 레짐 연동
    """

    def __init__(self, config=None):
        self.config = config or {}

        # ATR 설정
        self.atr_period = self.config.get('atr_period', 14)
        self.atr_multiplier_stop = self.config.get('atr_multiplier_stop', 1.5)  # 손절: ATR * 1.5
        self.atr_multiplier_take = self.config.get('atr_multiplier_take', 2.5)  # 익절: ATR * 2.5

        # 손절/익절 제한 (안전장치)
        self.min_stop_loss = self.config.get('min_stop_loss', 0.008)   # 최소 0.8%
        self.max_stop_loss = self.config.get('max_stop_loss', 0.030)   # 최대 3.0%
        self.min_take_profit = self.config.get('min_take_profit', 0.015)  # 최소 1.5%
        self.max_take_profit = self.config.get('max_take_profit', 0.080)  # 최대 8.0%

        # 캐시
        self._atr_cache = {}
        self._cache_duration = 300  # 5분 캐시

        # 히스토리
        self.atr_history = {}  # 심볼별 ATR 기록

        logger.info("=" * 60)
        logger.info("ATR 기반 동적 리스크 관리자 초기화")
        logger.info("=" * 60)
        logger.info(f"  ATR 기간: {self.atr_period}")
        logger.info(f"  손절 배수: ATR x {self.atr_multiplier_stop}")
        logger.info(f"  익절 배수: ATR x {self.atr_multiplier_take}")
        logger.info(f"  손절 범위: {self.min_stop_loss:.1%} ~ {self.max_stop_loss:.1%}")
        logger.info(f"  익절 범위: {self.min_take_profit:.1%} ~ {self.max_take_profit:.1%}")
        logger.info("=" * 60)

    def calculate_atr(self, symbol, interval='minute60', count=50):
        """
        ATR (Average True Range) 계산

        Args:
            symbol: 심볼 (예: 'BTC')
            interval: 봉 간격
            count: 데이터 개수

        Returns:
            atr: ATR 값 (가격 단위)
            atr_pct: ATR 비율 (%)
        """
        cache_key = f"{symbol}_{interval}"
        now = datetime.now()

        # 캐시 확인
        if cache_key in self._atr_cache:
            cached = self._atr_cache[cache_key]
            if (now - cached['time']).total_seconds() < self._cache_duration:
                return cached['atr'], cached['atr_pct']

        try:
            ticker = f"KRW-{symbol}"
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)

            if df is None or len(df) < self.atr_period + 1:
                logger.warning(f"{symbol}: ATR 계산을 위한 데이터 부족")
                return None, None

            # True Range 계산
            high = df['high']
            low = df['low']
            close = df['close']

            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))

            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # ATR 계산 (EMA 방식)
            atr = true_range.ewm(span=self.atr_period, adjust=False).mean().iloc[-1]

            # 현재가 대비 비율
            current_price = close.iloc[-1]
            atr_pct = atr / current_price

            # 캐시 저장
            self._atr_cache[cache_key] = {
                'time': now,
                'atr': atr,
                'atr_pct': atr_pct,
                'current_price': current_price
            }

            # 히스토리 저장
            if symbol not in self.atr_history:
                self.atr_history[symbol] = deque(maxlen=100)
            self.atr_history[symbol].append({
                'time': now,
                'atr': atr,
                'atr_pct': atr_pct
            })

            return atr, atr_pct

        except Exception as e:
            logger.error(f"{symbol} ATR 계산 실패: {e}")
            return None, None

    def get_dynamic_stop_loss(self, symbol, base_stop_loss=0.015, market_regime=None):
        """
        ATR 기반 동적 손절 계산

        Args:
            symbol: 심볼
            base_stop_loss: 기본 손절 (fallback)
            market_regime: 마켓 레짐 정보 (dict)

        Returns:
            dynamic_stop_loss: 조정된 손절 비율
        """
        atr, atr_pct = self.calculate_atr(symbol)

        if atr_pct is None:
            logger.info(f"{symbol}: ATR 데이터 없음, 기본 손절 {base_stop_loss:.2%} 사용")
            return base_stop_loss

        # ATR 기반 손절 계산
        atr_stop = atr_pct * self.atr_multiplier_stop

        # 마켓 레짐에 따른 조정
        regime_multiplier = 1.0
        if market_regime:
            regime = market_regime.get('regime', 'NORMAL')
            if regime == 'HIGH_VOLATILITY':
                regime_multiplier = 1.3  # 변동성 높을 때 손절 넓게
            elif regime == 'TRENDING':
                regime_multiplier = 1.1  # 추세장에서 약간 넓게
            elif regime == 'RANGING':
                regime_multiplier = 0.9  # 횡보장에서 타이트하게

        adjusted_stop = atr_stop * regime_multiplier

        # 범위 제한 적용
        final_stop = np.clip(adjusted_stop, self.min_stop_loss, self.max_stop_loss)

        logger.info(f"{symbol} 동적 손절 계산:")
        logger.info(f"  ATR: {atr_pct:.3%} x {self.atr_multiplier_stop} = {atr_stop:.3%}")
        if market_regime:
            logger.info(f"  레짐 조정: x{regime_multiplier:.1f} ({market_regime.get('regime', 'NORMAL')})")
        logger.info(f"  최종 손절: {final_stop:.2%}")

        return final_stop

    def get_dynamic_take_profit(self, symbol, base_take_profit=0.030, market_regime=None):
        """
        ATR 기반 동적 익절 계산

        Args:
            symbol: 심볼
            base_take_profit: 기본 익절 (fallback)
            market_regime: 마켓 레짐 정보

        Returns:
            dynamic_take_profit: 조정된 익절 비율
        """
        atr, atr_pct = self.calculate_atr(symbol)

        if atr_pct is None:
            logger.info(f"{symbol}: ATR 데이터 없음, 기본 익절 {base_take_profit:.2%} 사용")
            return base_take_profit

        # ATR 기반 익절 계산
        atr_take = atr_pct * self.atr_multiplier_take

        # 마켓 레짐에 따른 조정
        regime_multiplier = 1.0
        if market_regime:
            regime = market_regime.get('regime', 'NORMAL')
            if regime == 'TRENDING':
                regime_multiplier = 1.3  # 추세장에서 익절 늘림 (더 큰 수익 노리기)
            elif regime == 'HIGH_VOLATILITY':
                regime_multiplier = 1.2  # 변동성 높을 때 익절 약간 늘림
            elif regime == 'RANGING':
                regime_multiplier = 0.8  # 횡보장에서 익절 빨리

        adjusted_take = atr_take * regime_multiplier

        # 범위 제한 적용
        final_take = np.clip(adjusted_take, self.min_take_profit, self.max_take_profit)

        logger.info(f"{symbol} 동적 익절 계산:")
        logger.info(f"  ATR: {atr_pct:.3%} x {self.atr_multiplier_take} = {atr_take:.3%}")
        if market_regime:
            logger.info(f"  레짐 조정: x{regime_multiplier:.1f} ({market_regime.get('regime', 'NORMAL')})")
        logger.info(f"  최종 익절: {final_take:.2%}")

        return final_take

    def get_dynamic_risk_params(self, symbol, market_regime=None):
        """
        종합 동적 리스크 파라미터 반환

        Returns:
            dict: {
                'stop_loss': 동적 손절,
                'take_profit': 동적 익절,
                'risk_reward_ratio': 손익비,
                'atr_pct': ATR 비율,
                'regime': 마켓 레짐
            }
        """
        stop_loss = self.get_dynamic_stop_loss(symbol, market_regime=market_regime)
        take_profit = self.get_dynamic_take_profit(symbol, market_regime=market_regime)

        risk_reward = take_profit / stop_loss if stop_loss > 0 else 0

        atr, atr_pct = self.calculate_atr(symbol)

        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward_ratio': round(risk_reward, 2),
            'atr_pct': atr_pct or 0,
            'regime': market_regime.get('regime', 'NORMAL') if market_regime else 'NORMAL'
        }

    def get_position_size_by_risk(self, symbol, account_balance, risk_per_trade=0.02, market_regime=None):
        """
        ATR 기반 포지션 사이징 (리스크 기반)

        Args:
            symbol: 심볼
            account_balance: 계좌 잔고
            risk_per_trade: 거래당 리스크 비율 (기본 2%)
            market_regime: 마켓 레짐

        Returns:
            position_size: 포지션 금액
        """
        stop_loss = self.get_dynamic_stop_loss(symbol, market_regime=market_regime)

        # 리스크 금액 = 계좌 잔고 * 거래당 리스크
        risk_amount = account_balance * risk_per_trade

        # 포지션 크기 = 리스크 금액 / 손절 비율
        position_size = risk_amount / stop_loss if stop_loss > 0 else 0

        # 최대 포지션 제한 (계좌의 20%)
        max_position = account_balance * 0.20
        position_size = min(position_size, max_position)

        logger.info(f"{symbol} 리스크 기반 포지션 사이징:")
        logger.info(f"  계좌 잔고: {account_balance:,.0f}")
        logger.info(f"  리스크 금액: {risk_amount:,.0f} ({risk_per_trade:.1%})")
        logger.info(f"  손절 비율: {stop_loss:.2%}")
        logger.info(f"  포지션 크기: {position_size:,.0f}")

        return position_size

    def get_atr_status(self, symbol):
        """ATR 상태 반환 (대시보드용)"""
        atr, atr_pct = self.calculate_atr(symbol)

        if atr_pct is None:
            return {
                'symbol': symbol,
                'atr_pct': None,
                'level': 'unknown',
                'stop_loss': self.min_stop_loss,
                'take_profit': self.min_take_profit
            }

        # ATR 레벨 판정
        if atr_pct < 0.015:
            level = 'low'
        elif atr_pct < 0.025:
            level = 'normal'
        elif atr_pct < 0.040:
            level = 'high'
        else:
            level = 'extreme'

        return {
            'symbol': symbol,
            'atr_pct': atr_pct,
            'level': level,
            'stop_loss': self.get_dynamic_stop_loss(symbol),
            'take_profit': self.get_dynamic_take_profit(symbol)
        }


class MarketRegimeDetector:
    """
    마켓 레짐 감지 시스템
    - HIGH_VOLATILITY: 고변동성 (포지션 축소, 넓은 손절)
    - TRENDING: 추세장 (추세 추종, 트레일링 스탑 활성화)
    - RANGING: 횡보장 (보수적 진입, 빠른 익절)
    """

    def __init__(self, config=None):
        self.config = config or {}

        # 감지 설정
        self.volatility_lookback = self.config.get('volatility_lookback', 24)  # 24시간
        self.trend_lookback = self.config.get('trend_lookback', 48)  # 48시간
        self.adx_period = self.config.get('adx_period', 14)

        # 임계값
        self.high_volatility_threshold = self.config.get('high_volatility_threshold', 0.035)  # 3.5%
        self.trend_strength_threshold = self.config.get('trend_strength_threshold', 25)  # ADX 25
        self.trend_price_threshold = self.config.get('trend_price_threshold', 0.03)  # 3% 추세

        # 캐시
        self._regime_cache = {}
        self._cache_duration = 300  # 5분

        # 레짐 히스토리
        self.regime_history = deque(maxlen=100)

        logger.info("=" * 60)
        logger.info("마켓 레짐 감지 시스템 초기화")
        logger.info("=" * 60)
        logger.info(f"  변동성 관찰 기간: {self.volatility_lookback}시간")
        logger.info(f"  추세 관찰 기간: {self.trend_lookback}시간")
        logger.info(f"  고변동성 임계값: {self.high_volatility_threshold:.1%}")
        logger.info(f"  추세 강도 임계값: ADX > {self.trend_strength_threshold}")
        logger.info("=" * 60)

    def detect_regime(self, trading_pairs):
        """
        현재 마켓 레짐 감지

        Args:
            trading_pairs: 분석할 심볼 리스트

        Returns:
            dict: {
                'regime': 'HIGH_VOLATILITY' | 'TRENDING' | 'RANGING',
                'confidence': 신뢰도 (0~1),
                'volatility': 평균 변동성,
                'trend_strength': 추세 강도,
                'details': 세부 정보
            }
        """
        cache_key = ','.join(sorted(trading_pairs[:3]))
        now = datetime.now()

        # 캐시 확인
        if cache_key in self._regime_cache:
            cached = self._regime_cache[cache_key]
            if (now - cached['time']).total_seconds() < self._cache_duration:
                return cached['regime']

        try:
            volatility_data = self._analyze_volatility(trading_pairs)
            trend_data = self._analyze_trend(trading_pairs)

            # 레짐 결정
            regime, confidence = self._determine_regime(volatility_data, trend_data)

            result = {
                'regime': regime,
                'confidence': confidence,
                'volatility': volatility_data['avg_volatility'],
                'trend_strength': trend_data['avg_strength'],
                'trend_direction': trend_data['direction'],
                'details': {
                    'volatility_level': volatility_data['level'],
                    'adx': trend_data['avg_adx'],
                    'price_change': trend_data['avg_change'],
                    'coins_analyzed': len(trading_pairs)
                },
                'timestamp': now
            }

            # 캐시 저장
            self._regime_cache[cache_key] = {
                'time': now,
                'regime': result
            }

            # 히스토리 저장
            self.regime_history.append(result)

            # 로깅
            self._log_regime(result)

            return result

        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
            return {
                'regime': 'NORMAL',
                'confidence': 0,
                'volatility': 0,
                'trend_strength': 0,
                'details': {}
            }

    def _analyze_volatility(self, coins):
        """변동성 분석"""
        volatilities = []

        for coin in coins[:5]:  # 상위 5개만
            try:
                ticker = f"KRW-{coin}"
                df = pyupbit.get_ohlcv(ticker, interval='minute60', count=self.volatility_lookback + 1)

                if df is None or len(df) < 14:
                    continue

                # ATR 기반 변동성
                high = df['high']
                low = df['low']
                close = df['close']

                tr = pd.concat([
                    high - low,
                    abs(high - close.shift(1)),
                    abs(low - close.shift(1))
                ], axis=1).max(axis=1)

                atr = tr.rolling(14).mean().iloc[-1]
                volatility = atr / close.iloc[-1]

                volatilities.append(volatility)

            except Exception as e:
                logger.debug(f"{coin} 변동성 분석 실패: {e}")
                continue

        if not volatilities:
            return {'avg_volatility': 0.02, 'level': 'normal'}

        avg_vol = np.mean(volatilities)

        # 변동성 레벨 판정
        if avg_vol >= self.high_volatility_threshold:
            level = 'high'
        elif avg_vol >= 0.02:
            level = 'normal'
        else:
            level = 'low'

        return {
            'avg_volatility': avg_vol,
            'level': level,
            'max_volatility': max(volatilities),
            'min_volatility': min(volatilities)
        }

    def _analyze_trend(self, coins):
        """추세 분석 (ADX + 가격 변화)"""
        adx_values = []
        price_changes = []
        trend_directions = []

        for coin in coins[:5]:
            try:
                ticker = f"KRW-{coin}"
                df = pyupbit.get_ohlcv(ticker, interval='minute60', count=self.trend_lookback + 1)

                if df is None or len(df) < 30:
                    continue

                # ADX 계산
                adx = self._calculate_adx(df)
                adx_values.append(adx)

                # 가격 변화율
                price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
                price_changes.append(price_change)

                # 추세 방향
                if price_change > 0.02:
                    trend_directions.append(1)
                elif price_change < -0.02:
                    trend_directions.append(-1)
                else:
                    trend_directions.append(0)

            except Exception as e:
                logger.debug(f"{coin} 추세 분석 실패: {e}")
                continue

        if not adx_values:
            return {'avg_adx': 20, 'avg_strength': 0, 'avg_change': 0, 'direction': 'neutral'}

        avg_adx = np.mean(adx_values)
        avg_change = np.mean(price_changes)
        avg_direction = np.mean(trend_directions)

        # 추세 방향 판정
        if avg_direction > 0.5:
            direction = 'bullish'
        elif avg_direction < -0.5:
            direction = 'bearish'
        else:
            direction = 'neutral'

        return {
            'avg_adx': avg_adx,
            'avg_strength': avg_adx,
            'avg_change': avg_change,
            'direction': direction
        }

    def _calculate_adx(self, df):
        """ADX (Average Directional Index) 계산"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']

            # +DM, -DM 계산
            plus_dm = high.diff()
            minus_dm = -low.diff()

            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

            # True Range
            tr = pd.concat([
                high - low,
                abs(high - close.shift(1)),
                abs(low - close.shift(1))
            ], axis=1).max(axis=1)

            # Smoothed values (14일)
            atr = tr.rolling(self.adx_period).mean()
            plus_di = 100 * (plus_dm.rolling(self.adx_period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(self.adx_period).mean() / atr)

            # DX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)

            # ADX (DX의 이동평균)
            adx = dx.rolling(self.adx_period).mean().iloc[-1]

            return adx if not np.isnan(adx) else 20

        except Exception as e:
            logger.debug(f"ADX 계산 실패: {e}")
            return 20

    def _determine_regime(self, volatility_data, trend_data):
        """레짐 최종 결정"""
        vol_level = volatility_data['level']
        adx = trend_data['avg_adx']
        price_change = abs(trend_data['avg_change'])

        # 1. 고변동성 체크 (우선)
        if vol_level == 'high':
            confidence = min(1.0, volatility_data['avg_volatility'] / self.high_volatility_threshold)
            return 'HIGH_VOLATILITY', confidence

        # 2. 추세장 체크
        if adx >= self.trend_strength_threshold or price_change >= self.trend_price_threshold:
            confidence = min(1.0, max(adx / 40, price_change / 0.05))
            return 'TRENDING', confidence

        # 3. 횡보장
        confidence = 1.0 - (adx / 50)  # ADX 낮을수록 횡보 신뢰도 높음
        return 'RANGING', max(0.3, confidence)

    def _log_regime(self, result):
        """레짐 변화 로깅"""
        regime = result['regime']
        confidence = result['confidence']

        emoji = {
            'HIGH_VOLATILITY': '🔥',
            'TRENDING': '📈',
            'RANGING': '↔️'
        }.get(regime, '⚪')

        logger.info("")
        logger.info("=" * 50)
        logger.info(f"{emoji} 마켓 레짐: {regime}")
        logger.info("=" * 50)
        logger.info(f"  신뢰도: {confidence:.1%}")
        logger.info(f"  변동성: {result['volatility']:.2%}")
        logger.info(f"  추세 강도: {result['trend_strength']:.1f}")
        logger.info(f"  추세 방향: {result['trend_direction']}")
        logger.info("=" * 50)

    def get_strategy_adjustments(self, regime_result=None, trading_pairs=None):
        """
        레짐에 따른 전략 조정값 반환

        Returns:
            dict: 전략 조정 파라미터
        """
        if regime_result is None and trading_pairs:
            regime_result = self.detect_regime(trading_pairs)

        regime = regime_result.get('regime', 'NORMAL') if regime_result else 'NORMAL'

        adjustments = {
            'HIGH_VOLATILITY': {
                'position_size_mult': 0.5,      # 포지션 50% 축소
                'stop_loss_mult': 1.3,          # 손절 30% 넓게
                'take_profit_mult': 1.2,        # 익절 20% 넓게
                'entry_score_adj': 1.5,         # 진입 기준 상향
                'trailing_stop_enabled': True,
                'description': '고변동성 - 보수적 접근'
            },
            'TRENDING': {
                'position_size_mult': 1.1,      # 포지션 10% 증가
                'stop_loss_mult': 1.1,          # 손절 약간 넓게
                'take_profit_mult': 1.5,        # 익절 50% 넓게 (추세 탐)
                'entry_score_adj': -0.5,        # 진입 기준 하향
                'trailing_stop_enabled': True,
                'description': '추세장 - 추세 추종'
            },
            'RANGING': {
                'position_size_mult': 0.8,      # 포지션 20% 축소
                'stop_loss_mult': 0.9,          # 손절 타이트
                'take_profit_mult': 0.7,        # 익절 빠르게
                'entry_score_adj': 0.5,         # 진입 기준 약간 상향
                'trailing_stop_enabled': False,
                'description': '횡보장 - 보수적 진입, 빠른 익절'
            }
        }

        default = {
            'position_size_mult': 1.0,
            'stop_loss_mult': 1.0,
            'take_profit_mult': 1.0,
            'entry_score_adj': 0,
            'trailing_stop_enabled': True,
            'description': '기본 모드'
        }

        return adjustments.get(regime, default)

    def get_regime_status(self, trading_pairs):
        """레짐 상태 반환 (대시보드용)"""
        result = self.detect_regime(trading_pairs)

        emoji = {
            'HIGH_VOLATILITY': '🔥',
            'TRENDING': '📈',
            'RANGING': '↔️'
        }.get(result['regime'], '⚪')

        return {
            'regime': result['regime'],
            'emoji': emoji,
            'confidence': result['confidence'],
            'volatility': result['volatility'],
            'trend_strength': result['trend_strength'],
            'trend_direction': result.get('trend_direction', 'neutral'),
            'adjustments': self.get_strategy_adjustments(result)
        }


# 싱글톤 인스턴스
_adaptive_risk_instance = None
_regime_detector_instance = None


def get_adaptive_risk_manager(config=None):
    """AdaptiveRiskManager 싱글톤"""
    global _adaptive_risk_instance
    if _adaptive_risk_instance is None:
        _adaptive_risk_instance = AdaptiveRiskManager(config)
    return _adaptive_risk_instance


def get_regime_detector(config=None):
    """MarketRegimeDetector 싱글톤"""
    global _regime_detector_instance
    if _regime_detector_instance is None:
        _regime_detector_instance = MarketRegimeDetector(config)
    return _regime_detector_instance
