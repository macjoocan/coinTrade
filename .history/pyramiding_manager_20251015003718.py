# pyramiding_manager.py - 안전한 추매 시스템

import logging
from datetime import datetime
import pyupbit
from config import PYRAMIDING_CONFIG

logger = logging.getLogger(__name__)

class PyramidingManager:
    """조건부 추매 관리자"""
    
    def __init__(self):
        self.enabled = PYRAMIDING_CONFIG.get('enabled', False)
        self.max_pyramids = PYRAMIDING_CONFIG.get('max_pyramids', 1)
        self.min_score_increase = PYRAMIDING_CONFIG.get('min_score_increase', 1.0)
        self.min_profit = PYRAMIDING_CONFIG.get('min_profit_for_pyramid', 0.02)
        self.pyramid_size_ratio = PYRAMIDING_CONFIG.get('pyramid_size_ratio', 0.5)
        self.max_total_position = PYRAMIDING_CONFIG.get('max_total_position', 0.35)
        
        # 추매 기록
        self.pyramid_history = {}  # {symbol: [entry_scores, entry_prices]}
        
    def can_pyramid(self, symbol, current_score, current_price, position, market_condition):
        """추매 가능 여부 판단"""
        
        if not self.enabled:
            return False, "추매 기능 비활성화"
        
        # 1. 기존 포지션 확인
        if symbol not in position:
            return False, "기존 포지션 없음"
        
        pos = position[symbol]
        entry_price = pos.get('entry_price')
        quantity = pos.get('quantity', 0)
        
        if not entry_price or quantity == 0:
            return False, "포지션 정보 불완전"
        
        # 2. 추매 횟수 체크
        pyramid_count = self.pyramid_history.get(symbol, {}).get('count', 0)
        if pyramid_count >= self.max_pyramids:
            return False, f"최대 추매 횟수 도달 ({pyramid_count}/{self.max_pyramids})"
        
        # 3. 수익 상태 체크 ⚠️ 가장 중요
        profit_rate = (current_price - entry_price) / entry_price
        if profit_rate < self.min_profit:
            return False, f"수익률 부족 ({profit_rate:.1%} < {self.min_profit:.1%})"
        
        # 4. 점수 향상 체크
        previous_score = self.pyramid_history.get(symbol, {}).get('last_score', 0)
        if previous_score > 0:
            score_increase = current_score - previous_score
            if score_increase < self.min_score_increase:
                return False, f"점수 상승 부족 (+{score_increase:.1f} < +{self.min_score_increase:.1f})"
        
        # 5. 시장 조건 체크
        allowed_markets = PYRAMIDING_CONFIG.get('allowed_markets', ['bullish'])
        if market_condition not in allowed_markets:
            return False, f"시장 조건 부적합 ({market_condition})"
        
        # 6. 모든 신호 확인 필요
        if PYRAMIDING_CONFIG.get('require_all_signals', True):
            # 이건 외부에서 체크하도록 (improved_strategy.py에서)
            pass
        
        # 7. 최대 포지션 크기 체크
        current_value = entry_price * quantity
        # 추가 매수 가능한 금액 계산은 외부에서
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ {symbol} 추매 조건 충족!")
        logger.info(f"   현재 수익률: {profit_rate:+.1%}")
        logger.info(f"   신호 점수: {current_score:.1f}")
        logger.info(f"   추매 횟수: {pyramid_count + 1}/{self.max_pyramids}")
        logger.info(f"{'='*60}")
        
        return True, "추매 조건 충족"
    
    def calculate_pyramid_size(self, symbol, current_balance, current_price, existing_position):
        """추매 크기 계산"""
        
        # 기존 포지션 정보
        entry_price = existing_position.get('entry_price')
        quantity = existing_position.get('quantity')
        existing_value = entry_price * quantity
        
        # 추매 크기: 기존의 50%
        pyramid_value = existing_value * self.pyramid_size_ratio
        
        # 최대 포지션 제한 체크
        total_value = existing_value + pyramid_value
        max_allowed_value = current_balance * self.max_total_position
        
        if total_value > max_allowed_value:
            # 초과하면 조정
            pyramid_value = max_allowed_value - existing_value
            logger.warning(f"포지션 크기 조정: {pyramid_value:,.0f}원")
        
        # 최소 주문 금액
        if pyramid_value < 5000:
            return 0, "추매 금액 너무 작음"
        
        pyramid_quantity = pyramid_value / current_price
        
        return pyramid_quantity, "OK"
    
    def record_pyramid(self, symbol, entry_price, score):
        """추매 기록"""
        
        if symbol not in self.pyramid_history:
            self.pyramid_history[symbol] = {
                'count': 0,
                'prices': [],
                'scores': [],
                'timestamps': []
            }
        
        self.pyramid_history[symbol]['count'] += 1
        self.pyramid_history[symbol]['prices'].append(entry_price)
        self.pyramid_history[symbol]['scores'].append(score)
        self.pyramid_history[symbol]['timestamps'].append(datetime.now())
        self.pyramid_history[symbol]['last_score'] = score
        
        logger.info(f"📝 {symbol} 추매 기록: {self.pyramid_history[symbol]['count']}회차")
    
    def calculate_average_entry(self, symbol):
        """평균 단가 계산"""
        
        if symbol not in self.pyramid_history:
            return None
        
        prices = self.pyramid_history[symbol]['prices']
        if not prices:
            return None
        
        # 간단 평균 (실제로는 수량 가중 평균 필요)
        avg_price = sum(prices) / len(prices)
        return avg_price
    
    def should_use_breakeven_stop(self, symbol, current_price):
        """손익분기점 손절 체크"""
        
        if not PYRAMIDING_CONFIG.get('use_breakeven_stop', True):
            return False
        
        avg_entry = self.calculate_average_entry(symbol)
        if not avg_entry:
            return False
        
        # 평균 단가 아래로 떨어지면 손절
        if current_price < avg_entry:
            logger.warning(f"⚠️ {symbol} 평균단가 이탈: {current_price:,.0f} < {avg_entry:,.0f}")
            return True
        
        return False
    
    def reset_pyramid(self, symbol):
        """포지션 청산 시 추매 기록 초기화"""
        if symbol in self.pyramid_history:
            del self.pyramid_history[symbol]
            logger.info(f"🔄 {symbol} 추매 기록 초기화")
    
    def get_pyramid_info(self, symbol):
        """추매 정보 조회"""
        return self.pyramid_history.get(symbol, {})
