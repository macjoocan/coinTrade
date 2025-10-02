# risk_manager.py 개선 버전

import pyupbit  # 추가 필요
from datetime import datetime
from collections import defaultdict
from config import RISK_CONFIG, ADVANCED_CONFIG
import logging
import numpy as np

# STABLE_PAIRS 안전하게 import
try:
    from config import STABLE_PAIRS
except ImportError:
    STABLE_PAIRS = ['BTC', 'ETH', 'SOL']

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.max_position_size = RISK_CONFIG['max_position_size']
        self.stop_loss = RISK_CONFIG['stop_loss']
        self.daily_loss_limit = RISK_CONFIG['daily_loss_limit']
        self.max_positions = RISK_CONFIG['max_positions']
        
        # MarketAnalyzer는 선택적으로
        try:
            from market_condition_check import MarketAnalyzer
            self.market_analyzer = MarketAnalyzer()
        except ImportError:
            self.market_analyzer = None
            logger.warning("MarketAnalyzer를 로드할 수 없습니다")
        
        # 일일 손익 추적
        self.daily_pnl = defaultdict(float)
        self.positions = {}
        
        # 리스크 메트릭
        self.consecutive_losses = 0
        self.max_consecutive_losses = ADVANCED_CONFIG.get('max_consecutive_losses', 3)
        self.daily_trades = defaultdict(list)
        
        # 전체 거래 기록 (승률 계산용)
        self.all_trades_history = []
        
        # Kelly Criterion 파라미터
        self.win_rate = 0.5
        self.avg_win_loss_ratio = 1.5
        
        # 디버그 정보
        self.last_calculated_win_rate = 0.5
        self.total_wins = 0
        self.total_losses = 0
    
    def calculate_position_size(self, balance, symbol, current_price, volatility=None, indicators=None):
        """포지션 크기 계산"""
        
        # Kelly Criterion
        kelly_fraction = self._calculate_kelly_fraction()
        base_position_value = balance * min(self.max_position_size, kelly_fraction)
        
        # 동적 코인 체크
        if symbol not in STABLE_PAIRS:
            base_position_value *= 0.6
            logger.info(f"{symbol}: 동적 코인 - 포지션 60% 축소")
        
        # 시장 상황별 조정
        if self.market_analyzer:
            multiplier = self.market_analyzer.get_position_size_multiplier()
            base_position_value *= multiplier
        
        # 변동성 조정
        if volatility and volatility > 0:
            vol_adjustment = min(1.0, 0.02 / volatility)
            base_position_value *= vol_adjustment
        
        # 연속 손실 조정
        if self.consecutive_losses > 0:
            loss_adjustment = 1.0 / (1 + self.consecutive_losses * 0.2)
            base_position_value *= loss_adjustment
            logger.info(f"연속 손실 {self.consecutive_losses}회 - 포지션 {loss_adjustment:.1%}로 조정")
        
        # 최종 계산
        min_order_amount = 5000
        max_order_amount = balance * self.max_position_size
        
        final_position_value = max(min_order_amount, min(base_position_value, max_order_amount))
        
        if final_position_value < min_order_amount:
            return 0
        
        return final_position_value / current_price
    
    def update_position(self, symbol, entry_price, quantity, trade_type):
        """포지션 업데이트 - 개선된 버전"""
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
            pnl_rate = (pnl / (position['entry_price'] * quantity) 
                       if position['entry_price'] * quantity > 0 else 0)
            
            # 거래 기록
            today = datetime.now().strftime('%Y-%m-%d')
            trade_record = {
                'symbol': symbol,
                'pnl': pnl,
                'pnl_rate': pnl_rate,
                'timestamp': datetime.now()
            }
            
            self.daily_pnl[today] += pnl
            self.daily_trades[today].append(trade_record)
            self.all_trades_history.append(trade_record)
            
            # 승/패 카운트
            if pnl > 0:
                self.total_wins += 1
                self.consecutive_losses = max(0, self.consecutive_losses - 1)
            else:
                self.total_losses += 1
                self.consecutive_losses += 1
            
            # 통계 업데이트
            self._update_statistics()
            
            # 로깅
            logger.info(f"포지션 청산: {symbol}, PnL: {pnl:+,.0f} ({pnl_rate:+.1%})")
            logger.info(f"통계: {self.total_wins}승 {self.total_losses}패 "
                       f"(승률: {self.win_rate:.1%})")
            
            del self.positions[symbol]
    
    def _update_statistics(self):
        """통계 업데이트 - 실시간 반영"""
        total_trades = len(self.all_trades_history)
        
        if total_trades > 0:
            wins = [t for t in self.all_trades_history if t['pnl'] > 0]
            losses = [t for t in self.all_trades_history if t['pnl'] <= 0]
            
            # 승률 실시간 업데이트
            self.win_rate = len(wins) / total_trades
            
            # 손익비 계산
            if wins and losses:
                avg_win = np.mean([abs(t['pnl']) for t in wins])
                avg_loss = np.mean([abs(t['pnl']) for t in losses])
                self.avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
            
            logger.debug(f"통계 업데이트: 승률={self.win_rate:.1%}, "
                        f"손익비={self.avg_win_loss_ratio:.2f}, "
                        f"총거래={total_trades}")
    
    def get_risk_status(self):
        """현재 리스크 상태 - 실시간 가치 반영"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 현재 가격으로 포지션 가치 재계산
        total_value = self.current_balance
        for symbol, pos in self.positions.items():
            try:
                current_price = pyupbit.get_current_price(f"KRW-{symbol}")
                if current_price:
                    total_value += current_price * pos['quantity']
                else:
                    total_value += pos['value']
            except:
                total_value += pos['value']
        
        return {
            'current_balance': self.current_balance,
            'total_value': total_value,
            'daily_pnl': self.daily_pnl[today],
            'daily_pnl_rate': (self.daily_pnl[today] / self.initial_balance 
                              if self.initial_balance > 0 else 0),
            'consecutive_losses': self.consecutive_losses,
            'active_positions': len(self.positions),
            'win_rate': self.win_rate,
            'kelly_fraction': self._calculate_kelly_fraction(),
            'total_trades': len(self.all_trades_history),
            'wins': self.total_wins,
            'losses': self.total_losses
        }