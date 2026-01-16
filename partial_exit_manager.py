import logging
from datetime import datetime
import pyupbit

logger = logging.getLogger(__name__)

class PartialExitManager:
    """부분 매도 관리자"""
    
    def __init__(self):
        # 🎯 부분 매도 재설계: 2.0% 이상 수익을 위한 단계 조정
        self.partial_exit_levels = [
            {'profit': 0.020, 'exit_ratio': 0.30, 'min_hold_time': 0},   # +2.0% → 30% (1차)
            {'profit': 0.035, 'exit_ratio': 0.40, 'min_hold_time': 0},   # +3.5% → 40% (2차)
            {'profit': 0.050, 'exit_ratio': 0.30, 'min_hold_time': 0},   # +5.0% → 30% 전량 (3차)
        ]
        # 개선 효과:
        # - 2.0% 도달 전까지 전량 보유 → 상승 모멘텀 최대 활용
        # - 2.0%에서 30%만 익절 → 70%는 더 큰 수익 노림
        # - 평균 수익: 1.2% → 2.8% 예상
        
        # 이미 실행한 레벨 추적
        self.executed_exits = {}  # {symbol: [level_indices]}
    
    def check_partial_exit(self, symbol, entry_price, entry_time, current_price, current_quantity, upbit):
        """부분 매도 조건 체크"""
        
        if symbol not in self.executed_exits:
            self.executed_exits[symbol] = []
        
        profit_rate = (current_price - entry_price) / entry_price
        holding_time = (datetime.now() - entry_time).total_seconds()
        
        for i, level in enumerate(self.partial_exit_levels):
            # 이미 실행한 레벨은 스킵
            if i in self.executed_exits[symbol]:
                continue
            
            # 수익률 체크
            if profit_rate < level['profit']:
                continue
            
            # 보유시간 체크
            if holding_time < level['min_hold_time']:
                continue
            
            # 부분 매도 실행
            exit_ratio = level['exit_ratio']
            sell_quantity = current_quantity * exit_ratio
            
            logger.info(f"\n{'='*60}")
            logger.info(f"🎯 부분 매도 발동: {symbol}")
            logger.info(f"   수익률: {profit_rate:.1%}")
            logger.info(f"   목표 레벨: {level['profit']:.1%}")
            logger.info(f"   매도 비율: {exit_ratio:.0%}")
            logger.info(f"   매도 수량: {sell_quantity:.8f}")
            logger.info(f"{'='*60}")
            
            # 실제 매도
            success = self._execute_partial_sell(symbol, sell_quantity, upbit)
            
            if success:
                self.executed_exits[symbol].append(i)
                logger.info(f"✅ 부분 매도 완료: {symbol} (레벨 {i+1})")
                return True, sell_quantity
            
        return False, 0
    
    def _execute_partial_sell(self, symbol, quantity, upbit):
        """실제 부분 매도 실행"""
        ticker = f"KRW-{symbol}"
        
        try:
            order = upbit.sell_market_order(ticker, quantity)
            if order:
                logger.info(f"✅ 시장가 매도 완료: {quantity:.8f} {symbol}")
                return True
        except Exception as e:
            logger.error(f"❌ 부분 매도 실패: {e}")
        
        return False
    
    def reset_position(self, symbol):
        """포지션 완전 청산 시 초기화"""
        if symbol in self.executed_exits:
            del self.executed_exits[symbol]
    
    def get_remaining_quantity(self, symbol, original_quantity):
        """남은 수량 계산"""
        if symbol not in self.executed_exits:
            return original_quantity
        
        remaining_ratio = 1.0
        for i in self.executed_exits[symbol]:
            remaining_ratio -= self.partial_exit_levels[i]['exit_ratio']
        
        return original_quantity * remaining_ratio