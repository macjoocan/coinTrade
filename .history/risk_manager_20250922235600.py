# risk_manager.py

from datetime import datetime
from collections import defaultdict
from config import RISK_CONFIG
import logging
import numpy as np

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.max_position_size = RISK_CONFIG['max_position_size']
        self.stop_loss = RISK_CONFIG['stop_loss']
        self.daily_loss_limit = RISK_CONFIG['daily_loss_limit']
        self.max_positions = RISK_CONFIG['max_positions']
        
        # 일일 손익 추적
        self.daily_pnl = defaultdict(float)
        self.positions = {}
        
        # 리스크 메트릭
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        self.daily_trades = defaultdict(list)
        
        # Kelly Criterion 파라미터
        self.win_rate = 0.5  # 초기값, 실제 거래로 업데이트
        self.avg_win_loss_ratio = 1.5  # 초기값
        
    def calculate_position_size(self, balance, symbol, current_price, volatility=None, indicators=None):
        """고급 포지션 크기 계산 (Kelly Criterion + 변동성 조정)"""
        
        # 1. Kelly Criterion으로 최적 포지션 크기 계산
        kelly_fraction = self._calculate_kelly_fraction()
        
        # 2. 기본 포지션 크기
        base_position_value = balance * min(self.max_position_size, kelly_fraction)
        
        # 3. 변동성 조정
        if volatility:
            # ATR 기반 조정 (변동성이 높을수록 포지션 감소)
            vol_adjustment = min(1.0, 0.02 / max(volatility, 0.001))
            base_position_value *= vol_adjustment
        
        # 4. 연속 손실 조정
        if self.consecutive_losses > 0:
            # 연속 손실 시 포지션 크기 감소
            loss_adjustment = 1.0 / (1 + self.consecutive_losses * 0.2)
            base_position_value *= loss_adjustment
            logger.info(f"연속 손실 {self.consecutive_losses}회 - 포지션 크기 {loss_adjustment:.1%} 조정")
        
        # 5. 시장 상황 조정
        if indicators:
            market_condition = self._assess_market_condition(indicators)
            base_position_value *= market_condition
        
        # 6. 최대/최소 제한
        min_order_amount = 5000  # 업비트 최소 주문 금액
        max_order_amount = balance * self.max_position_size
        
        final_position_value = max(min_order_amount, min(base_position_value, max_order_amount))
        
        if final_position_value < min_order_amount:
            return 0
        
        quantity = final_position_value / current_price
        
        logger.info(f"포지션 크기 계산: {symbol}")
        logger.info(f"  - Kelly: {kelly_fraction:.1%}, 변동성: {volatility:.3f}")
        logger.info(f"  - 최종 금액: {final_position_value:,.0f} KRW")
        logger.info(f"  - 수량: {quantity:.8f}")
        
        return quantity
    
    def _calculate_kelly_fraction(self):
        """Kelly Criterion 계산"""
        if self.win_rate <= 0 or self.avg_win_loss_ratio <= 0:
            return 0.02  # 기본값 2%
        
        # Kelly 공식: f = (p*b - q) / b
        # p: 승률, q: 패율(1-p), b: 평균 손익비
        p = self.win_rate
        q = 1 - p
        b = self.avg_win_loss_ratio
        
        kelly = (p * b - q) / b
        
        # Kelly의 25% 사용 (보수적 접근)
        conservative_kelly = kelly * 0.25
        
        # 최대 10%로 제한
        return min(max(conservative_kelly, 0.01), 0.1)
    
    def _assess_market_condition(self, indicators):
        """시장 상황 평가"""
        score = 1.0
        
        # 추세 확인
        if indicators.get('trend') == 'strong_up':
            score *= 1.2
        elif indicators.get('trend') == 'down':
            score *= 0.8
        
        # RSI 확인
        rsi = indicators.get('rsi', 50)
        if rsi > 70:  # 과매수
            score *= 0.7
        elif rsi < 30:  # 과매도
            score *= 1.1
        
        return min(max(score, 0.5), 1.5)
    
    def check_stop_loss(self, symbol, current_price):
        """동적 손절 체크"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        holding_time = (datetime.now() - position['entry_time']).total_seconds() / 3600
        
        # 시간에 따른 손절 조정 (시간이 지날수록 타이트하게)
        time_adjusted_stop_loss = self.stop_loss * (1 - min(holding_time / 24, 0.3))
        
        loss_rate = (current_price - entry_price) / entry_price
        
        if loss_rate <= -time_adjusted_stop_loss:
            logger.warning(f"{symbol} 손절 신호: {loss_rate:.1%} (조정된 손절선: {-time_adjusted_stop_loss:.1%})")
            return True
        
        return False
    
    def check_trailing_stop(self, symbol, current_price):
        """추적 손절 체크"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        entry_price = position['entry_price']
        highest_price = position.get('highest_price', entry_price)
        
        # 최고가 업데이트
        if current_price > highest_price:
            self.positions[symbol]['highest_price'] = current_price
            highest_price = current_price
        
        # 수익 중일 때 추적 손절 적용
        profit_rate = (highest_price - entry_price) / entry_price
        if profit_rate > 0.02:  # 2% 이상 수익
            trailing_stop = highest_price * (1 - 0.01)  # 최고가 대비 1% 하락 시
            if current_price <= trailing_stop:
                logger.info(f"{symbol} 추적 손절 발동: 최고가 {highest_price:,.0f} → 현재가 {current_price:,.0f}")
                return True
        
        return False
    
    def update_position(self, symbol, entry_price, quantity, trade_type):
        """포지션 업데이트 (강화된 추적)"""
        if trade_type == 'buy':
            self.positions[symbol] = {
                'entry_price': entry_price,
                'quantity': quantity,
                'value': entry_price * quantity,
                'entry_time': datetime.now(),
                'highest_price': entry_price
            }
            logger.info(f"포지션 추가: {symbol} @ {entry_price:,.0f}")
            
        elif trade_type == 'sell' and symbol in self.positions:
            position = self.positions[symbol]
            pnl = (entry_price - position['entry_price']) * quantity