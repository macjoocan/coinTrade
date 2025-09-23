# improved_strategy.py

import time
from datetime import datetime, timedelta
from collections import defaultdict
from config import STRATEGY_CONFIG

class ImprovedStrategy:
    def __init__(self):
        self.min_profit_target = STRATEGY_CONFIG['min_profit_target']
        self.max_trades_per_day = STRATEGY_CONFIG['max_trades_per_day']
        self.min_hold_time = STRATEGY_CONFIG['min_hold_time']
        
        # 거래 추적용
        self.daily_trades = defaultdict(int)
        self.position_entry_time = {}
        
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
    
    def record_trade(self, symbol, trade_type):
        """거래 기록"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_trades[today] += 1
        
        if trade_type == 'buy':
            self.position_entry_time[symbol] = time.time()
        elif trade_type == 'sell' and symbol in self.position_entry_time:
            del self.position_entry_time[symbol]
    
    def check_profit_target(self, entry_price, current_price):
        """최소 수익률 달성 여부 확인"""
        profit_rate = (current_price - entry_price) / entry_price
        return profit_rate >= self.min_profit_target