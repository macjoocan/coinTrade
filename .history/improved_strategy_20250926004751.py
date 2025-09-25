# improved_strategy.py

import time
from datetime import datetime, timedelta
from collections import defaultdict
from config import STRATEGY_CONFIG
import logging

logger = logging.getLogger(__name__)

class ImprovedStrategy:
    def __init__(self):
        self.min_profit_target = STRATEGY_CONFIG['min_profit_target']
        self.max_trades_per_day = STRATEGY_CONFIG['max_trades_per_day']
        self.min_hold_time = STRATEGY_CONFIG['min_hold_time']
        
        # 거래 추적용
        self.daily_trades = defaultdict(int)
        self.position_entry_time = {}
        self.trade_cooldown = {}  # 종목별 쿨다운
        
        # 진입 조건 점수
        self.entry_score_threshold = 7  # 7점 이상일 때만 진입
        
    def can_trade_today(self):
        """오늘 거래 가능한지 확인"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.daily_trades[today] < self.max_trades_per_day
    
    def can_exit_position(self, symbol):
        """포지션 청산 가능한지 확인 (최소 보유시간 체크)"""
        if symbol not in self.position_entry_time:
            return True
        
        elapsed_time = time.time() - self.position_entry_time[symbol]
        return elapsed_time >= self.min_hold_time
    
    def is_in_cooldown(self, symbol):
        """종목별 쿨다운 체크 (연속 거래 방지)"""
        if symbol not in self.trade_cooldown:
            return False
        
        cooldown_time = 1800  # 30분 쿨다운
        elapsed = time.time() - self.trade_cooldown[symbol]
        return elapsed < cooldown_time
    
    # def calculate_entry_score(self, indicators):
    #     """진입 조건 점수 계산 (강화된 버전)"""
    #     score = 0
    #     details = []
        
    #     # 1. 추세 조건 (최대 3점)
    #     if indicators.get('sma_20', 0) > indicators.get('sma_50', 0):
    #         score += 2
    #         details.append("상승 추세 (+2)")
        
    #     if indicators.get('price', 0) > indicators.get('sma_20', 0):
    #         score += 1
    #         details.append("단기 이평선 상향 돌파 (+1)")
        
    #     # 2. RSI 조건 (최대 2점)
    #     rsi = indicators.get('rsi', 50)
    #     if 30 < rsi < 40:  # 과매도 영역에서 반등
    #         score += 2
    #         details.append(f"RSI 과매도 반등 신호 ({rsi:.1f}) (+2)")
    #     elif 40 < rsi < 60:  # 중립 구간
    #         score += 1
    #         details.append(f"RSI 중립 ({rsi:.1f}) (+1)")
        
    #     # 3. MACD 조건 (최대 2점)
    #     if indicators.get('macd', 0) > indicators.get('macd_signal', 0):
    #         score += 2
    #         details.append("MACD 골든크로스 (+2)")
        
    #     # 4. 볼륨 조건 (최대 2점)
    #     volume_ratio = indicators.get('volume_ratio', 1.0)
    #     if volume_ratio > 1.5:
    #         score += 2
    #         details.append(f"거래량 급증 ({volume_ratio:.1f}x) (+2)")
    #     elif volume_ratio > 1.2:
    #         score += 1
    #         details.append(f"거래량 증가 ({volume_ratio:.1f}x) (+1)")
        
    #     # 5. 변동성 조건 (최대 2점)
    #     volatility = indicators.get('volatility', 0.02)
    #     if volatility < 0.015:  # 저변동성
    #         score += 2
    #         details.append(f"안정적 변동성 ({volatility:.3f}) (+2)")
    #     elif volatility < 0.025:
    #         score += 1
    #         details.append(f"적정 변동성 ({volatility:.3f}) (+1)")
        
    #     # 6. 수익률 기대치 (최대 1점)
    #     expected_return = indicators.get('expected_return', 0)
    #     if expected_return > 0.02:  # 2% 이상 기대
    #         score += 1
    #         details.append(f"기대 수익률 양호 ({expected_return:.1%}) (+1)")
        
    #     logger.info(f"진입 점수: {score}/12 - {', '.join(details)}")
        
    #     return score, details

    def calculate_entry_score(self, indicators):
        """진입 조건 점수 계산 (완화된 버전)"""
        score = 0
        details = []
        
        # 1. 추세 조건 (최대 3점) - 기준 완화
        if indicators.get('sma_20', 0) > indicators.get('sma_50', 0):
            score += 1.5  # 2 → 1.5
            details.append("상승 추세 (+1.5)")
        
        if abs(indicators.get('price', 0) - indicators.get('sma_20', 0)) / indicators.get('sma_20', 1) < 0.02:
            score += 1  # 이평선 근처면 점수
            details.append("이평선 근접 (+1)")
        
        # 2. RSI 조건 (최대 3점) - 범위 확대
        rsi = indicators.get('rsi', 50)
        if 25 < rsi < 45:  # 과매도 영역 확대
            score += 2
            details.append(f"RSI 매수 구간 ({rsi:.1f}) (+2)")
        elif 45 < rsi < 65:  # 중립 구간 확대
            score += 1.5
            details.append(f"RSI 중립 ({rsi:.1f}) (+1.5)")
        elif rsi <= 25:  # 극단적 과매도
            score += 3
            details.append(f"RSI 극과매도 ({rsi:.1f}) (+3)")
        
        # 3. MACD 조건 (최대 2점) - 조건 완화
        macd_diff = indicators.get('macd', 0) - indicators.get('macd_signal', 0)
        if macd_diff > 0:
            score += 1.5
            details.append("MACD 양전환 (+1.5)")
        elif abs(macd_diff) < indicators.get('price', 1) * 0.0001:  # 크로스 임박
            score += 1
            details.append("MACD 크로스 임박 (+1)")
        
        # 4. 볼륨 조건 (최대 2점) - 기준 완화
        volume_ratio = indicators.get('volume_ratio', 1.0)
        if volume_ratio > 1.2:  # 1.5 → 1.2
            score += 1.5
            details.append(f"거래량 증가 ({volume_ratio:.1f}x) (+1.5)")
        elif volume_ratio > 0.8:  # 평균 수준이어도 점수
            score += 0.5
            details.append(f"거래량 정상 ({volume_ratio:.1f}x) (+0.5)")
        
        # 5. 변동성 보너스 (최대 2점)
        volatility = indicators.get('volatility', 0.02)
        if 0.01 < volatility < 0.03:  # 적정 변동성
            score += 1
            details.append(f"적정 변동성 ({volatility:.3f}) (+1)")
        
        # 6. 모멘텀 보너스 (추가 점수)
        momentum = indicators.get('momentum', 0)
        if momentum > 0:
            score += 0.5
            details.append(f"양의 모멘텀 (+0.5)")
        
        logger.info(f"진입 점수: {score:.1f}/12 - {', '.join(details)}")
        
        return score, details
    
    # def should_enter_position(self, symbol, indicators):
    #     """포지션 진입 여부 결정 (강화된 조건)"""
    #     # 1. 거래 빈도 체크
    #     if not self.can_trade_today():
    #         return False, "일일 거래 한도 초과"
        
    #     # 2. 쿨다운 체크
    #     if self.is_in_cooldown(symbol):
    #         return False, "쿨다운 중"
        
    #     # 3. 진입 점수 계산
    #     score, details = self.calculate_entry_score(indicators)
        
    #     # 4. 최소 점수 체크
    #     if score < self.entry_score_threshold:
    #         return False, f"진입 조건 미충족 (점수: {score}/{self.entry_score_threshold})"
        
    #     # 5. 예상 수익률 체크
    #     expected_return = indicators.get('expected_return', 0)
    #     if expected_return < self.min_profit_target:
    #         return False, f"예상 수익률 부족 ({expected_return:.1%})"
        
    #     return True, f"진입 조건 충족 (점수: {score})"

    def _check_market_condition(self, indicators):
        """시장 상황 평가 (추가 메서드)"""
        trend = indicators.get('trend', 'sideways')
        volatility = indicators.get('volatility', 0.02)
        
        # 시장 상황 분류
        if trend in ['strong_up', 'up'] and volatility < 0.025:
            return "bullish"  # 상승 추세 + 안정적
        elif trend == 'down' or volatility > 0.03:
            return "bearish"  # 하락 추세 또는 높은 변동성
        else:
            return "neutral"  # 중립

    def should_enter_position(self, symbol, indicators):
        """포지션 진입 여부 결정 (강화된 조건)"""
        
        # 1. 거래 빈도 체크
        if not self.can_trade_today():
            return False, "일일 거래 한도 초과"
        
        # 2. 쿨다운 체크 (무조건 적용)
        if self.is_in_cooldown(symbol):
            # strong_signal 체크 제거 - 쿨다운은 무조건 지켜야 함
            return False, "쿨다운 중 (30분 대기)"
        
        # 3. 연속 손실 체크 (추가)
        if hasattr(self, 'consecutive_losses'):
            if self.consecutive_losses >= 2:
                return False, f"연속 손실 {self.consecutive_losses}회 - 거래 일시 중단"
        
        # 4. 진입 점수 계산
        score, details = self.calculate_entry_score(indicators)
        
        # 5. 시장 상황 체크 (추가)
        market_condition = self._check_market_condition(indicators)
        
        # 6. 다단계 진입 전략 (더 엄격하게)
        from config import ADVANCED_CONFIG
        
        # 매우 강한 신호 (점수 9 이상 + 시장 상황 양호)
        if score >= 9 and market_condition == "bullish":
            return True, f"매우 강한 매수 신호! (점수: {score:.1f})"
        
        # 강한 신호 (점수 7 이상 + RSI 조건)
        elif score >= 7:
            rsi = indicators.get('rsi', 50)
            if 30 < rsi < 60:  # RSI가 극단적이지 않을 때
                return True, f"강한 진입 신호 (점수: {score:.1f}, RSI: {rsi:.1f})"
            else:
                return False, f"점수는 충족하나 RSI 부적합 ({rsi:.1f})"
        
        # 일반 신호 (점수 6 이상 + 추가 조건)
        elif score >= ADVANCED_CONFIG.get('entry_score_threshold', 6):
            rsi = indicators.get('rsi', 50)
            volume_ratio = indicators.get('volume_ratio', 1.0)
            
            # RSI와 거래량 모두 확인
            if 35 < rsi < 55 and volume_ratio > 1.2:
                return True, f"진입 조건 충족 (점수: {score:.1f}, RSI: {rsi:.1f}, Vol: {volume_ratio:.1f}x)"
            else:
                return False, f"보조 지표 미충족 (RSI: {rsi:.1f}, Vol: {volume_ratio:.1f}x)"
        
        # 소액 포지션 진입 비활성화 (너무 위험)
        # 아래 코드는 주석 처리
        """
        elif score >= ADVANCED_CONFIG.get('min_score_for_small_position', 4):
            if indicators.get('rsi', 50) < 40:
                return True, f"소액 진입 가능 (점수: {score:.1f})"
        """
        
        return False, f"진입 조건 미충족 (점수: {score:.1f}/{ADVANCED_CONFIG.get('entry_score_threshold', 6)})"
    
    def record_trade(self, symbol, trade_type):
        """거래 기록"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_trades[today] += 1
        
        if trade_type == 'buy':
            self.position_entry_time[symbol] = time.time()
        elif trade_type == 'sell':
            if symbol in self.position_entry_time:
                del self.position_entry_time[symbol]
            # 매도 후 쿨다운 설정
            self.trade_cooldown[symbol] = time.time()
    
    def check_profit_target(self, entry_price, current_price):
        """최소 수익률 달성 여부 확인"""
        profit_rate = (current_price - entry_price) / entry_price
        return profit_rate >= self.min_profit_target
    
    def get_trade_statistics(self):
        """거래 통계 반환"""
        today = datetime.now().strftime('%Y-%m-%d')
        return {
            'trades_today': self.daily_trades[today],
            'trades_remaining': self.max_trades_per_day - self.daily_trades[today],
            'active_positions': len(self.position_entry_time),
            'cooldown_symbols': list(self.trade_cooldown.keys())
        }