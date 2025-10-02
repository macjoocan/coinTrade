# improved_strategy.py
import time
from collections import defaultdict
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# ⭐ market_condition_check 모듈 import
from market_condition_check import MarketAnalyzer

from config import (
    TRADING_PAIRS, 
    STRATEGY_CONFIG, 
    RISK_CONFIG,
    ADVANCED_CONFIG
)

logger = logging.getLogger(__name__)

class ImprovedStrategy:
    def __init__(self):
        self.min_profit_target = STRATEGY_CONFIG['min_profit_target']
        self.max_trades_per_day = STRATEGY_CONFIG['max_trades_per_day']
        self.min_hold_time = STRATEGY_CONFIG['min_hold_time']
        
        # 
        self.positions = {}
        self.last_trade_time = {}
        self.trade_count_today = 0
        self.consecutive_losses = 0
        
        # ⭐ MarketAnalyzer 인스턴스 생성
        self.market_analyzer = MarketAnalyzer()
        
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
    
    def can_exit_position(self, symbol, force_stop_loss=False):
        """포지션 청산 가능 여부"""
        
        # 손절이면 시간 무시
        if force_stop_loss:
            logger.warning(f"{symbol}: 손절 강제 실행 (보유시간 무시)")
            return True
        
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
        """진입 조건 점수 계산 (더 엄격한 버전)"""
        score = 0
        details = []
        
        # 1. 추세 조건 (최대 3점) - 기준 강화
        sma_20 = indicators.get('sma_20', 0)
        sma_50 = indicators.get('sma_50', 0)
        price = indicators.get('price', 0)
        
        if sma_20 > sma_50 and price > sma_20:
            score += 2.5
            details.append("강한 상승 추세 (+2.5)")
        elif sma_20 > sma_50:
            score += 1.5
            details.append("상승 추세 (+1.5)")
        elif price > sma_20:
            score += 0.5
            details.append("단기 상승 (+0.5)")
        
        # 2. RSI 조건 (최대 3점) - 범위 조정
        rsi = indicators.get('rsi', 50)
        if 30 < rsi < 40:  # 과매도 영역
            score += 3
            details.append(f"RSI 과매도 반등 ({rsi:.1f}) (+3)")
        elif 40 < rsi < 50:  # 적정 매수 구간
            score += 2
            details.append(f"RSI 적정 ({rsi:.1f}) (+2)")
        elif 50 < rsi < 60:  # 중립
            score += 1
            details.append(f"RSI 중립 ({rsi:.1f}) (+1)")
        # 극단적 RSI는 점수 없음
        
        # 3. MACD 조건 (최대 2점)
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_diff = macd - macd_signal
        
        if macd_diff > 0 and macd > 0:
            score += 2
            details.append("MACD 강세 (+2)")
        elif macd_diff > 0:
            score += 1.5
            details.append("MACD 양전환 (+1.5)")
        elif abs(macd_diff) < price * 0.0001:
            score += 0.5
            details.append("MACD 크로스 임박 (+0.5)")
        
        # 4. 볼륨 조건 (최대 2점) - 기준 강화
        volume_ratio = indicators.get('volume_ratio', 1.0)
        if volume_ratio > 1.5:
            score += 2
            details.append(f"거래량 급증 ({volume_ratio:.1f}x) (+2)")
        elif volume_ratio > 1.2:
            score += 1
            details.append(f"거래량 증가 ({volume_ratio:.1f}x) (+1)")
        # 평균 이하 거래량은 점수 없음
        
        # 5. 변동성 조건 (최대 2점)
        volatility = indicators.get('volatility', 0.02)
        if 0.01 < volatility < 0.02:  # 적정 변동성
            score += 2
            details.append(f"안정적 변동성 ({volatility:.3f}) (+2)")
        elif 0.02 <= volatility < 0.025:
            score += 1
            details.append(f"보통 변동성 ({volatility:.3f}) (+1)")
        # 높은 변동성은 점수 없음
        
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
        
    # improved_strategy.py에서 수정할 부분
    def should_enter_position(self, symbol, indicators):
        """포지션 진입 여부 결정"""
        
        # 1. 거래 빈도 체크
        if not self.can_trade_today():
            return False, "일일 거래 한도 초과"
        
        # 2. 쿨다운 체크
        if self.is_in_cooldown(symbol):
            return False, "쿨다운 중 (30분 대기)"
        
        # 3. 연속 손실 체크
        if hasattr(self, 'consecutive_losses') and self.consecutive_losses >= 2:
            return False, f"연속 손실 {self.consecutive_losses}회 - 거래 일시 중단"
        
        # 4. 시장 상황 분석
        market_condition = self.market_analyzer.analyze_market(TRADING_PAIRS)
        
        # 5. 진입 점수 계산
        score, details = self.calculate_entry_score(indicators)
        
        # 6. 시장 상황에 따른 기준 조정
        base_threshold = ADVANCED_CONFIG.get('entry_score_threshold', 6)
        
        if market_condition == 'bearish':
            adjusted_threshold = base_threshold + 1.0  # 베어장: 기준 상향
        elif market_condition == 'bullish':
            adjusted_threshold = base_threshold - 0.5  # 불장: 기준 완화
        else:
            adjusted_threshold = base_threshold
        
        # 7. 최종 판단
        if score >= adjusted_threshold:
            return True, f"진입 조건 충족 (점수: {score:.1f}/{adjusted_threshold:.1f}, 시장: {market_condition})"
        
        return False, f"진입 조건 미충족 (점수: {score:.1f}/{adjusted_threshold:.1f})"
    
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