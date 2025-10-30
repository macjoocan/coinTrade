# averaging_down_manager.py
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AveragingDownManager:
    """물타기 관리 시스템 - 간단한 버전"""
    
    def __init__(self, config):
        self.config = config
        self.averaging_history = {}  # {symbol: [매수1, 매수2, ...]}
    
    def should_average_down(self, symbol, position, current_price):
        """물타기 실행 여부 판단"""
        
        # 비활성화 체크
        if not self.config.get('enabled', False):
            return False, "물타기 비활성화"
        
        # 기존 물타기 횟수 체크
        avg_count = len(self.averaging_history.get(symbol, []))
        max_count = self.config.get('max_averaging_count', 2)
        
        if avg_count >= max_count:
            return False, f"최대 물타기 횟수 도달 ({avg_count}회)"
        
        # 손실률 계산
        entry_price = position['entry_price']
        loss_rate = (current_price - entry_price) / entry_price
        
        # 최대 손실 한도 체크 (안전장치)
        max_total_loss = self.config.get('max_total_loss', -0.08)
        if loss_rate <= max_total_loss:
            return False, f"최대 손실 한도 도달 ({loss_rate:.1%})"
        
        # 물타기 트리거 (-1.0%)
        trigger_loss = self.config.get('trigger_loss_rate', -0.01)
        
        # 첫 번째 물타기: -1.0% 이하
        if avg_count == 0 and loss_rate <= trigger_loss:
            logger.info(f"✅ {symbol} 1차 물타기 조건 충족! (현재: {loss_rate:.2%})")
            return True, "1차 물타기"
        
        # 추가 물타기: 이전 물타기 대비 추가 -1.0%
        if avg_count > 0:
            last_avg = self.averaging_history[symbol][-1]
            last_avg_price = last_avg['price']
            
            # 마지막 물타기 가격 대비 손실률
            loss_from_last = (current_price - last_avg_price) / last_avg_price
            
            if loss_from_last <= trigger_loss:
                logger.info(f"✅ {symbol} {avg_count + 1}차 물타기 조건 충족!")
                logger.info(f"   마지막 물타기 대비: {loss_from_last:.2%}")
                return True, f"{avg_count + 1}차 물타기"
        
        return False, "물타기 조건 미달"
    
    def calculate_averaging_size(self, symbol, original_value):
        """물타기 금액 계산"""
        avg_count = len(self.averaging_history.get(symbol, []))
        
        # 기본: 원래 포지션과 동일한 금액
        ratio = self.config.get('averaging_size_ratio', 1.0)
        
        return original_value * ratio
    
    def record_averaging(self, symbol, price, quantity, amount):
        """물타기 기록"""
        if symbol not in self.averaging_history:
            self.averaging_history[symbol] = []
        
        record = {
            'price': price,
            'quantity': quantity,
            'amount': amount,
            'timestamp': datetime.now()
        }
        
        self.averaging_history[symbol].append(record)
        
        count = len(self.averaging_history[symbol])
        logger.info(f"📊 {symbol} 물타기 기록 추가:")
        logger.info(f"   회차: {count}차")
        logger.info(f"   가격: {price:,.0f} KRW")
        logger.info(f"   수량: {quantity:.8f}")
        logger.info(f"   금액: {amount:,.0f} KRW")
    
    def calculate_average_price(self, symbol, original_entry_price, original_quantity):
        """평균 매수가 계산"""
        if symbol not in self.averaging_history or not self.averaging_history[symbol]:
            return original_entry_price
        
        # 총 금액과 총 수량 계산
        total_amount = original_entry_price * original_quantity
        total_quantity = original_quantity
        
        for avg in self.averaging_history[symbol]:
            total_amount += avg['price'] * avg['quantity']
            total_quantity += avg['quantity']
        
        avg_price = total_amount / total_quantity if total_quantity > 0 else original_entry_price
        
        return avg_price
    
    def get_averaging_info(self, symbol):
        """물타기 정보 조회"""
        if symbol not in self.averaging_history:
            return {
                'count': 0,
                'total_amount': 0,
                'total_quantity': 0,
                'history': []
            }
        
        history = self.averaging_history[symbol]
        total_amount = sum(h['amount'] for h in history)
        total_quantity = sum(h['quantity'] for h in history)
        
        return {
            'count': len(history),
            'total_amount': total_amount,
            'total_quantity': total_quantity,
            'history': history
        }
    
    def clear_history(self, symbol):
        """청산 시 기록 삭제"""
        if symbol in self.averaging_history:
            count = len(self.averaging_history[symbol])
            del self.averaging_history[symbol]
            logger.info(f"🧹 {symbol} 물타기 기록 삭제 ({count}회)")
    
    def get_all_stats(self):
        """전체 물타기 통계"""
        total_count = sum(len(history) for history in self.averaging_history.values())
        active_symbols = list(self.averaging_history.keys())
        
        return {
            'total_averaging_count': total_count,
            'active_symbols': active_symbols,
            'active_positions': len(active_symbols)
        }