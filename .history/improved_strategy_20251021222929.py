# improved_strategy.py (수정 버전)

import time
from collections import defaultdict
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from multi_timeframe_analyzer import MultiTimeframeAnalyzer
from ml_signal_generator import MLSignalGenerator
from market_condition_check import MarketAnalyzer

from config import (
    TRADING_PAIRS, 
    STRATEGY_CONFIG, 
    RISK_CONFIG,
    ADVANCED_CONFIG,
    MTF_CONFIG, 
    ML_CONFIG, 
    SIGNAL_INTEGRATION_CONFIG    
)

logger = logging.getLogger(__name__)

class ImprovedStrategy:
    def __init__(self):
        self.min_profit_target = STRATEGY_CONFIG['min_profit_target']
        self.max_trades_per_day = STRATEGY_CONFIG['max_trades_per_day']
        self.min_hold_time = STRATEGY_CONFIG['min_hold_time']
        
        self.positions = {}
        self.last_trade_time = {}
        self.trade_count_today = 0
        self.consecutive_losses = 0
        
        self.market_analyzer = MarketAnalyzer()
        
        self.daily_trades = defaultdict(int)
        self.position_entry_time = {}
        self.trade_cooldown = {}
        
        self.entry_score_threshold = ADVANCED_CONFIG.get('entry_score_threshold', 6)
        
        if SIGNAL_INTEGRATION_CONFIG['enabled']:
            self.signal_weights = SIGNAL_INTEGRATION_CONFIG['weights']
        else:
            self.signal_weights = {
                'technical': 0.35,
                'mtf': 0.35,
                'ml': 0.30
            }
        
        if MTF_CONFIG['enabled']:
            self.mtf_analyzer = MultiTimeframeAnalyzer()
            self.mtf_min_score = MTF_CONFIG['min_score']
            self.mtf_min_consensus = MTF_CONFIG['min_consensus']
        else:
            self.mtf_analyzer = None
        
        if ML_CONFIG['enabled']:
            self.ml_generator = MLSignalGenerator(
                model_type=ML_CONFIG['model_type']
            )
            self.ml_min_probability = ML_CONFIG['prediction']['min_buy_probability']
            self.ml_min_confidence = ML_CONFIG['prediction']['min_confidence']
            
            if not self.ml_generator.is_trained:
                logger.info("🤖 ML 모델 초기 학습을 시작합니다...")
                self.ml_generator.train_model(TRADING_PAIRS)
        else:
            self.ml_generator = None
        
    def can_trade_today(self):
        """오늘 거래 가능한지 확인"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.daily_trades[today] < self.max_trades_per_day
    
    def can_exit_position(self, symbol, force_stop_loss=False):
        """포지션 청산 가능 여부"""
        if force_stop_loss:
            logger.warning(f"{symbol}: 손절 강제 실행 (보유시간 무시)")
            return True
        
        if symbol not in self.position_entry_time:
            return True
        
        elapsed_time = time.time() - self.position_entry_time[symbol]
        return elapsed_time >= self.min_hold_time
    
    def is_in_cooldown(self, symbol):
        """종목별 쿨다운 체크"""
        if symbol not in self.trade_cooldown:
            return False
        
        cooldown_time = 1800  # 30분
        elapsed = time.time() - self.trade_cooldown[symbol]
        return elapsed < cooldown_time
    
    def calculate_entry_score(self, indicators):
        """✅ 개선된 진입 점수 계산 - 상승장 대응"""
        score = 0
        details = []
        
        # 추세 조건
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
        
        # ✅ RSI 조건 - 상승장 대응 + 과매수 필터
        rsi = indicators.get('rsi', 50)
        
        if rsi < 30:
            score += 1.0
            details.append(f"RSI 과매도 ({rsi:.1f}) (+1.0)")
        
        elif 30 <= rsi < 40:
            score += 3.0  # 과매도 반등 (최고 점수)
            details.append(f"RSI 과매도 반등 ({rsi:.1f}) (+3.0)")
        
        elif 40 <= rsi < 50:
            score += 2.5  # 건강한 상승 준비
            details.append(f"RSI 건강한 수준 ({rsi:.1f}) (+2.5)")
        
        elif 50 <= rsi < 60:
            score += 2.0  # ✅ 상승 지속 (기존 1 → 2.0)
            details.append(f"RSI 상승 지속 ({rsi:.1f}) (+2.0)")
        
        elif 60 <= rsi < 65:
            score += 1.5  # ✅ 강세지만 괜찮음 (새로 추가)
            details.append(f"RSI 강세 ({rsi:.1f}) (+1.5)")
        
        elif 65 <= rsi < 70:
            score += 1.0  # ✅ 과매수 진입 (새로 추가)
            details.append(f"RSI 과매수 주의 ({rsi:.1f}) (+1.0)")
        
        elif rsi >= 70:
            score += 0.0  # ✅ 과매수 경고 - 진입 금지
            details.append(f"RSI 과매수 위험 ({rsi:.1f}) (+0.0)")
        
        # MACD 조건
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
        
        # 볼륨 조건
        volume_ratio = indicators.get('volume_ratio', 1.0)
        if volume_ratio > 1.5:
            score += 2
            details.append(f"거래량 급증 ({volume_ratio:.1f}x) (+2)")
        elif volume_ratio > 1.2:
            score += 1
            details.append(f"거래량 증가 ({volume_ratio:.1f}x) (+1)")
        
        # 변동성 조건
        volatility = indicators.get('volatility', 0.02)
        if 0.01 < volatility < 0.02:
            score += 2
            details.append(f"안정적 변동성 ({volatility:.3f}) (+2)")
        elif 0.02 <= volatility < 0.025:
            score += 1
            details.append(f"보통 변동성 ({volatility:.3f}) (+1)")
        
        return score, details
    
    def should_enter_position(self, symbol, indicators):
        """향상된 진입 판단 - 3가지 신호 통합"""
        
        # 1. 거래 빈도 체크
        if not self.can_trade_today():
            return False, "일일 거래 한도 초과"
        
        # 2. 쿨다운 체크
        if self.is_in_cooldown(symbol):
            return False, "쿨다운 중 (30분 대기)"
        
        # 3. 연속 손실 체크
        if hasattr(self, 'consecutive_losses') and self.consecutive_losses >= 2:
            return False, f"연속 손실 {self.consecutive_losses}회 - 거래 일시 중단"
        
        # ✅ 4. 과매수 필터 (RSI 70 이상이면 진입 금지)
        rsi = indicators.get('rsi', 50)
        if rsi >= 70:
            return False, f"RSI 과매수 ({rsi:.1f}) - 조정 대기"
        
        # 5. 멀티 신호 분석
        signal_scores = {}
        signal_details = {}
        
        # 5-1. 기존 기술적 분석
        tech_score, tech_details = self.calculate_entry_score(indicators)
        signal_scores['technical'] = tech_score / 12.0  # 정규화 (0~1)
        signal_details['technical'] = tech_details
        
        # 5-2. 멀티 타임프레임 분석
        if MTF_CONFIG['enabled'] and self.mtf_analyzer:
            try:
                mtf_result = self.mtf_analyzer.analyze(symbol)
                if mtf_result:
                    signal_scores['mtf'] = mtf_result['final_score'] / 10.0
                    signal_details['mtf'] = [
                        f"MTF 점수: {mtf_result['final_score']:.1f}/10",
                        f"합의: {mtf_result['consensus_level']:.1%}",
                        f"추세: {mtf_result['dominant_trend']}"
                    ]
                else:
                    signal_scores['mtf'] = 0.5
                    signal_details['mtf'] = ["MTF 분석 불가"]
            except Exception as e:
                logger.warning(f"MTF 분석 실패: {e}")
                signal_scores['mtf'] = 0.5
                signal_details['mtf'] = ["MTF 오류"]
        else:
            signal_scores['mtf'] = 0.5
            signal_details['mtf'] = ["MTF 비활성화"]
        
        # 5-3. 머신러닝 예측
        if ML_CONFIG['enabled'] and self.ml_generator:
            try:
                ml_prediction = self.ml_generator.predict(symbol)
                if ml_prediction:
                    signal_scores['ml'] = ml_prediction['buy_probability']
                    signal_details['ml'] = [
                        f"ML 매수 확률: {ml_prediction['buy_probability']:.1%}",
                        f"신뢰도: {ml_prediction['confidence']:.1%}"
                    ]
                else:
                    signal_scores['ml'] = 0.5
                    signal_details['ml'] = ["ML 예측 불가"]
            except Exception as e:
                logger.warning(f"ML 예측 실패: {e}")
                signal_scores['ml'] = 0.5
                signal_details['ml'] = ["ML 오류"]
        else:
            signal_scores['ml'] = 0.5
            signal_details['ml'] = ["ML 비활성화"]
        
        # 6. 가중 평균 최종 점수 계산
        final_score = sum(
            signal_scores[key] * self.signal_weights[key]
            for key in signal_scores.keys()
        ) * 10  # 0~10 스케일로 변환
        
        # 7. 시장 상황에 따른 기준 조정
        market_condition = self.market_analyzer.analyze_market(TRADING_PAIRS)
        base_threshold = ADVANCED_CONFIG.get('entry_score_threshold', 6)
        
        market_adjustments = SIGNAL_INTEGRATION_CONFIG.get('market_adjustment', {
            'bullish': 0.0,
            'neutral': 0.0,
            'bearish': 0.0
        })
        
        adjustment = market_adjustments.get(market_condition, 0.0)
        adjusted_threshold = base_threshold + adjustment
        
        logger.info(f"시장: {market_condition}, "
                    f"기준: {base_threshold:.1f} → {adjusted_threshold:.1f} "
                    f"(조정: {adjustment:+.1f})")
        
        # 고변동성 체크
        volatility = indicators.get('volatility', 0)
        if volatility > 0.03:
            logger.warning(f"{symbol}: 고변동성 감지 ({volatility:.1%}) - 포지션 크기 50% 축소")
        
        # 8. 상세 로깅
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 {symbol} 종합 분석")
        logger.info(f"{'='*60}")
        logger.info(f"🔧 기술적 분석: {signal_scores['technical']:.2f} "
                   f"(가중치: {self.signal_weights['technical']:.0%})")
        for detail in signal_details['technical']:
            logger.info(f"   - {detail}")
        
        logger.info(f"📈 멀티 타임프레임: {signal_scores['mtf']:.2f} "
                   f"(가중치: {self.signal_weights['mtf']:.0%})")
        for detail in signal_details['mtf']:
            logger.info(f"   - {detail}")
        
        logger.info(f"🤖 머신러닝: {signal_scores['ml']:.2f} "
                   f"(가중치: {self.signal_weights['ml']:.0%})")
        for detail in signal_details['ml']:
            logger.info(f"   - {detail}")
        
        logger.info(f"\n최종 점수: {final_score:.2f}/10")
        logger.info(f"진입 기준: {adjusted_threshold:.2f} (시장: {market_condition})")
        logger.info(f"{'='*60}\n")
        
        # 9. 최종 판단
        if final_score >= adjusted_threshold:
            return True, (f"✅ 진입 조건 충족 (점수: {final_score:.2f}/{adjusted_threshold:.2f}, "
                         f"시장: {market_condition})")
        
        return False, (f"❌ 진입 조건 미충족 (점수: {final_score:.2f}/{adjusted_threshold:.2f})")
    
    def record_trade(self, symbol, trade_type):
        """거래 기록"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_trades[today] += 1
        
        if trade_type == 'buy':
            self.position_entry_time[symbol] = time.time()
        elif trade_type == 'sell':
            if symbol in self.position_entry_time:
                del self.position_entry_time[symbol]
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
    
    def retrain_ml_model(self):
        """ML 모델 재학습"""
        logger.info("🔄 ML 모델 재학습 시작...")
        success = self.ml_generator.train_model(TRADING_PAIRS, retrain=True)
        if success:
            logger.info("✅ ML 모델 재학습 완료")
        return success
    
    def evaluate_ml_performance(self, days=7):
        """ML 모델 성능 평가"""
        self.ml_generator.evaluate_recent_performance(TRADING_PAIRS, days=days)